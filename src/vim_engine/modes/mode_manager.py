"""Mode manager coordinating Normal/Insert/etc pipelines."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Dict, Optional, Type

from vim_engine.runtime import telemetry

from vim_engine.keymaps import KeymapRegistry, KeymapResolver, load_default_keymaps

from .base_mode import KeyInput, Mode, ModeContext, ModeResult


@dataclass
class PendingTimeout:
    deadline: float
    timeout_ms: int
    generation: int


class ModeManager:
    """Owns active mode, handles transitions, and dispatches key events."""

    def __init__(
        self,
        context: ModeContext,
        *,
        keymap_registry: KeymapRegistry | None = None,
        keymap_resolver: KeymapResolver | None = None,
        load_defaults: bool = True,
    ) -> None:
        self.context = context
        self._modes: Dict[str, Mode] = {}
        self._active: Optional[str] = None
        self.logger = telemetry.get_logger("vim_engine.modes")
        self.keymap_registry = keymap_registry or KeymapRegistry(
            logger_name="vim_engine.keymaps"
        )
        if load_defaults and keymap_registry is None:
            load_default_keymaps(self.keymap_registry)
        self.keymap_resolver = keymap_resolver or KeymapResolver(
            self.keymap_registry, logger_name="vim_engine.keymaps"
        )
        self.context.extras.setdefault("keymap_registry", self.keymap_registry)
        self.context.extras.setdefault("keymap_resolver", self.keymap_resolver)
        self.context.extras.setdefault("keymap_flags", {})
        self.context.extras.setdefault("mode_manager", self)
        self._pending_timeouts: Dict[str, PendingTimeout] = {}
        self._timer_counter = 0

    @property
    def active_mode(self) -> Optional[Mode]:
        if self._active is None:
            return None
        return self._modes.get(self._active)

    def register_mode(
        self,
        mode_cls: Type[Mode],
        /,
        *mode_args: object,
        **mode_kwargs: object,
    ) -> Mode:
        mode = mode_cls(self.context, *mode_args, **mode_kwargs)
        if mode.name in self._modes:
            raise ValueError(f"Mode '{mode.name}' already registered")
        self._modes[mode.name] = mode
        if self._active is None:
            self._active = mode.name
            mode.on_enter(None)
        return mode

    def switch_mode(self, name: str) -> None:
        if name not in self._modes:
            raise KeyError(f"Unknown mode '{name}'")
        previous = self.active_mode
        if previous and previous.name == name:
            return
        if previous:
            self.cancel_timeout(previous.name)
            previous.on_exit(name)
        self._active = name
        self._modes[name].on_enter(previous.name if previous else None)
        self.cancel_timeout(name)
        telemetry.record_event("mode.switch", data={"mode": name})

    def handle_key(self, key: KeyInput) -> ModeResult:
        mode = self.active_mode
        if mode is None:
            raise RuntimeError("No active mode registered")
        with telemetry.span(
            name=f"mode::{mode.name}",
            component=True,
            metadata={"key": key.key, "mode": mode.name},
        ):
            result = mode.handle_key(key)
        return self._after_mode_result(mode, result)

    def _after_mode_result(self, mode: Mode, result: ModeResult) -> ModeResult:
        if result.timeout_ms:
            self.arm_timeout(mode.name, result.timeout_ms)
        else:
            self.cancel_timeout(mode.name)
        if result.switch_to:
            self.switch_mode(result.switch_to)
        return result

    def arm_timeout(self, mode_name: str, timeout_ms: int) -> None:
        self._timer_counter += 1
        deadline = time.monotonic() + (timeout_ms / 1000.0)
        self._pending_timeouts[mode_name] = PendingTimeout(
            deadline=deadline,
            timeout_ms=timeout_ms,
            generation=self._timer_counter,
        )

    def cancel_timeout(self, mode_name: str) -> None:
        self._pending_timeouts.pop(mode_name, None)

    def process_timeouts(self) -> Dict[str, ModeResult]:
        now = time.monotonic()
        expired = {
            mode_name: timer
            for mode_name, timer in self._pending_timeouts.items()
            if timer.deadline <= now
        }
        results: Dict[str, ModeResult] = {}
        for mode_name, timer in expired.items():
            results[mode_name] = self._trigger_timeout(mode_name, timer.generation)
        return results

    def force_timeout(self, mode_name: Optional[str] = None) -> Dict[str, ModeResult]:
        if mode_name is not None:
            timer = self._pending_timeouts.get(mode_name)
            if not timer:
                return {}
            return {mode_name: self._trigger_timeout(mode_name, timer.generation)}

        # force all
        current = list(self._pending_timeouts.items())
        results: Dict[str, ModeResult] = {}
        for name, timer in current:
            results[name] = self._trigger_timeout(name, timer.generation)
        return results

    def _trigger_timeout(self, mode_name: str, generation: int) -> ModeResult:
        timer = self._pending_timeouts.get(mode_name)
        if not timer or timer.generation != generation:
            return ModeResult(consumed=False, status="timeout")
        self._pending_timeouts.pop(mode_name, None)
        mode = self._modes.get(mode_name)
        if mode is None:
            return ModeResult(consumed=False, status="timeout")
        with telemetry.span(
            name=f"mode_timeout::{mode_name}",
            component=True,
            metadata={"mode": mode_name},
        ):
            result = mode.handle_timeout()
        return self._after_mode_result(mode, result)
