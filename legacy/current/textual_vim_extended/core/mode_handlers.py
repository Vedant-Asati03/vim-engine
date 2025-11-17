"""Mode handlers and dispatcher logic for the Vim editor."""

from __future__ import annotations

from typing import Callable, Dict

from textual.events import Key

from textual_vim_extended.config import VimMode
from textual_vim_extended.core.actions import EditorActions
from textual_vim_extended.core.commanding import CommandBinding
from textual_vim_extended.modes.base_mode import ModeState
from textual_vim_extended.utils.cursor_movement import CursorMovementService
from textual_vim_extended.utils.cut_paste import ClipboardService


class ModeHandler:
    """Base class for mode-specific key handling."""

    mode: VimMode | None = None

    def __init__(self, editor, actions: EditorActions) -> None:
        if self.mode is None:
            raise ValueError("mode handlers must define a VimMode")
        self.editor = editor
        self.actions = actions
        self.mode_state: ModeState = editor.mode_state
        self.cursor: CursorMovementService = editor.cursor_service
        self.clipboard: ClipboardService = editor.clipboard_service

    def activate(self) -> None:
        self.mode_state.apply(self.mode)  # type: ignore[arg-type]
        self.editor.refresh()

    def handle_key(self, event: Key) -> bool:
        raise NotImplementedError

    def _repeat(self, func: Callable[[], None], repeat: int) -> None:
        for _ in range(max(repeat, 1)):
            func()


class SequenceModeHandler(ModeHandler):
    """Implements Vim-style multi-key sequences and repeat prefixes."""

    sequence_limit = 10

    def __init__(
        self,
        editor,
        actions: EditorActions,
        bindings: Dict[str, CommandBinding],
        honor_repeats: bool = True,
    ) -> None:
        super().__init__(editor, actions)
        self._bindings = bindings
        self._honor_repeats = honor_repeats
        self._sequence: str = ""

    def handle_key(self, event: Key) -> bool:
        self._sequence += event.key
        command, repeat = self._split_sequence()
        repeat = repeat if self._honor_repeats else 1
        binding = self._bindings.get(command)
        if binding:
            binding.run(repeat)
            self.after_command(command, repeat)
            self._sequence = ""
            return True
        if len(self._sequence) > self.sequence_limit:
            self._sequence = ""
        return False

    def after_command(self, command: str, repeat: int) -> None:  # noqa: D401
        """Hook for subclasses to record command metadata."""

    def reset_sequence(self) -> None:
        self._sequence = ""

    def _split_sequence(self) -> tuple[str, int]:
        sequence = self._sequence
        repeat = 0
        command = sequence
        for idx, char in enumerate(sequence):
            if char.isdigit():
                repeat = repeat * 10 + int(char)
                continue
            command = sequence[idx:]
            break
        else:
            command = sequence
        if repeat == 0:
            repeat = 1
        return command, repeat


