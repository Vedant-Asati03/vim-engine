"""Trie-based keymap resolution with telemetry instrumentation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Literal, Mapping, Optional, Sequence

from vim_engine.runtime.telemetry import span

from .models import ActionRef, Binding
from .registry import KeymapRegistry


@dataclass(slots=True)
class TrieNode:
    """Single trie node tracking bindings and child transitions."""

    bindings: list[str] = field(default_factory=list)
    children: Dict[str, "TrieNode"] = field(default_factory=dict)

    def child(self, token: str) -> "TrieNode":
        return self.children.setdefault(token, TrieNode())

    def next_tokens(self) -> tuple[str, ...]:
        return tuple(sorted(self.children.keys()))


@dataclass(slots=True)
class KeymapTrie:
    """Concrete trie built for a given mode."""

    mode: str
    root: TrieNode = field(default_factory=TrieNode)

    def add_binding(self, binding: Binding) -> None:
        node = self.root
        for token in binding.sequence.tokens:
            node = node.child(token)
        node.bindings.append(binding.id)


@dataclass(frozen=True, slots=True)
class ResolutionMatch:
    """Resolved binding paired with its action."""

    binding: Binding
    action: ActionRef


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    """Outcome returned from the resolver."""

    status: Literal["match", "pending", "miss"]
    match: Optional[ResolutionMatch] = None
    consumed: int = 0
    next_expected: tuple[str, ...] = ()
    timeout_ms: Optional[int] = None


class KeymapResolver:
    """Builds mode-specific tries and resolves sequences."""

    def __init__(
        self, registry: KeymapRegistry, *, logger_name: str | None = None
    ) -> None:
        self._registry = registry
        self._logger_name = logger_name
        self._cache: Dict[str, tuple[int, KeymapTrie]] = {}

    def resolve(
        self,
        mode: str,
        tokens: Sequence[str],
        *,
        context: Optional[Mapping[str, bool]] = None,
    ) -> ResolutionResult:
        ctx = context or {}
        normalized = tuple(tokens)
        with span(
            "keymaps::resolve",
            logger_name=self._logger_name,
            component="keymaps",
            metadata={"mode": mode, "length": len(normalized)},
        ) as handle:
            trie = self._ensure_trie(mode)
            node = trie.root
            consumed = 0
            for token in normalized:
                child = node.children.get(token)
                if child is None:
                    handle.add_metadata("status", "miss")
                    return ResolutionResult(status="miss", consumed=consumed)
                node = child
                consumed += 1

            match = self._select_match(node, ctx)
            if match:
                handle.add_metadata("status", "match")
                handle.add_metadata("binding_id", match.binding.id)
                return ResolutionResult(
                    status="match",
                    match=match,
                    consumed=consumed,
                )

            next_expected = node.next_tokens()
            if next_expected:
                handle.add_metadata("status", "pending")
                timeout_ms = self._pending_timeout(node)
                if timeout_ms is not None:
                    handle.add_metadata("timeout_ms", timeout_ms)
                return ResolutionResult(
                    status="pending",
                    consumed=consumed,
                    next_expected=next_expected,
                    timeout_ms=timeout_ms,
                )

            handle.add_metadata("status", "miss")
            return ResolutionResult(status="miss", consumed=consumed)

    def reset(self, mode: Optional[str] = None) -> None:
        if mode is None:
            self._cache.clear()
        else:
            self._cache.pop(mode, None)

    def _ensure_trie(self, mode: str) -> KeymapTrie:
        revision = self._registry.revision()
        cached = self._cache.get(mode)
        if cached and cached[0] == revision:
            return cached[1]

        trie = KeymapTrie(mode=mode)
        for binding in self._registry.iter_bindings(mode):
            trie.add_binding(binding)
        self._cache[mode] = (revision, trie)
        return trie

    def _select_match(
        self, node: TrieNode, context: Mapping[str, bool]
    ) -> Optional[ResolutionMatch]:
        if not node.bindings:
            return None

        matches: list[ResolutionMatch] = []
        for binding_id in node.bindings:
            binding = self._registry.get_binding(binding_id)
            if not binding.allows(context):
                continue
            action = self._registry.get_action(binding.action_id)
            matches.append(ResolutionMatch(binding=binding, action=action))

        if not matches:
            return None

        matches.sort(key=lambda m: (-m.binding.priority, m.binding.id))
        return matches[0]

    def _pending_timeout(self, node: TrieNode) -> Optional[int]:
        timeouts: list[int] = []
        stack = list(node.children.values())
        while stack:
            current = stack.pop()
            for binding_id in current.bindings:
                binding = self._registry.get_binding(binding_id)
                timeouts.append(binding.sequence.timeout_ms)
            stack.extend(current.children.values())
        if not timeouts:
            return None
        return min(timeouts)


__all__ = [
    "KeymapResolver",
    "ResolutionResult",
    "ResolutionMatch",
]
