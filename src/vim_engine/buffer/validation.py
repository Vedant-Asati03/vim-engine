"""Validation helpers shared across buffer services."""

from __future__ import annotations

from .document import BufferDocument
from .state import Cursor
from .sync import BufferValidationError


def ensure_cursor(document: BufferDocument, cursor: Cursor) -> Cursor:
    row, col = cursor
    if row < 0 or row >= document.line_count:
        raise BufferValidationError("Row out of range", cursor=cursor)
    line = document.get_line(row)
    if col < 0 or col > len(line):
        raise BufferValidationError("Column out of range", cursor=cursor)
    return cursor
