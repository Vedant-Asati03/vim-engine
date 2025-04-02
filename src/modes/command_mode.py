from .base_mode import BaseMode
from ..config import VimMode


class CommandMode(BaseMode):
    """Command mode for executing Ex commands.

    Handles colon commands like :w, :q, :wq, etc.
    """

    command_buffer: str = ""

    def enter_command_mode(self) -> None:
        """Enter command mode and initialize command input."""
        self._setup_mode(VimMode.COMMAND)
        self.command_buffer = ":"
        self.refresh()

    def _reset_command_buffer_and_enter_normal(self) -> None:
        """Clear command buffer."""
        self.command_buffer = ""
        self.enter_normal_mode()

    def _update_subtitle(self) -> None:
        """Update command input in subtitle bar."""
        self.border_subtitle = self.command_buffer.strip()
        self.refresh()

    def append_to_command(self, char: str) -> None:
        """Append character to command buffer."""
        self.command_buffer += char
        self._update_subtitle()

    def handle_backspace(self) -> None:
        """Handle backspace in command buffer."""
        if len(self.command_buffer) == 1:
            self.enter_normal_mode()

        self.command_buffer = self.command_buffer[:-1]
        self._update_subtitle()

    def execute_command(self) -> None:
        """Execute the current command in buffer."""
        cmd = self.command_buffer[1:]

        if cmd.isdigit():
            self.cursor_location = (int(cmd) - 1, 0)
        elif cmd == "q":
            self.app.exit()
        elif cmd == "w":
            self.notify("File saved", severity="information")
        elif cmd == "wq" or cmd == "x":
            self.notify("File saved", severity="information")
            self.app.exit()
        elif cmd == "setnu":
            self.border_title = f"Line({self.cursor_location[0] + 1})"
        elif "," in cmd:
            start_range, end_range, action = self._parse_range_command(cmd)
            start_line = self._resolve_range_value(start_range) + 3
            end_line = self._resolve_range_value(end_range) + 3
            self.selection = (start_line, 0), self.get_cursor_line_end_location()
            self.yank_selection()
            # 9,11 -> 6,8
            if action == "d":
                # self.delete(
                # (start_line, 0), (end_line, self.get_cursor_line_end_location())
                # )
                self.action_delete_line()
        elif cmd == "macros":
            # Show macro information
            info = self.macro_recorder.get_macro_info()
            if info:
                self.notify("\n".join(info), severity="information")
            else:
                self.notify("No macros recorded", severity="warning")

        self._reset_command_buffer_and_enter_normal()

    def _parse_range_command(self, command: str) -> tuple[str, str, str]:
        """Parse a range command like '10,1d', '.,1d', '.,$d' into components.

        Args:
            command: String like "10,1d" or ".,1d" or ".,$d"

        Returns:
            tuple: (start_range, end_range, action)
            where ranges can be: number, "." (current line), "$" (last line)
        """
        if "," not in command:
            return None

        range_part, action = command[:-1], command[-1]
        start_range, end_range = range_part.split(",")

        start_range = start_range.strip()
        end_range = end_range.strip()

        return (start_range, end_range, action)

    def _resolve_range_value(self, range_str: str) -> int:
        """Convert range value to line number.

        Args:
            range_str: String like "10", ".", "$"

        Returns:
            int: Resolved line number (0-based)
        """
        if range_str == ".":
            return self.cursor_location[0]  # Current line
        elif range_str == "$":
            return len(self.text.splitlines()) - 1  # Last line
        else:
            return int(range_str) - 1  # Convert to 0-based index
