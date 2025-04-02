from textual.events import Key
from textual.widgets import TextArea

from .config import VimMode
from .custom_css import CSS
from .modes.insert_mode import InsertMode
from .modes.normal_mode import NormalMode
from .modes.visual_mode import VisualMode
from .modes.command_mode import CommandMode
from .vimbindings.normal_binding import NORMALMODEBINDINGS
from .vimbindings.insert_binding import INSERTMODEBINDINGS
from .vimbindings.visual_binding import VISUALMODEBINDINGS
from .vimbindings.command_binding import COMMANDMODEBINDINGS
from src.utils.cursor_movement import HandleCursorMovement
from src.utils.cut_paste import ManageEditorsClipboard
from .utils.macros import MacroRecorder


class VimBindings(
    NORMALMODEBINDINGS, INSERTMODEBINDINGS, VISUALMODEBINDINGS, COMMANDMODEBINDINGS
):
    def config_bindings(self):
        self.N_mode()
        self.I_mode()
        self.V_mode()
        self.C_mode()


class VimModes(InsertMode, NormalMode, VisualMode, CommandMode):
    pass


class VimEditor(
    TextArea,
    CSS,
    HandleCursorMovement,
    ManageEditorsClipboard,
    VimModes,
    VimBindings,
):
    read_only: bool = True
    mode: VimMode = VimMode.NORMAL
    current_sequence: str = ""
    command_history: dict[str, list[int]] = {}
    clipboard: str = ""
    _next_key_handler: callable = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.macro_recorder = MacroRecorder(self)

    def reset_sequence(self) -> None:
        """Resets the current key sequence after it's processed."""
        self.current_sequence = ""

    def capture_next_key(self, handler: callable) -> None:
        """Set up handler for next keypress.

        Args:
            handler: Callback function that takes a Key event
        """
        self._next_key_handler = handler

    def handle_mode_switch(self, event) -> None:
        """Process key events based on current mode."""
        should_record = (
            self.macro_recorder.recording_macro
            and self.mode == VimMode.NORMAL
            and event.key != "q"
            and not self._next_key_handler
        )

        if should_record:
            self.macro_recorder.record_key(event.key)

        if self._next_key_handler:
            self._next_key_handler(event)
            self._next_key_handler = None
            event.prevent_default()
            return

        match self.mode:
            case VimMode.COMMAND:
                if event.key in self.command_mode_bindings:
                    self.command_mode_bindings[event.key]()
                    event.prevent_default()
                elif event.is_printable:
                    self.append_to_command(event.character)
                    event.prevent_default()

            case VimMode.NORMAL:
                self.current_sequence += event.key

                if len(self.current_sequence) == 0 and event.key == "0":
                    if self.current_sequence.isdigit():
                        event.prevent_default()
                        return

                command, repeat = self.get_command_from_sequence()

                if command in self.normal_mode:
                    # Execute the command
                    self.normal_mode[command]()

                    if command not in list("iIoOaA"):
                        self.read_only = True

                    # Important: Reset sequence after command execution
                    self.reset_sequence()
                    event.prevent_default()
                else:
                    if len(self.current_sequence) > 10:
                        self.reset_sequence()

            case VimMode.VISUAL | VimMode.VISUAL_LINE | VimMode.VISUAL_BLOCK:
                self.current_sequence += event.key

                if self.current_sequence.isdigit():
                    event.prevent_default()
                    return

                command, repeat = self.get_command_from_sequence()
                bindings = {
                    VimMode.VISUAL: self.visual_mode_bindings,
                    VimMode.VISUAL_LINE: self.visual_line_mode_bindings,
                    VimMode.VISUAL_BLOCK: self.visual_block_mode_bindings,
                }

                if command in bindings[self.mode]:
                    self.read_only = False
                    self._record_command(command, repeat)

                    for _ in range(repeat):
                        bindings[self.mode][command]()

                    if command not in ["i", "I", "a", "A"]:
                        self.read_only = True

                    self.reset_sequence()
                    event.prevent_default()
                else:
                    if len(self.current_sequence) > 10:
                        self.reset_sequence()

            case VimMode.INSERT:
                if event.key in self.insert_mode_bindings:
                    self.insert_mode_bindings[event.key]()
                    if event.key == "escape":
                        self.read_only = True
                    event.prevent_default()

    def get_command_from_sequence(self) -> tuple[str, int]:
        """Parse a command sequence into command and repeat count.

        Handles sequences like:
        - "5j" -> move down 5 lines
        - "3dd" -> delete 3 lines
        - "10x" -> delete 10 characters

        Returns:
            tuple[str, int]: (command, repeat_count)
            command is the actual command, repeat_count is how many times to run it
        """
        repeat = 0
        command = self.current_sequence

        for i, char in enumerate(self.current_sequence):
            if char.isdigit():
                repeat = repeat * 10 + int(char)
            else:
                command = self.current_sequence[i:]
                break

        return command, repeat if repeat > 0 else 1

    def _record_command(self, command: str, repeat: int) -> None:
        """Record command usage with its repeat count.

        Stores commands and their repeat counts in command_history.
        Example:
        - 4dd -> {"dd": [4]}
        - x -> {"x": [1]}
        - 3j -> {"j": [3]}
        """
        if command not in self.command_history:
            self.command_history[command] = []
        self.command_history[command].append(repeat)
        # Update display to show latest command
        self.border_subtitle = f"Last: {command}[{repeat}] | {self.mode.value.upper()}"

    async def on_key(self, event: Key) -> None:
        """Capture key presses and handle multi-key sequences."""
        self.set_custom_css()
        self.config_bindings()
        self.handle_mode_switch(event)

        row, col = self.cursor_location

        show_selected = (
            f"Selected({len(self.selected_text)}) " if self.selected_text else ""
        )

        self.border_title = f"{show_selected}[ {event.key} ][{row + 1}:{col + 1}]"
