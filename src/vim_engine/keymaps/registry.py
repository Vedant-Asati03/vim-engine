"""Keymap registry responsible for storing actions and bindings."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Iterable, Iterator, Optional, Sequence

from vim_engine.runtime.telemetry import span

from .models import ActionRef, Binding, KeySequence


@dataclass(slots=True)
class RegistryStats:
    """Lightweight snapshot describing registry state."""

    action_count: int
    binding_count: int
    modes: tuple[str, ...]


class KeymapConflictError(RuntimeError):
    """Raised when a new binding conflicts with existing entries."""

    def __init__(self, binding: Binding, conflicts: Iterable[Binding]):
        conflicts_tuple = tuple(conflicts)
        message = (
            f"Binding '{binding.id}' conflicts with {[b.id for b in conflicts_tuple]}"
        )
        super().__init__(message)
        self.binding = binding
        self.conflicts = conflicts_tuple


class KeymapRegistry:
    """Owns action references and binding metadata."""

    def __init__(self, *, logger_name: str | None = None) -> None:
        self._actions: Dict[str, ActionRef] = {}
        self._bindings: Dict[str, Binding] = {}
        self._mode_index: Dict[str, Dict[str, set[str]]] = {}
        self._logger_name = logger_name
        self._revision = 0

    def revision(self) -> int:
        return self._revision

    def get_action(self, action_id: str) -> ActionRef:
        try:
            return self._actions[action_id]
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise KeyError(f"Action '{action_id}' is not registered") from exc

    def get_binding(self, binding_id: str) -> Binding:
        try:
            return self._bindings[binding_id]
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise KeyError(f"Binding '{binding_id}' is not registered") from exc

    def register_action(self, action: ActionRef, *, replace: bool = False) -> ActionRef:
        with span(
            "keymaps::register_action",
            logger_name=self._logger_name,
            component="keymaps",
            metadata={"action_id": action.id},
        ):
            if not replace and action.id in self._actions:
                raise ValueError(f"Action '{action.id}' already registered")
            self._actions[action.id] = action
            return action

    def register_binding(self, binding: Binding, *, replace: bool = False) -> Binding:
        with span(
            "keymaps::register_binding",
            logger_name=self._logger_name,
            component="keymaps",
            metadata={"binding_id": binding.id, "mode": binding.mode},
        ) as handle:
            if binding.action_id not in self._actions:
                handle.add_metadata("missing_action", binding.action_id)
                raise KeyError(
                    f"Binding '{binding.id}' references unknown action '{binding.action_id}'"
                )

            conflicts = self.detect_conflicts(binding)
            if conflicts and not replace:
                handle.add_metadata(
                    "conflicts", ",".join(conflict.id for conflict in conflicts)
                )
                raise KeymapConflictError(binding, conflicts)

            if replace:
                for conflict in conflicts:
                    self._remove_binding(conflict)
                    self._bindings.pop(conflict.id, None)
                existing = self._bindings.get(binding.id)
                if existing:
                    self._remove_binding(existing)
                    self._bindings.pop(existing.id, None)
            elif binding.id in self._bindings:
                raise ValueError(f"Binding id '{binding.id}' already registered")

            self._bindings[binding.id] = binding
            self._index_binding(binding)
            self._touch_bindings()
            return binding

    def unregister_binding(self, binding_id: str) -> Optional[Binding]:
        with span(
            "keymaps::unregister_binding",
            logger_name=self._logger_name,
            component="keymaps",
            metadata={"binding_id": binding_id},
        ):
            binding = self._bindings.pop(binding_id, None)
            if not binding:
                return None
            self._remove_binding(binding)
            self._touch_bindings()
            return binding

    def update_binding(self, binding_id: str, **changes: object) -> Binding:
        with span(
            "keymaps::update_binding",
            logger_name=self._logger_name,
            component="keymaps",
            metadata={"binding_id": binding_id},
        ) as handle:
            if binding_id not in self._bindings:
                handle.fail("missing_binding")
                raise KeyError(f"Binding '{binding_id}' not found")

            current = self._bindings[binding_id]
            updated = replace(current, **changes)
            if updated.action_id not in self._actions:
                handle.add_metadata("missing_action", updated.action_id)
                raise KeyError(
                    f"Binding '{binding_id}' references unknown action '{updated.action_id}'"
                )

            self._remove_binding(current)
            conflicts = self.detect_conflicts(updated)
            if conflicts:
                self._index_binding(current)
                handle.add_metadata(
                    "conflicts", ",".join(conflict.id for conflict in conflicts)
                )
                raise KeymapConflictError(updated, conflicts)

            self._bindings[binding_id] = updated
            self._index_binding(updated)
            self._touch_bindings()
            return updated

    def iter_bindings(self, mode: Optional[str] = None) -> Iterator[Binding]:
        if mode is None:
            yield from self._bindings.values()
            return
        for bucket in self._mode_index.get(mode, {}).values():
            for binding_id in bucket:
                yield self._bindings[binding_id]

    def override_sequence_timeouts(
        self,
        *,
        timeout_ms: int,
        mode: Optional[str] = None,
        binding_ids: Optional[Iterable[str]] = None,
    ) -> None:
        if timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")

        if binding_ids is not None:
            targets = [self.get_binding(binding_id) for binding_id in binding_ids]
        else:
            targets = list(self.iter_bindings(mode))

        if not targets:
            return

        for binding in targets:
            updated_sequence = KeySequence(
                binding.sequence.strokes, timeout_ms=timeout_ms
            )
            updated = replace(binding, sequence=updated_sequence)
            self._update_binding_in_place(binding, updated)

        self._touch_bindings()

    def stats(self) -> RegistryStats:
        return RegistryStats(
            action_count=len(self._actions),
            binding_count=len(self._bindings),
            modes=tuple(sorted(self._mode_index)),
        )

    def detect_conflicts(
        self, binding: Binding, *, ignore: Sequence[str] | None = None
    ) -> list[Binding]:
        ignored = set(ignore or ())
        conflicts: list[Binding] = []
        for match_id in self._mode_index.get(binding.mode, {}).get(
            binding.key_signature, set()
        ):
            if match_id in ignored:
                continue
            existing = self._bindings[match_id]
            if _contexts_overlap(binding, existing):
                conflicts.append(existing)
        return conflicts

    def _index_binding(self, binding: Binding) -> None:
        by_signature = self._mode_index.setdefault(binding.mode, {})
        bucket = by_signature.setdefault(binding.key_signature, set())
        bucket.add(binding.id)

    def _remove_binding(self, binding: Binding) -> None:
        mode_bucket = self._mode_index.get(binding.mode)
        if not mode_bucket:
            return
        signatures = mode_bucket.get(binding.key_signature)
        if not signatures:
            return
        signatures.discard(binding.id)
        if not signatures:
            mode_bucket.pop(binding.key_signature, None)
        if not mode_bucket:
            self._mode_index.pop(binding.mode, None)

    def _touch_bindings(self) -> None:
        self._revision += 1

    def _update_binding_in_place(self, current: Binding, updated: Binding) -> None:
        self._remove_binding(current)
        self._bindings[current.id] = updated
        self._index_binding(updated)


def _contexts_overlap(left: Binding, right: Binding) -> bool:
    left_map = left.when_map
    right_map = right.when_map

    if not left.when and not right.when:
        return True

    for flag, expected in left_map.items():
        if flag in right_map and right_map[flag] != expected:
            return False
    for flag, expected in right_map.items():
        if flag in left_map and left_map[flag] != expected:
            return False

    if not left.when or not right.when:
        return False

    return left_map == right_map


__all__ = [
    "KeymapRegistry",
    "KeymapConflictError",
    "RegistryStats",
]
