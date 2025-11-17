"""Shared editing actions reused across mode handlers."""

from __future__ import annotations

from textual.widgets.text_area import Selection


class EditorActions:
    """Collection of high-level editing verbs used by keybindings."""

    def __init__(self, editor) -> None:
        self._editor = editor
        self._clipboard = editor.clipboard_service

    @property
    def editor(self):
        return self._editor

    def delete_at_cursor(self) -> None:
        editor = self._editor
        row, col = editor.cursor_location
        end = (
            row,
            min(
                col + 1, len(editor.lines[row]) if row < len(editor.lines) else col + 1
            ),
        )
        editor.selection = Selection(editor.cursor_location, end)
        self._clipboard.yank_selection()
        editor.cursor_location = (row, col)
        editor.delete((row, col), end)

    def delete_before_cursor(self) -> None:
        editor = self._editor
        row, col = editor.cursor_location
        if col > 0:
            editor.selection = Selection((row, col - 1), editor.cursor_location)
            self._clipboard.yank_selection()
        editor.cursor_location = (row, col)
        editor.action_delete_left()

    def delete_line(self) -> None:
        editor = self._editor
        editor.action_select_line()
        self._clipboard.yank_selection()
        editor.action_delete_line()

    def yank_line(self) -> None:
        editor = self._editor
        editor.action_select_line()
        self._clipboard.yank_selection()
        editor.selection = Selection()

    def indent_selection(self) -> None:
        editor = self._editor
        start_row = min(editor.selection[0][0], editor.selection[1][0])
        end_row = max(editor.selection[0][0], editor.selection[1][0])
        for row in range(start_row, end_row + 1):
            editor.move_cursor((row, 0))
            editor.insert("    ")
        editor.enter_normal_mode()

    def unindent_selection(self) -> None:
        editor = self._editor
        start_row = min(editor.selection[0][0], editor.selection[1][0])
        end_row = max(editor.selection[0][0], editor.selection[1][0])
        for row in range(start_row, end_row + 1):
            line = editor.lines[row]
            if line.startswith("    "):
                editor.move_cursor((row, 0))
                for _ in range(4):
                    editor.action_delete()
        editor.enter_normal_mode()

    def change_selection(self) -> None:
        editor = self._editor
        if editor.selected_text:
            self._clipboard.delete_selection()
            editor.enter_insert_mode()

    def toggle_case_selection(self) -> None:
        editor = self._editor
        if editor.selected_text:
            text = editor.selected_text
            self._clipboard.delete_selection()
            editor.insert(text.swapcase())
            editor.enter_normal_mode()

    def uppercase_selection(self) -> None:
        editor = self._editor
        if editor.selected_text:
            text = editor.selected_text.upper()
            start, end = editor.selection
            editor.replace(text, start, end, maintain_selection_offset=False)
            editor.enter_normal_mode()

    def lowercase_selection(self) -> None:
        editor = self._editor
        if editor.selected_text:
            text = editor.selected_text.lower()
            start, end = editor.selection
            editor.replace(text, start, end, maintain_selection_offset=False)
            editor.enter_normal_mode()

    def paste_over_selection(self) -> None:
        editor = self._editor
        if editor.selected_text:
            self._clipboard.delete_selection()
            editor.paste()
            editor.enter_normal_mode()

    def swap_selection_ends(self) -> None:
        editor = self._editor
        if editor.selection:
            start, end = editor.selection
            editor.move_cursor(
                start if editor.cursor_location == end else end, select=True
            )

    def delete_block_selection(self) -> None:
        editor = self._editor
        if not editor.selection:
            return
        start, end = editor.selection
        start_row, start_col = start
        end_row, end_col = end
        for row in range(min(start_row, end_row), max(start_row, end_row) + 1):
            left = min(start_col, end_col)
            right = max(start_col, end_col)
            editor.delete((row, left), (row, right))
        editor.enter_normal_mode()

    def change_block_selection(self) -> None:
        editor = self._editor
        if editor.selected_text:
            self.delete_block_selection()
            editor.enter_insert_mode()

    def insert_block_selection(self) -> None:
        editor = self._editor
        if editor.selected_text:
            start, _ = editor.selection
            editor.move_cursor(start)
            editor.enter_insert_mode()

    def append_block_selection(self) -> None:
        editor = self._editor
        if editor.selected_text:
            _, end = editor.selection
            end_row, end_col = end
            editor.move_cursor((end_row, end_col + 1))
            editor.enter_insert_mode()

    def yank_block_selection(self) -> None:
        editor = self._editor
        if not editor.selection:
            return
        start, end = editor.selection
        start_row, start_col = start
        end_row, end_col = end
        block_text: list[str] = []
        left_col = min(start_col, end_col)
        right_col = max(start_col, end_col)
        for row in range(min(start_row, end_row), max(start_row, end_row) + 1):
            if row < len(editor.lines):
                line = editor.lines[row]
                block_line = line[left_col:right_col] if left_col < len(line) else ""
                block_text.append(block_line)
        editor.app.clipboard = "\n".join(block_text)
        editor.enter_normal_mode()
