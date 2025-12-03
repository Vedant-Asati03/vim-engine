"""Dataclasses describing keymap bindings and action metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Callable, Iterable, Mapping, MutableMapping


def _normalize_modifiers(modifiers: Iterable[str]) -> tuple[str, ...]:
    values = tuple(m.strip().lower() for m in modifiers if m.strip())
    return tuple(sorted(dict.fromkeys(values)))


@dataclass(frozen=True, slots=True)
class KeyStroke:
    """Single normalized key press used by key sequences."""

    key: str
    modifiers: tuple[str, ...] = ()
    text: str | None = None

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("key cannot be empty")
        object.__setattr__(self, "modifiers", _normalize_modifiers(self.modifiers))

    @property
    def token(self) -> str:
        if self.modifiers:
            modifier = "+".join(self.modifiers)
            return f"{modifier}+{self.key}"
        return self.key


@dataclass(frozen=True, slots=True)
class KeySequence:
    """Immutable collection of keystrokes."""

    strokes: tuple[KeyStroke, ...]
    timeout_ms: int = 1000

    def __post_init__(self) -> None:
        if not self.strokes:
            raise ValueError("KeySequence requires at least one stroke")

    @property
    def tokens(self) -> tuple[str, ...]:
        return tuple(stroke.token for stroke in self.strokes)

    def prepend(self, *strokes: KeyStroke) -> "KeySequence":
        return KeySequence(tuple(strokes) + self.strokes, timeout_ms=self.timeout_ms)

    def append(self, *strokes: KeyStroke) -> "KeySequence":
        return KeySequence(self.strokes + tuple(strokes), timeout_ms=self.timeout_ms)

    @classmethod
    def from_strings(cls, *keys: str, timeout_ms: int = 1000) -> "KeySequence":
        strokes = tuple(KeyStroke(key) for key in keys if key)
        return cls(strokes=strokes, timeout_ms=timeout_ms)


@dataclass(frozen=True, slots=True)
class WhenClause:
    """Simple boolean condition used to gate bindings."""

    flag: str
    expected: bool = True

    def __post_init__(self) -> None:
        if not self.flag:
            raise ValueError("flag cannot be empty")

    @classmethod
    def parse(cls, expression: str) -> "WhenClause":
        expr = expression.strip()
        if not expr:
            raise ValueError("expression cannot be empty")
        expected = True
        if expr.startswith("!"):
            expected = False
            expr = expr[1:]
        return cls(expr, expected)

    def evaluate(self, context: Mapping[str, bool]) -> bool:
        return bool(context.get(self.flag, False)) is self.expected


@dataclass(frozen=True, slots=True)
class ActionRef:
    """Callable metadata used during binding execution."""

    id: str
    handler: Callable[..., object]
    telemetry_name: str | None = None
    description: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("ActionRef id cannot be empty")
        if not callable(self.handler):
            raise TypeError("handler must be callable")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        if self.telemetry_name is None:
            object.__setattr__(self, "telemetry_name", self.id)

    def __call__(self, *args: object, **kwargs: object) -> object:
        return self.handler(*args, **kwargs)


def _normalize_tags(tags: Iterable[str]) -> tuple[str, ...]:
    seen: MutableMapping[str, None] = {}
    result: list[str] = []
    for tag in tags:
        cleaned = tag.strip()
        if cleaned and cleaned not in seen:
            seen[cleaned] = None
            result.append(cleaned)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class Binding:
    """Associates a key sequence with an action and context."""

    id: str
    mode: str
    sequence: KeySequence
    action_id: str
    description: str = ""
    when: tuple[WhenClause, ...] = ()
    tags: tuple[str, ...] = ()
    source: str | None = None
    priority: int = 0

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("binding id cannot be empty")
        if not self.mode:
            raise ValueError("binding mode cannot be empty")
        if not self.action_id:
            raise ValueError("binding action_id cannot be empty")
        object.__setattr__(self, "tags", _normalize_tags(self.tags))
        normalized_when = tuple(
            clause if isinstance(clause, WhenClause) else WhenClause.parse(str(clause))
            for clause in self.when
        )
        object.__setattr__(self, "when", normalized_when)

    @property
    def when_map(self) -> Mapping[str, bool]:
        return MappingProxyType({clause.flag: clause.expected for clause in self.when})

    def allows(self, context: Mapping[str, bool]) -> bool:
        return all(clause.evaluate(context) for clause in self.when)

    @property
    def key_signature(self) -> str:
        return " ".join(self.sequence.tokens)


__all__ = [
    "KeyStroke",
    "KeySequence",
    "WhenClause",
    "ActionRef",
    "Binding",
]