class NormalModeHandler(SequenceModeHandler):
    mode = VimMode.NORMAL

    def __init__(self, editor, actions: EditorActions) -> None:
        bindings = self._build_bindings(editor, actions)
        super().__init__(editor, actions, bindings, honor_repeats=False)

    def _build_bindings(
        self, editor, actions: EditorActions
    ) -> Dict[str, CommandBinding]:
        cursor = editor.cursor_service
        clipboard = editor.clipboard_service

        def move_cursor(target: Callable[[], None]) -> CommandBinding:
            return CommandBinding(lambda repeat: self._repeat(target, repeat))

        return {
            "backspace": move_cursor(editor.action_cursor_left),
            "v": CommandBinding(lambda repeat: editor.enter_visual_mode()),
            "V": CommandBinding(
                lambda repeat: editor.enter_visual_line_mode(linewise_visual_mode=True)
            ),
            "ctrl+v": CommandBinding(
                lambda repeat: editor.enter_visual_block_mode(block_visual_mode=True)
            ),
            "i": CommandBinding(
                lambda repeat: editor.enter_insert_mode(at_cursor=True)
            ),
            "I": CommandBinding(
                lambda repeat: editor.enter_insert_mode(at_line_start=True)
            ),
            "a": CommandBinding(
                lambda repeat: editor.enter_insert_mode(after_cursor=True)
            ),
            "A": CommandBinding(
                lambda repeat: editor.enter_insert_mode(after_line=True)
            ),
            "o": CommandBinding(
                lambda repeat: editor.enter_insert_mode(new_line_below=True)
            ),
            "O": CommandBinding(
                lambda repeat: editor.enter_insert_mode(new_line_above=True)
            ),
            "h": move_cursor(editor.action_cursor_left),
            "l": move_cursor(editor.action_cursor_right),
            "k": move_cursor(editor.action_cursor_up),
            "j": move_cursor(editor.action_cursor_down),
            "w": move_cursor(editor.action_cursor_word_right),
            "b": move_cursor(editor.action_cursor_word_left),
            "ge": CommandBinding(lambda repeat: cursor.jump_backwards_to_end_of_word()),
            "gg": CommandBinding(lambda repeat: editor.move_cursor((0, 0))),
            "G": CommandBinding(
                lambda repeat: editor.move_cursor((len(editor.text.splitlines()), 0))
            ),
            "0": CommandBinding(lambda repeat: editor.action_cursor_line_start()),
            "$": CommandBinding(lambda repeat: editor.action_cursor_line_end()),
            "u": CommandBinding(lambda repeat: editor.action_undo()),
            "ctrl+r": CommandBinding(lambda repeat: editor.action_redo()),
            "H": CommandBinding(lambda repeat: cursor.move_to_top_of_screen()),
            "L": CommandBinding(lambda repeat: cursor.move_to_bot_of_screen()),
            "M": CommandBinding(lambda repeat: cursor.move_to_mid_of_screen()),
            "delete": CommandBinding(lambda repeat: actions.delete_at_cursor()),
            "x": CommandBinding(lambda repeat: actions.delete_at_cursor()),
            "X": CommandBinding(lambda repeat: actions.delete_before_cursor()),
            "dd": CommandBinding(lambda repeat: actions.delete_line()),
            "D": CommandBinding(lambda repeat: editor.action_delete_to_end_of_line()),
            "yy": CommandBinding(lambda repeat: actions.yank_line()),
            "p": CommandBinding(lambda repeat: clipboard.paste_after_selection()),
            "P": CommandBinding(lambda repeat: clipboard.paste_before_selection()),
            "colon": CommandBinding(lambda repeat: editor.enter_command_mode()),
            "semicolon": CommandBinding(lambda repeat: editor.handle_semicolon()),
            "dollar_sign": CommandBinding(
                lambda repeat: editor.action_cursor_line_end()
            ),
            "percent_sign": CommandBinding(
                lambda repeat: cursor.move_to_matching_bracket()
            ),
            "ampersand": CommandBinding(lambda repeat: editor.handle_ampersand()),
            "tilde": CommandBinding(lambda repeat: editor.toggle_case_at_cursor()),
            "grave_accent": CommandBinding(lambda repeat: editor.handle_backtick()),
            "circumflex_accent": CommandBinding(
                lambda repeat: cursor.move_to_first_non_blank()
            ),
            "q": CommandBinding(lambda repeat: editor.macro_recorder.handle_q_press()),
            "at": CommandBinding(
                lambda repeat: editor.macro_recorder.handle_at_press()
            ),
        }

    def enter(self, **kwargs):
        self.activate()
        self.editor.read_only = True
        return True

    def after_command(self, command: str, repeat: int) -> None:
        self.editor.read_only = True


class InsertModeHandler(ModeHandler):
    mode = VimMode.INSERT

    def __init__(self, editor, actions: EditorActions) -> None:
        super().__init__(editor, actions)
        self._bindings = self._build_bindings()

    def _build_bindings(self) -> Dict[str, Callable[[], None]]:
        cursor = self.editor.cursor_service
        return {
            "escape": self.editor.enter_normal_mode,
            "ctrl+j": lambda: self.editor.insert("\n"),
            "ctrl+b": cursor.indent,
            "ctrl+d": cursor.de_indent,
            "ctrl+w": self.editor.action_delete_word_left,
            "ctrl+u": self.editor.action_delete_to_start_of_line,
            "ctrl+k": self.editor.action_delete_to_end_of_line,
            "ctrl+a": self.editor.action_cursor_line_start,
            "ctrl+e": self.editor.action_cursor_line_end,
        }

    def enter(
        self,
        at_cursor: bool = True,
        at_line_start: bool = False,
        after_cursor: bool = False,
        after_line: bool = False,
        new_line_below: bool = False,
        new_line_above: bool = False,
    ) -> bool:
        self.activate()
        editor = self.editor

        if at_line_start:
            editor.action_cursor_line_start()
        elif after_cursor:
            editor.action_cursor_right()
        elif after_line:
            editor.action_cursor_line_end()
        elif new_line_below:
            editor.action_cursor_line_end()
            editor.insert("\n")
            editor.action_cursor_down()
        elif new_line_above:
            editor.action_cursor_line_start()
            editor.insert("\n")
            editor.action_cursor_up()

        editor.read_only = False
        editor.refresh()
        return True

    def handle_key(self, event: Key) -> bool:
        handler = self._bindings.get(event.key)
        if handler:
            handler()
            if event.key == "escape":
                self.editor.read_only = True
            return True
        return False


