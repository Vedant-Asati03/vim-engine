"""Undo/redo scaffolding for buffer operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .state import Cursor


@dataclass(slots=True)
class UndoEntry:
    label: str
    before_text: str
    after_text: str
    cursor_before: Cursor
    cursor_after: Cursor


class UndoTimeline:
    """Linear undo/redo history with placeholder methods for future tree support."""

    def __init__(self) -> None:
        self._entries: List[UndoEntry] = []
        self._index: int = -1

    def push(self, entry: UndoEntry) -> None:
        if self._index < len(self._entries) - 1:
            self._entries = self._entries[: self._index + 1]
        self._entries.append(entry)
        self._index = len(self._entries) - 1

    def can_undo(self) -> bool:
        return self._index >= 0

    def can_redo(self) -> bool:
        return self._index < len(self._entries) - 1

    def undo(self) -> Optional[UndoEntry]:
        if not self.can_undo():
            return None
        entry = self._entries[self._index]
        self._index -= 1
        return entry

    def redo(self) -> Optional[UndoEntry]:
        if not self.can_redo():
            return None
        self._index += 1
        return self._entries[self._index]
