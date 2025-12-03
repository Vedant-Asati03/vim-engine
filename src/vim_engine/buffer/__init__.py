"""Buffer abstractions and undo/redo data structures."""

from .buffer import Buffer, BufferDelta, BufferView, Transaction
from .document import BufferDocument
from .registers import RegisterBank, RegisterValue
from .state import BufferState
from .sync import BufferMirror, BufferSync, BufferValidationError
from .undo import UndoEntry, UndoTimeline
from .validation import ensure_cursor

__all__ = [
    "BufferDocument",
    "BufferState",
    "RegisterBank",
    "RegisterValue",
    "UndoTimeline",
    "UndoEntry",
    "Buffer",
    "BufferDelta",
    "BufferView",
    "Transaction",
    "BufferMirror",
    "BufferSync",
    "BufferValidationError",
    "ensure_cursor",
]
