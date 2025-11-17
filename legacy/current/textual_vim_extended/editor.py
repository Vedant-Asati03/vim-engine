from __future__ import annotations

from collections import defaultdict
from typing import Callable, Dict

from textual.events import Key
from textual.widgets import TextArea

from .config import VimMode
from .core.actions import EditorActions
from .core.mode_handlers import (
    CommandModeHandler,
    InsertModeHandler,
    ModeHandler,
    NormalModeHandler,
    VisualBlockModeHandler,
    VisualLineModeHandler,
    VisualModeHandler,
)
from .custom_css import ThemeManager
from .modes.base_mode import ModeState
from .utils.cursor_movement import CursorMovementService
from .utils.cut_paste import ClipboardService
from .utils.logger import get_logger, log_kv
from .utils.macros import MacroRecorder


class VimEditor(TextArea):
    """Textual TextArea with Vim-inspired key handling using composition."""

    read_only: bool = True
    mode: VimMode = VimMode.NORMAL

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.clipboard: str = ""
        self.command_history: dict[str, list[int]] = defaultdict(list)
        self._entered_commands: list[str] = []
        self._history_index: int | None = None
        self._next_key_handler: Callable[[Key], None] | None = None
        self.logger = get_logger("textual_vim_extended.editor")

        # Services
        self.theme_manager = ThemeManager(self)
        self.mode_state = ModeState(self)
        self.clipboard_service = ClipboardService(self)
        self.cursor_service = CursorMovementService(self)
        self.macro_recorder = MacroRecorder(self)

        self.actions = EditorActions(self)
        self._mode_handlers: Dict[VimMode, ModeHandler] = {}
        self._configure_mode_handlers()
        self.logger.debug("VimEditor initialized")

    async def on_mount(self) -> None:
        self.theme_manager.apply()
        self.logger.info("Editor mounted")

    async def on_key(self, event: Key) -> None:
        self.handle_mode_switch(event)
        log_kv(self.logger, "debug", "Key event", key=event.key, mode=self.mode.value)
        row, col = self.cursor_location
        show_selected = (
            f"Selected({len(self.selected_text)}) " if self.selected_text else ""
        )
        self.border_title = f"{show_selected}[ {event.key} ][{row + 1}:{col + 1}]"

    def _configure_mode_handlers(self) -> None:
        self._mode_handlers = {
            VimMode.NORMAL: NormalModeHandler(self, self.actions),
            VimMode.INSERT: InsertModeHandler(self, self.actions),
            VimMode.VISUAL: VisualModeHandler(self, self.actions),
            VimMode.VISUAL_LINE: VisualLineModeHandler(self, self.actions),
            VimMode.VISUAL_BLOCK: VisualBlockModeHandler(self, self.actions),
            VimMode.COMMAND: CommandModeHandler(self, self.actions),
        }
        self.logger.debug("Mode handlers configured")

    # --- Mode wrapper methods -------------------------------------------------
    def enter_normal_mode(self) -> bool:
        return self._mode_handlers[VimMode.NORMAL].enter()

    def enter_insert_mode(self, **kwargs) -> bool:
        handler = self._mode_handlers[VimMode.INSERT]
        return handler.enter(**kwargs)  # type: ignore[arg-type]

    def enter_visual_mode(self) -> None:
        self._mode_handlers[VimMode.VISUAL].enter()

    def enter_visual_line_mode(self, **kwargs) -> None:
        handler = self._mode_handlers[VimMode.VISUAL_LINE]
        handler.enter(**kwargs)  # type: ignore[arg-type]

    def enter_visual_block_mode(self, **kwargs) -> None:
        handler = self._mode_handlers[VimMode.VISUAL_BLOCK]
        handler.enter(**kwargs)  # type: ignore[arg-type]

    def enter_command_mode(self) -> None:
        self._mode_handlers[VimMode.COMMAND].enter()

    # --- Editing helpers delegated to controllers/services --------------------
    def delete_at_cursor(self) -> None:
        self.actions.delete_at_cursor()

    def delete_before_cursor(self) -> None:
        self.actions.delete_before_cursor()

    def delete_line(self) -> None:
        self.actions.delete_line()

    def yank_line(self) -> None:
        self.actions.yank_line()

    def indent_selection(self) -> None:
        self.actions.indent_selection()

    def unindent_selection(self) -> None:
        self.actions.unindent_selection()

    def change_selection(self) -> None:
        self.actions.change_selection()

    def toggle_case_selection(self) -> None:
        self.actions.toggle_case_selection()

    def uppercase_selection(self) -> None:
        self.actions.uppercase_selection()

    def lowercase_selection(self) -> None:
        self.actions.lowercase_selection()

    def paste_over_selection(self) -> None:
        self.actions.paste_over_selection()

    def swap_selection_ends(self) -> None:
        self.actions.swap_selection_ends()

    def delete_block_selection(self) -> None:
        self.actions.delete_block_selection()

    def change_block_selection(self) -> None:
        self.actions.change_block_selection()

    def insert_block_selection(self) -> None:
        self.actions.insert_block_selection()

    def append_block_selection(self) -> None:
        self.actions.append_block_selection()

    def yank_block_selection(self) -> None:
        self.actions.yank_block_selection()

    def yank_selection(self) -> None:
        self.clipboard_service.yank_selection()

    def handle_completion(self) -> None:
        self.notify("Command completion is not implemented yet", severity="warning")

    def cycle_history(self, direction: int) -> None:
        if not self._entered_commands:
            return
        if self._history_index is None:
            self._history_index = len(self._entered_commands)
        self._history_index = max(
            0, min(len(self._entered_commands) - 1, self._history_index + direction)
        )
        buffer_value = ":" + self._entered_commands[self._history_index]
        command_handler = self._mode_handlers[VimMode.COMMAND]
        if isinstance(command_handler, CommandModeHandler):
            command_handler.set_buffer(buffer_value)

    # --- Misc helpers --------------------------------------------------------
    def reset_sequence(self) -> None:
        for handler in self._mode_handlers.values():
            reset = getattr(handler, "reset_sequence", None)
            if callable(reset):
                reset()

    def capture_next_key(self, handler: Callable[[Key], None]) -> None:
        self._next_key_handler = handler

    def register_command_history(self, command: str) -> None:
        if command:
            self._entered_commands.append(command)
            self._history_index = None

    def handle_mode_switch(self, event: Key) -> None:
        should_record = (
            self.macro_recorder.recording_macro
            and self.mode == VimMode.NORMAL
            and event.key != "q"
            and not self._next_key_handler
        )
        if should_record:
            self.macro_recorder.record_key(event.key)
            log_kv(self.logger, "debug", "Macro recording key", key=event.key)

        if self._next_key_handler:
            self._next_key_handler(event)
            self._next_key_handler = None
            event.prevent_default()
            return

        handler = self._mode_handlers.get(self.mode)
        if handler and handler.handle_key(event):
            log_kv(
                self.logger,
                "debug",
                "Mode handler processed key",
                key=event.key,
                mode=self.mode.value,
            )
            event.prevent_default()

    # --- Placeholder commands ------------------------------------------------
    def handle_semicolon(self) -> None:
        self.notify("Repeat search (;) not implemented", severity="warning")

    def handle_ampersand(self) -> None:
        self.notify("Repeat substitution (&) not implemented", severity="warning")

    def toggle_case_at_cursor(self) -> None:
        row, col = self.cursor_location
        if row >= len(self.lines) or col >= len(self.lines[row]):
            return
        line = self.lines[row]
        char = line[col]
        swapped = char.swapcase()
        self.delete((row, col), (row, col + 1))
        self.insert(swapped)

    def handle_backtick(self) -> None:
        self.notify("Mark navigation (`) not implemented", severity="warning")
