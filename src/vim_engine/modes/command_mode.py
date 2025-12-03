"""Command-line mode with inline editing and keymap integration."""

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


class CommandMode(Mode):
    name = "command"

    def __init__(
        self,
        context: ModeContext,
        *,
        default_pending_timeout_ms: int = 1000,
    ) -> None:
        super().__init__(context)
        self.logger = telemetry.get_logger("vim_engine.modes.command")
        self._resolver = require_keymap_resolver(context)
        self._flags = keymap_flag_context(context)
        self._pending: List[str] = []
        self._typed: List[str] = []
        self._default_timeout_ms = default_pending_timeout_ms

    def on_enter(self, previous: str | None) -> None:
        del previous
        self._typed.clear()
        update_flag(self.context, "command_active", True)
        self.context.bus.emit("command.start", None)
        self._sync_command_state()

    def on_exit(self, next_mode: str | None) -> None:
        del next_mode
        update_flag(self.context, "command_active", False)
        self._pending.clear()
        self.context.bus.emit("command.end", self.current_command)
        self._typed.clear()
        self._sync_command_state()

    @property
    def current_command(self) -> str:
        return "".join(self._typed)

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
        return self._handle_text_input(key)

    def _handle_text_input(self, key: KeyInput) -> ModeResult:
        if key.key in {"ESC", "<Esc>"}:
            self._typed.clear()
            self._sync_command_state()
            return ModeResult(
                consumed=True, switch_to="normal", message="command_cancel"
            )

        if key.key in {"ENTER", "RETURN"}:
            command = self.current_command
            self.context.bus.emit("command.submit", command)
            self._typed.clear()
            self._sync_command_state()
            return ModeResult(
                consumed=True,
                switch_to="normal",
                status="command_submit",
                message=command,
            )

        if key.key == "BACKSPACE" and self._typed:
            self._typed.pop()
            self._sync_command_state()
            return ModeResult(consumed=True, status="editing")

        if key.text:
            self._typed.append(key.text)
            self._sync_command_state()
            return ModeResult(consumed=True, status="editing")

        return ModeResult(consumed=False, status="miss", message="unhandled")

    def handle_timeout(self) -> ModeResult:
        if not self._pending:
            return ModeResult(consumed=False, status="timeout")

        tokens = tuple(self._pending)
        self._pending.clear()
        result = self._resolver.resolve(self.name, tokens, context=self._flags)
        if result.status == "match" and result.match:
            return self._execute_match(result.match)
        return ModeResult(consumed=False, status="timeout", message="pending_timeout")

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

    def _command_state(self) -> MutableMapping[str, object]:
        return cast(
            MutableMapping[str, object],
            self.context.extras.setdefault("command_state", {}),
        )

    def _sync_command_state(self) -> None:
        state = self._command_state()
        state["text"] = self.current_command