class VisualBaseHandler(SequenceModeHandler):
    def __init__(
        self, editor, actions: EditorActions, bindings: Dict[str, CommandBinding]
    ):
        super().__init__(editor, actions, bindings, honor_repeats=True)

    def after_command(self, command: str, repeat: int) -> None:
        self.editor.read_only = True


class VisualModeHandler(VisualBaseHandler):
    mode = VimMode.VISUAL

    def __init__(self, editor, actions: EditorActions) -> None:
        bindings = self._build_bindings(editor, actions)
        super().__init__(editor, actions, bindings)

    def _build_bindings(
        self, editor, actions: EditorActions
    ) -> Dict[str, CommandBinding]:
        clipboard = editor.clipboard_service
        return {
            "escape": CommandBinding(lambda repeat: editor.enter_normal_mode()),
            "ctrl+c": CommandBinding(lambda repeat: editor.enter_normal_mode()),
            "ctrl+v": CommandBinding(
                lambda repeat: editor.enter_visual_block_mode(block_visual_mode=True)
            ),
            "v": CommandBinding(lambda repeat: editor.enter_normal_mode()),
            "V": CommandBinding(
                lambda repeat: editor.enter_visual_line_mode(linewise_visual_mode=True)
            ),
            "h": CommandBinding(
                lambda repeat: self._repeat(
                    lambda: editor.action_cursor_left(True), repeat
                )
            ),
            "l": CommandBinding(
                lambda repeat: self._repeat(
                    lambda: editor.action_cursor_right(True), repeat
                )
            ),
            "k": CommandBinding(
                lambda repeat: self._repeat(
                    lambda: editor.action_cursor_up(True), repeat
                )
            ),
            "j": CommandBinding(
                lambda repeat: self._repeat(
                    lambda: editor.action_cursor_down(True), repeat
                )
            ),
            "w": CommandBinding(
                lambda repeat: self._repeat(
                    lambda: editor.action_cursor_word_right(True), repeat
                )
            ),
            "b": CommandBinding(
                lambda repeat: self._repeat(
                    lambda: editor.action_cursor_word_left(True), repeat
                )
            ),
            "d": CommandBinding(lambda repeat: clipboard.delete_selection()),
            "y": CommandBinding(lambda repeat: clipboard.yank_selection()),
            "p": CommandBinding(lambda repeat: clipboard.paste_after_selection()),
            "c": CommandBinding(lambda repeat: actions.change_selection()),
            "u": CommandBinding(lambda repeat: actions.lowercase_selection()),
            "U": CommandBinding(lambda repeat: actions.uppercase_selection()),
            "o": CommandBinding(lambda repeat: actions.swap_selection_ends()),
            "gg": CommandBinding(lambda repeat: editor.action_go_first_line(True)),
            "G": CommandBinding(lambda repeat: editor.action_go_last_line(True)),
            "$": CommandBinding(lambda repeat: editor.action_cursor_line_end(True)),
            "^": CommandBinding(lambda repeat: editor.action_cursor_line_start(True)),
        }

    def enter(self) -> bool:
        self.activate()
        self.editor.selection_start = self.editor.cursor_location
        return True


