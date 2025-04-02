from .base_mode import BaseMode
from ..config import VimMode


class InsertMode(BaseMode):
    def enter_insert_mode(
        self,
        at_cursor: bool = True,
        at_line_start: bool = False,
        after_cursor: bool = False,
        after_line: bool = False,
        new_line_below: bool = False,
        new_line_above: bool = False,
    ) -> None:
        """Enter insert mode with various cursor positioning options."""
        self._setup_mode(VimMode.INSERT)  # Pass VimMode enum, not config

        # Handle cursor positioning
        if at_line_start:
            self.action_cursor_line_start()
        elif after_cursor:
            self.action_cursor_right()
        elif after_line:
            self.action_cursor_line_end()
        elif new_line_below:
            self.action_cursor_line_end()
            self.insert("\n")
            self.action_cursor_down()
        elif new_line_above:
            self.action_cursor_line_start()
            self.insert("\n")
            self.action_cursor_up()

        self.refresh()
        return True  # Add this to indicate event should be prevented
