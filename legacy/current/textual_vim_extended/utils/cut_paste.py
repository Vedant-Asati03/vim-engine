from textual.widgets.text_area import Selection


class ClipboardService:
    """Encapsulates yank/paste helpers so they work via composition."""

    def __init__(self, editor) -> None:
        self._editor = editor

    def yank_selection(self) -> None:
        """Copy selected text to the editor clipboard."""
        editor = self._editor
        if editor.selected_text:
            editor.clipboard = editor.selected_text
        editor.selection = Selection()

    def paste_after_selection(self) -> None:
        """Paste clipboard contents at the current cursor and exit visual modes."""
        editor = self._editor
        if editor.clipboard:
            editor.insert(editor.clipboard)
        editor.enter_normal_mode()

    def paste_before_selection(self) -> None:
        """Insert clipboard contents before the current cursor position."""
        editor = self._editor
        if editor.clipboard:
            row, col = editor.cursor_location
            editor.cursor_location = (row, max(0, col - 1))
            editor.insert(editor.clipboard)
        editor.enter_normal_mode()

    def delete_selection(self) -> None:
        """Delete the current selection and leave visual mode."""
        editor = self._editor
        editor.action_delete_left()
        editor.selection = Selection(editor.cursor_location, editor.cursor_location)
        editor.enter_normal_mode()