class VisualLineModeHandler(VisualBaseHandler):
    mode = VimMode.VISUAL_LINE

    def __init__(self, editor, actions: EditorActions) -> None:
        bindings = self._build_bindings(editor, actions)
        super().__init__(editor, actions, bindings)

    def _build_bindings(
        self, editor, actions: EditorActions
    ) -> Dict[str, CommandBinding]:
        clipboard = editor.clipboard_service
        return {
            "escape": CommandBinding(lambda repeat: editor.enter_normal_mode()),
            "V": CommandBinding(lambda repeat: editor.enter_normal_mode()),
            "v": CommandBinding(lambda repeat: editor.enter_visual_mode()),
            "ctrl+v": CommandBinding(
                lambda repeat: editor.enter_visual_block_mode(block_visual_mode=True)
            ),
            "k": CommandBinding(
                lambda repeat: self._repeat(
                    lambda: editor.action_cursor_up(True), repeat
                )
            ),
            "j": CommandBinding(
                lambda repeat: self._repeat(
                    lambda: editor.action_cursor_down(True), repeat
                )
            ),
            "h": CommandBinding(lambda repeat: editor.action_cursor_left()),
            "l": CommandBinding(lambda repeat: editor.action_cursor_right()),
            "d": CommandBinding(lambda repeat: clipboard.delete_selection()),
            "y": CommandBinding(lambda repeat: clipboard.yank_selection()),
            "c": CommandBinding(lambda repeat: actions.change_selection()),
            ">": CommandBinding(lambda repeat: actions.indent_selection()),
            "<": CommandBinding(lambda repeat: actions.unindent_selection()),
            "~": CommandBinding(lambda repeat: actions.toggle_case_selection()),
            "u": CommandBinding(lambda repeat: actions.lowercase_selection()),
            "U": CommandBinding(lambda repeat: actions.uppercase_selection()),
            "p": CommandBinding(lambda repeat: actions.paste_over_selection()),
            "gg": CommandBinding(lambda repeat: editor.action_go_first_line(True)),
            "G": CommandBinding(lambda repeat: editor.action_go_last_line(True)),
        }

    def enter(self, linewise_visual_mode: bool = False) -> bool:
        self.activate()
        if linewise_visual_mode:
            self._select_line(self.editor.cursor_location[0])
        return True

    def _select_line(self, row: int) -> None:
        editor = self.editor
        start = (row, 0)
        end = (row, len(editor.lines[row]))
        editor.select(start, end)


class VisualBlockModeHandler(VisualBaseHandler):
    mode = VimMode.VISUAL_BLOCK

    def __init__(self, editor, actions: EditorActions) -> None:
        bindings = self._build_bindings(editor, actions)
        super().__init__(editor, actions, bindings)

    def _build_bindings(
        self, editor, actions: EditorActions
    ) -> Dict[str, CommandBinding]:
        cursor = editor.cursor_service
        return {
            "escape": CommandBinding(lambda repeat: editor.enter_normal_mode()),
            "V": CommandBinding(
                lambda repeat: editor.enter_visual_line_mode(linewise_visual_mode=True)
            ),
            "v": CommandBinding(lambda repeat: editor.enter_visual_mode()),
            "ctrl+v": CommandBinding(lambda repeat: editor.enter_normal_mode()),
            "h": CommandBinding(
                lambda repeat: self._repeat(
                    lambda: editor.action_cursor_left(True), repeat
                )
            ),
            "l": CommandBinding(
                lambda repeat: self._repeat(
                    lambda: editor.action_cursor_right(True), repeat
                )
            ),
            "k": CommandBinding(
                lambda repeat: self._repeat(
                    lambda: editor.action_cursor_up(True), repeat
                )
            ),
            "j": CommandBinding(
                lambda repeat: self._repeat(
                    lambda: editor.action_cursor_down(True), repeat
                )
            ),
            "d": CommandBinding(lambda repeat: actions.delete_block_selection()),
            "y": CommandBinding(lambda repeat: actions.yank_block_selection()),
            "c": CommandBinding(lambda repeat: actions.change_block_selection()),
            "I": CommandBinding(lambda repeat: actions.insert_block_selection()),
            "A": CommandBinding(lambda repeat: actions.append_block_selection()),
            ">": CommandBinding(lambda repeat: actions.indent_selection()),
            "<": CommandBinding(lambda repeat: actions.unindent_selection()),
            "~": CommandBinding(lambda repeat: actions.toggle_case_selection()),
            "u": CommandBinding(lambda repeat: actions.lowercase_selection()),
            "U": CommandBinding(lambda repeat: actions.uppercase_selection()),
            "o": CommandBinding(lambda repeat: actions.swap_selection_ends()),
            "gg": CommandBinding(lambda repeat: editor.action_go_first_line(True)),
            "G": CommandBinding(lambda repeat: editor.action_go_last_line(True)),
            "$": CommandBinding(lambda repeat: editor.action_cursor_line_end(True)),
            "^": CommandBinding(lambda repeat: editor.action_cursor_line_start(True)),
            "w": CommandBinding(
                lambda repeat: self._repeat(
                    lambda: editor.action_cursor_word_right(True), repeat
                )
            ),
            "b": CommandBinding(
                lambda repeat: self._repeat(
                    lambda: editor.action_cursor_word_left(True), repeat
                )
            ),
            "0": CommandBinding(lambda repeat: editor.action_cursor_line_start(True)),
            "%": CommandBinding(lambda repeat: cursor.move_to_matching_bracket()),
        }

    def enter(self, block_visual_mode: bool = False) -> bool:
        self.activate()
        return True


