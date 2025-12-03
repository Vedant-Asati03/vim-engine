"""Visual mode implementation built on the keymap resolver and operator pipeline."""

from __future__ import annotations

from typing import List, MutableMapping, cast

from vim_engine.runtime import telemetry

from vim_engine.keymaps import ResolutionMatch

from .base_mode import KeyInput, Mode, ModeContext, ModeResult
from .keymap_helpers import (
    key_to_token,
    keymap_flag_context,
    require_keymap_resolver,
    update_flag,
)
from .operator_pipeline import OperatorPipeline


class VisualMode(Mode):
    name = "visual"

    def __init__(
        self,
        context: ModeContext,
        *,
        default_pending_timeout_ms: int = 1000,
    ) -> None:
        super().__init__(context)
        self.logger = telemetry.get_logger("vim_engine.modes.visual")
        self._resolver = require_keymap_resolver(context)
        self._flags = keymap_flag_context(context)
        self._pending: List[str] = []
        self._default_timeout_ms = default_pending_timeout_ms
        self._operator_pipeline = OperatorPipeline(
            buffer=context.buffer, registers=context.registers
        )
        self._operator_tokens: List[str] = []

    def on_enter(self, previous: str | None) -> None:
        del previous
        update_flag(self.context, "visual_active", True)
        self._pending.clear()
        self._operator_tokens.clear()
        anchor = self.context.buffer.state.cursor
        state = self._visual_state()
        state["anchor"] = anchor
        self.context.buffer.state.set_selection(anchor, anchor)

    def on_exit(self, next_mode: str | None) -> None:
        del next_mode
        update_flag(self.context, "visual_active", False)
        self._pending.clear()
        self._operator_tokens.clear()
        visual_state = self.context.extras.get("visual_state")
        if isinstance(visual_state, dict):
            visual_state.pop("anchor", None)
        self.context.buffer.state.clear_selection()

    def handle_key(self, key: KeyInput) -> ModeResult:
        token = key_to_token(key)
        self._pending.append(token)
        result = self._resolver.resolve(
            self.name, tuple(self._pending), context=self._flags
        )

        if result.status == "match" and result.match:
            self._pending.clear()
            self._operator_tokens.clear()
            return self._execute_match(result.match)

        if result.status == "pending":
            timeout_ms = result.timeout_ms or self._default_timeout_ms
            return ModeResult(
                consumed=True,
                status="pending",
                message="awaiting_sequence",
                timeout_ms=timeout_ms,
            )

        # Resolver miss: fall back to operator pipeline or exit shortcuts.
        self._operator_tokens.append(token)
        plan = self._operator_pipeline.parse(tuple(self._operator_tokens))
        if plan:
            context = self._operator_pipeline.build_context(plan)
            self.context.bus.emit("operator.plan", context)
            self._pending.clear()
            self._operator_tokens.clear()
            return ModeResult(consumed=True, status="operator", message="operator_plan")

        self._pending.clear()
        if key.key in {"ESC", "<Esc>"}:
            self._operator_tokens.clear()
            return ModeResult(consumed=True, switch_to="normal", message="exit_visual")

        timeout_ms = self._default_timeout_ms
        return ModeResult(
            consumed=True,
            status="pending",
            message="operator_pending",
            timeout_ms=timeout_ms,
        )

    def handle_timeout(self) -> ModeResult:
        if self._pending:
            tokens = tuple(self._pending)
            self._pending.clear()
            self._operator_tokens.clear()
            result = self._resolver.resolve(self.name, tokens, context=self._flags)
            if result.status == "match" and result.match:
                return self._execute_match(result.match)
            return ModeResult(
                consumed=False, status="timeout", message="pending_timeout"
            )

        if self._operator_tokens:
            self._operator_tokens.clear()
            return ModeResult(
                consumed=False, status="timeout", message="operator_timeout"
            )

        return ModeResult(consumed=False, status="timeout")

    def _execute_match(self, match: ResolutionMatch) -> ModeResult:
        with telemetry.span(
            "keymaps::execute",
            component="keymaps",
            metadata={"binding_id": match.binding.id, "action": match.action.id},
        ):
            outcome = match.action(self.context, match)

        if isinstance(outcome, ModeResult):
            return outcome
        return ModeResult(consumed=True)

    def _visual_state(self) -> MutableMapping[str, object]:
        return cast(
            MutableMapping[str, object],
            self.context.extras.setdefault("visual_state", {}),
        )
