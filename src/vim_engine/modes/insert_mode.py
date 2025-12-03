"""Insert mode scaffolding."""

from __future__ import annotations

from typing import List

from vim_engine.runtime import telemetry

from vim_engine.keymaps import ResolutionMatch

from .base_mode import KeyInput, Mode, ModeContext, ModeResult
from .keymap_helpers import key_to_token, keymap_flag_context, require_keymap_resolver


class InsertMode(Mode):
    name = "insert"

    def __init__(
        self,
        context: ModeContext,
        *,
        default_pending_timeout_ms: int = 1000,
    ) -> None:
        super().__init__(context)
        self.logger = telemetry.get_logger("vim_engine.modes.insert")
        self._resolver = require_keymap_resolver(context)
        self._flags = keymap_flag_context(context)
        self._pending: List[str] = []
        self._default_timeout_ms = default_pending_timeout_ms

    def on_exit(self, next_mode: str | None) -> None:
        del next_mode
        self._pending.clear()

    def handle_key(self, key: KeyInput) -> ModeResult:
        token = key_to_token(key)
        self._pending.append(token)
        result = self._resolver.resolve(
            self.name, tuple(self._pending), context=self._flags
        )

        if result.status == "match" and result.match:
            self._pending.clear()
            return self._execute_match(result.match)

        if result.status == "pending":
            timeout_ms = result.timeout_ms or self._default_timeout_ms
            return ModeResult(
                consumed=True,
                status="pending",
                message="awaiting_sequence",
                timeout_ms=timeout_ms,
            )

        self._pending.clear()

        if key.key in {"ESC", "<Esc>"}:
            return ModeResult(consumed=True, switch_to="normal", message="exit_insert")

        # Placeholder: future implementation will insert text into buffer.
        return ModeResult(consumed=False)

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

    def handle_timeout(self) -> ModeResult:
        if not self._pending:
            return ModeResult(consumed=False, status="timeout")

        tokens = tuple(self._pending)
        self._pending.clear()
        result = self._resolver.resolve(self.name, tokens, context=self._flags)
        if result.status == "match" and result.match:
            return self._execute_match(result.match)
        return ModeResult(consumed=False, status="timeout", message="pending_timeout")
