"""Cursor, selection, and change tracking state for buffers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

Cursor = Tuple[int, int]  # (row, column)
Selection = Tuple[Cursor, Cursor]


@dataclass(slots=True)
class BufferState:
    """Mutable cursor + selection info tied to a BufferDocument version."""

    cursor: Cursor = (0, 0)
    selection: Optional[Selection] = None
    active_register: str = '"'
    last_change_tick: int = 0

    def set_cursor(self, row: int, col: int) -> None:
        self.cursor = (row, col)

    def clear_selection(self) -> None:
        self.selection = None

    def set_selection(self, start: Cursor, end: Cursor) -> None:
        self.selection = (start, end)
