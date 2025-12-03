"""Base classes and shared utilities for editor modes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Tuple

from vim_engine.buffer import Buffer, RegisterBank


@dataclass(slots=True)
class KeyInput:
    """Normalized key event passed to modes."""

    key: str
    modifiers: Tuple[str, ...] = ()
    text: Optional[str] = None


@dataclass(slots=True)
class ModeResult:
    """Result returned from ``Mode.handle_key``."""

    consumed: bool
    switch_to: Optional[str] = None
    status: str = "ok"
    message: Optional[str] = None
    timeout_ms: Optional[int] = None


@dataclass(slots=True)
class ModeContext:
    """Shared services every mode can access."""

    buffer: Buffer
    registers: RegisterBank
    bus: "ModeBus"
    extras: Dict[str, object] = field(default_factory=dict)


class ModeBus:
    """Minimal event bus letting modes exchange structured signals."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, list[Callable[[object], None]]] = {}

    def subscribe(self, event: str, callback: Callable[[object], None]) -> None:
        self._subscribers.setdefault(event, []).append(callback)

    def emit(self, event: str, payload: object | None = None) -> None:
        for callback in self._subscribers.get(event, []):
            callback(payload)


class Mode:
    """Base class all concrete editor modes inherit from."""

    name: str = "mode"

    def __init__(self, context: ModeContext) -> None:
        self.context = context

    def on_enter(
        self, previous: Optional[str]
    ) -> None:  # pragma: no cover - default no-op
        del previous

    def on_exit(
        self, next_mode: Optional[str]
    ) -> None:  # pragma: no cover - default no-op
        del next_mode

    def handle_key(
        self, key: KeyInput
    ) -> ModeResult:  # pragma: no cover - abstract override
        raise NotImplementedError

    def handle_timeout(self) -> ModeResult:
        """Invoked by the manager when a pending key sequence expires."""

        return ModeResult(consumed=False, status="timeout")
