"""Executable Textual app that hosts the Vim engine."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Any, Optional, Sequence, Tuple

try:  # pragma: no cover - imported only when demo is run
    from textual import events
    from textual.app import App, ComposeResult
    from textual.containers import Vertical
    from textual.widgets import Footer, Header, Static
except ModuleNotFoundError as exc:  # pragma: no cover - friendly error for missing dep
    raise RuntimeError(
        "Install the 'textual' package to use vim_engine.adapters.textual.app"
    ) from exc

from vim_engine.buffer import Buffer, BufferMirror
from vim_engine.keymaps import KeymapRegistry, KeymapResolver, load_default_keymaps
from vim_engine.modes import (
    CommandMode,
    InsertMode,
    ModeBus,
    ModeContext,
    NormalMode,
    VisualMode,
)
from vim_engine.modes.mode_manager import ModeManager

from .controller import TextualUIHooks, TextualVimAdapter
from vim_engine.logging import NetworkLogStreamer


def create_default_manager() -> ModeManager:
    """Build a ModeManager with the standard mode set + default keymaps."""

    registry = KeymapRegistry()
    load_default_keymaps(registry)
    resolver = KeymapResolver(registry)
    buffer = Buffer()
    context = ModeContext(
        buffer=buffer,
        registers=buffer.registers,
        bus=ModeBus(),
        extras={},
    )
    manager = ModeManager(
        context,
        keymap_registry=registry,
        keymap_resolver=resolver,
        load_defaults=False,
    )
    manager.register_mode(NormalMode)
    manager.register_mode(InsertMode)
    manager.register_mode(VisualMode)
    manager.register_mode(CommandMode)
    return manager


@dataclass
class UIState:
    buffer_text: str = ""
    status_text: str = ""
    command_text: str = ""


class VimEngineApp(App[None]):
    """Minimal Textual UI embedding the Vim engine."""

    CSS = """
	Screen {
		layout: vertical;
	}

	#buffer-view {
		height: 1fr;
		border: round $accent;
		padding: 1 1;
		content-align: left top;
		overflow: auto;
	}

	#status-line {
		height: 1;
		background: $surface-darken-1;
		padding: 0 1;
	}

	#command-line {
		height: 1;
		background: $surface-darken-2;
		padding: 0 1;
	}
	"""

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(
        self,
        *,
        log_host: str = "127.0.0.1",
        log_port: int | None = 8765,
    ) -> None:
        super().__init__()
        self._state = UIState()
        self.manager: ModeManager | None = None
        self.adapter: TextualVimAdapter | None = None
        self._buffer_widget: Static | None = None
        self._status_widget: Static | None = None
        self._command_widget: Static | None = None
        self._log_streamer: NetworkLogStreamer | None = None
        self._log_host = log_host
        self._requested_log_port = log_port

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="buffer-area"):
            self._buffer_widget = Static("", id="buffer-view")
            yield self._buffer_widget
        self._status_widget = Static("", id="status-line")
        self._command_widget = Static("", id="command-line")
        yield self._status_widget
        yield self._command_widget
        yield Footer()

    async def on_mount(self) -> None:
        self.manager = create_default_manager()
        hooks = TextualUIHooks(
            update_buffer=self._update_buffer,
            update_status=self._update_status,
            show_command=self._show_command,
            handle_event=self._handle_event,
            log=self._log_line,
        )
        self.adapter = TextualVimAdapter(self.manager, hooks)
        await self._maybe_start_log_stream()
        self.set_interval(0.1, self._process_timeouts)

    async def on_unmount(self) -> None:
        if self._log_streamer:
            await self._log_streamer.stop()
            self._log_streamer = None

    def _process_timeouts(self) -> None:
        if self.adapter:
            self.adapter.process_timeouts()

    async def on_key(self, event: events.Key) -> None:
        if not self.adapter:
            return
        normalized = self._normalize_key(event)
        if normalized is None:
            return
        key, text, modifiers = normalized
        self.adapter.handle_textual_key(key, text=text, modifiers=modifiers)
        event.stop()

    def _update_buffer(self, mirror: BufferMirror) -> None:
        self._state.buffer_text = mirror.text
        if self._buffer_widget:
            self._buffer_widget.update(self._state.buffer_text)

    def _update_status(self, status: str) -> None:
        self._state.status_text = status
        if self._status_widget:
            self._status_widget.update(status)

    def _show_command(self, command: str) -> None:
        self._state.command_text = command
        if self._command_widget:
            self._command_widget.update(f":{command}" if command else "")

    def _handle_event(self, name: str, payload: Any | None) -> None:
        if name.startswith("visual"):  # explicit buffer refresh already handled
            self._update_status(name)
        elif name.startswith("command") and isinstance(payload, str):
            self._update_status(f"{name}:{payload}")

    def _log_line(self, line: str) -> None:
        if self._log_streamer:
            self._log_streamer.log(line)

    async def _maybe_start_log_stream(self) -> None:
        if self._requested_log_port is None:
            return
        self._log_streamer = NetworkLogStreamer(
            self._log_host, self._requested_log_port
        )
        await self._log_streamer.start()
        bound = self._log_streamer.port
        self._update_status(f"Log stream @ {self._log_host}:{bound}")
        self._log_line("log stream ready")

    @staticmethod
    def _normalize_key(
        event: events.Key,
    ) -> Optional[Tuple[str, Optional[str], Tuple[str, ...]]]:
        modifiers = []
        ctrl = bool(getattr(event, "ctrl", False))
        alt = bool(getattr(event, "alt", False) or getattr(event, "meta", False))
        shift = bool(getattr(event, "shift", False))
        if ctrl:
            modifiers.append("CTRL")
        if alt:
            modifiers.append("ALT")
        if shift and not (event.character and len(event.character) == 1):
            modifiers.append("SHIFT")
        key = event.key
        if key in {"ctrl+c", "ctrl+q"}:
            return None
        if key == "escape":
            return ("ESC", None, tuple(modifiers))
        if key in {"enter", "return"}:
            return ("ENTER", None, tuple(modifiers))
        if event.character:
            return (event.character, event.character, tuple(modifiers))
        return (key.upper(), None, tuple(modifiers))


def _env_int(key: str, fallback: int) -> int:
    value = os.environ.get(key)
    if value is None:
        return fallback
    try:
        return int(value)
    except ValueError:
        return fallback


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Vim engine Textual demo.")
    parser.add_argument(
        "--log-host",
        default=os.environ.get("VIM_ENGINE_LOG_HOST", "127.0.0.1"),
        help="Host interface for the TCP log stream (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--log-port",
        type=int,
        default=_env_int("VIM_ENGINE_LOG_PORT", 8765),
        help="TCP port for the log stream (0 for ephemeral, default: 8765)",
    )
    parser.add_argument(
        "--no-log-server",
        action="store_true",
        help="Disable the external log server",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = _parse_args(argv)
    log_port: int | None = None if args.no_log_server else args.log_port
    app = VimEngineApp(log_host=args.log_host, log_port=log_port)
    app.run()


if __name__ == "__main__":  # pragma: no cover - manual demo
    main()
