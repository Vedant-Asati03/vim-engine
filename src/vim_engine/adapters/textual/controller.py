"""Minimal Textual adapter that wires ModeManager events into UI callbacks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Optional

from vim_engine.buffer import BufferMirror
from vim_engine.modes import KeyInput, ModeResult
from vim_engine.modes.mode_manager import ModeManager


def _noop(*_args, **_kwargs) -> None:  # pragma: no cover - default hook
    return None


@dataclass(slots=True)
class TextualUIHooks:
    """Callbacks invoked by the adapter to update Textual widgets."""

    update_buffer: Callable[[BufferMirror], None]
    update_status: Callable[[str], None] = _noop
    show_command: Callable[[str], None] = _noop
    handle_event: Callable[[str, object | None], None] = _noop
    # Optional realtime log callback a host may use to surface debug lines
    log: Callable[[str], None] = _noop


class TextualVimAdapter:
    """Bridges ModeManager + bus events to a Textual-friendly surface."""

    def __init__(self, manager: ModeManager, hooks: TextualUIHooks) -> None:
        self.manager = manager
        self.hooks = hooks
        self._subscribe_events()
        self._refresh_buffer()
        self._refresh_command_line()

    def handle_textual_key(
        self,
        key: str,
        *,
        text: Optional[str] = None,
        modifiers: Iterable[str] = (),
    ) -> ModeResult:
        """Translate a Textual key event into a KeyInput and dispatch it."""

        normalized_modifiers = tuple(str(mod).upper() for mod in modifiers)
        self._log_state(
            "key ->",
            key=key,
            text=text,
            mods=normalized_modifiers,
        )
        result = self.manager.handle_key(
            KeyInput(key=key, text=text, modifiers=normalized_modifiers)
        )
        self._after_mode_result(result)
        self._log_state(
            "result <-",
            consumed=result.consumed,
            status=result.status,
            message=result.message,
            switch_to=result.switch_to,
            timeout_ms=result.timeout_ms,
        )
        return result

    def process_timeouts(self) -> Dict[str, ModeResult]:
        """Forward expired timers and surface results to the UI."""

        results = self.manager.process_timeouts()
        for mode_name, outcome in results.items():
            label = f"{mode_name}:{outcome.status}"
            self.hooks.update_status(label)
            self._log_state(
                "timeout ->",
                source_mode=mode_name,
                status=outcome.status,
            )
        if results:
            self._refresh_buffer()
        return results

    def _after_mode_result(self, result: ModeResult) -> None:
        status = result.message or result.status
        if status:
            self.hooks.update_status(status)
        self._refresh_buffer()
        self._refresh_command_line()

    def _subscribe_events(self) -> None:
        bus = self.manager.context.bus
        for event in (
            "visual.selection",
            "visual.yank",
            "visual.delete",
            "command.start",
            "command.end",
            "command.submit",
            "command.write",
            "command.quit",
            "command.edit",
            "command.echo",
        ):
            bus.subscribe(
                event, lambda payload, name=event: self._handle_event(name, payload)
            )

    def _handle_event(self, name: str, payload: object | None) -> None:
        # Surface the event to the host UI and also emit a realtime log line.
        self._log_state("event ->", event=name, payload=payload)
        self.hooks.handle_event(name, payload)
        if name.startswith("command"):
            if name == "command.submit" and isinstance(payload, str):
                self.hooks.update_status(f"command::{payload}")
            self._refresh_command_line()
        if name.startswith("visual"):
            self._refresh_buffer()

    def _refresh_buffer(self) -> None:
        mirror = self.manager.context.buffer.mirror()
        self.hooks.update_buffer(mirror)

    def _refresh_command_line(self) -> None:
        state = self.manager.context.extras.get("command_state")
        if isinstance(state, dict):
            text = str(state.get("text", ""))
        else:
            text = ""
        self.hooks.show_command(text)

    def _log_state(self, prefix: str, **fields: object) -> None:
        try:
            snapshot = self._state_metadata()
            snapshot.update({k: v for k, v in fields.items() if v is not None})
            parts = [prefix]
            for key, value in snapshot.items():
                parts.append(f"{key}={value!r}")
            line = " ".join(parts)
            self.hooks.log(line)
        except Exception:
            pass

    def _state_metadata(self) -> Dict[str, object]:
        buffer = self.manager.context.buffer
        active_mode = self.manager.active_mode
        mode = active_mode.name if active_mode else "?"
        command_state = self.manager.context.extras.get("command_state")
        command_text = ""
        if isinstance(command_state, dict):
            command_text = str(command_state.get("text", ""))
        pending = bool(getattr(self.manager, "_pending_timeouts", None))
        return {
            "mode": mode,
            "cursor": buffer.state.cursor,
            "selection": buffer.state.selection,
            "command": command_text,
            "pending_timeout": pending,
            "buffer": buffer.name,
            "buffer_version": buffer.document.version,
        }


__all__ = ["TextualVimAdapter", "TextualUIHooks"]