class CommandModeHandler(ModeHandler):
    mode = VimMode.COMMAND

    def __init__(self, editor, actions: EditorActions) -> None:
        super().__init__(editor, actions)
        self.command_buffer: str = ""

    def enter(self) -> bool:
        self.activate()
        self.command_buffer = ":"
        self._update_subtitle()
        return True

    def handle_key(self, event: Key) -> bool:
        key = event.key
        if key == "enter":
            self._execute()
            return True
        if key == "escape":
            self.editor.enter_normal_mode()
            return True
        if key == "backspace":
            self._handle_backspace()
            return True
        if key == "tab":
            self.editor.handle_completion()
            return True
        if key == "up":
            self.editor.cycle_history(-1)
            return True
        if key == "down":
            self.editor.cycle_history(1)
            return True
        if event.is_printable and event.character:
            self._append_character(event.character)
            return True
        return False

    def set_buffer(self, value: str) -> None:
        self.command_buffer = value
        self._update_subtitle()

    def _append_character(self, char: str) -> None:
        self.command_buffer += char
        self._update_subtitle()

    def _handle_backspace(self) -> None:
        if len(self.command_buffer) == 1:
            self.editor.enter_normal_mode()
            return
        self.command_buffer = self.command_buffer[:-1]
        self._update_subtitle()

    def _execute(self) -> None:
        cmd = self.command_buffer[1:]
        editor = self.editor

        if cmd:
            editor.register_command_history(cmd)

        if cmd.isdigit():
            editor.cursor_location = (int(cmd) - 1, 0)
        elif cmd == "q":
            editor.app.exit()
        elif cmd == "w":
            editor.notify("File saved", severity="information")
        elif cmd in {"wq", "x"}:
            editor.notify("File saved", severity="information")
            editor.app.exit()
        elif cmd == "setnu":
            editor.border_title = f"Line({editor.cursor_location[0] + 1})"
        elif "," in cmd:
            parsed = self._parse_range_command(cmd)
            if parsed:
                start_range, end_range, action = parsed
                start_line = self._resolve_range_value(start_range) + 3
                end_line = self._resolve_range_value(end_range) + 3
                end_col = 0
                if end_line < len(editor.lines):
                    end_col = len(editor.lines[end_line])
                editor.selection = (
                    (start_line, 0),
                    (end_line, end_col),
                )
                editor.yank_selection()
                if action == "d":
                    editor.action_delete_line()
        elif cmd == "macros":
            info = editor.macro_recorder.get_macro_info()
            if info:
                editor.notify("\n".join(info), severity="information")
            else:
                editor.notify("No macros recorded", severity="warning")

        self.editor.enter_normal_mode()

    def _parse_range_command(self, command: str) -> tuple[str, str, str] | None:
        if "," not in command:
            return None
        range_part, action = command[:-1], command[-1]
        start_range, end_range = range_part.split(",")
        return (start_range.strip(), end_range.strip(), action)

    def _resolve_range_value(self, range_str: str) -> int:
        editor = self.editor
        if range_str == ".":
            return editor.cursor_location[0]
        if range_str == "$":
            return len(editor.text.splitlines()) - 1
        return int(range_str) - 1

    def _update_subtitle(self) -> None:
        self.editor.border_subtitle = self.command_buffer.strip()
        self.editor.refresh()
