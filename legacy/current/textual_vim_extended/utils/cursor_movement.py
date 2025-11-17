"""Cursor manipulation helpers implemented as a composition-friendly service."""

from textual.widgets import TextArea


class CursorMovementService:
    """Wraps bespoke cursor movements so they can be injected into the editor."""

    def __init__(self, editor: TextArea) -> None:
        self._editor = editor

    def cursor_location_cache(self) -> tuple[int, int]:
        """Cache and return the current cursor location."""
        return self._editor.cursor_location

    def move_to_first_non_blank(self) -> None:
        """Move cursor to first non-blank character in line."""
        self._editor.cursor_location = self._editor.get_cursor_line_start_location(
            smart_home=True
        )

    def move_to_matching_bracket(self) -> None:
        """Move to matching bracket (%)."""
        self._editor.cursor_location = self._editor.matching_bracket_location

    def jump_backwards_to_end_of_word(self) -> None:
        """Move cursor to end of previous word (ge)."""
        editor = self._editor
        row, col = editor.cursor_location
        line = editor.lines[row]

        text_before = line[:col]
        if not text_before.strip():
            if row > 0:
                editor.move_cursor((row - 1, len(editor.lines[row - 1].rstrip())))
            return

        words = text_before.rstrip().split()
        if words:
            last_word = words[-1]
            new_col = text_before.rindex(last_word) + len(last_word)
            editor.move_cursor((row, new_col))

    def indent(self) -> None:
        """Indent the current line with proper cursor position maintenance."""
        editor = self._editor
        row, col = editor.cursor_location
        editor.action_cursor_line_start()
        editor.insert("    ")
        editor.move_cursor((row, col + 4))

    def de_indent(self) -> None:
        """Remove one level of indentation while maintaining cursor position."""
        editor = self._editor
        row, col = editor.cursor_location
        line = editor.lines[row]
        if line.startswith("    "):
            editor.action_cursor_line_start()
            for _ in range(4):
                editor.action_delete()
            editor.move_cursor((row, max(0, col - 4)))

    def move_to_mid_of_screen(self) -> None:
        """Move the cursor to the middle of the screen."""
        editor = self._editor
        height = editor.content_size.height
        _, cursor_location = editor.selection
        target = editor.navigator.get_location_at_y_offset(
            cursor_location,
            height // 2,
        )
        editor.move_cursor(target)

    def move_to_top_of_screen(self) -> None:
        """Move the cursor and scroll up one page."""
        editor = self._editor
        height = editor.content_size.height
        _, cursor_location = editor.selection
        target = editor.navigator.get_location_at_y_offset(
            cursor_location,
            -(height - 1),
        )
        editor.move_cursor(target)

    def move_to_bot_of_screen(self) -> None:
        """Move the cursor and scroll down one page."""
        editor = self._editor
        height = editor.content_size.height
        _, cursor_location = editor.selection
        target = editor.navigator.get_location_at_y_offset(
            cursor_location,
            (height - 1),
        )
        editor.move_cursor(target)

    def left_curly_bracket(self) -> None:
        """Move cursor to previous paragraph (placeholder)."""
        # TODO: Implement actual paragraph navigation logic.
        return


# Backwards-compatible alias for legacy imports.
HandleCursorMovement = CursorMovementService
