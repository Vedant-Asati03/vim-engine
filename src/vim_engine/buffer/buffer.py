"""High-level buffer façade combining document, state, registers, and undo."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import ContextManager, Optional

from vim_engine.runtime import telemetry

from .document import BufferDocument
from .registers import RegisterBank
from .state import BufferState, Cursor, Selection
from .sync import BufferMirror
from .undo import UndoEntry, UndoTimeline
from .validation import ensure_cursor


@dataclass(slots=True)
class BufferView:
    version: int
    text: str
    cursor: Cursor
    selection: Optional[Selection]


@dataclass(slots=True)
class BufferDelta:
    version: int
    text: str
    cursor: Cursor
    selection: Optional[Selection]
    label: str


class Buffer:
    def __init__(
        self,
        *,
        name: str = "default",
        document: Optional[BufferDocument] = None,
        state: Optional[BufferState] = None,
        registers: Optional[RegisterBank] = None,
        undo: Optional[UndoTimeline] = None,
    ) -> None:
        self.name = name
        self.document = document or BufferDocument()
        self.state = state or BufferState()
        self.registers = registers or RegisterBank()
        self.undo = undo or UndoTimeline()

    @classmethod
    def from_text(cls, text: str, *, name: str = "default") -> "Buffer":
        return cls(name=name, document=BufferDocument.from_text(text))

    def snapshot(self) -> BufferView:
        return BufferView(
            version=self.document.version,
            text=_flatten_lines(self.document.snapshot()),
            cursor=self.state.cursor,
            selection=self.state.selection,
        )

    def mirror(self, *, attributes: Optional[dict[str, str]] = None) -> BufferMirror:
        return BufferMirror(
            text=_flatten_lines(self.document.snapshot()),
            cursor=self.state.cursor,
            selection=self.state.selection,
            attributes=dict(attributes or {}),
        )

    def replace_range(
        self, start: Cursor, end: Cursor, text: str, *, label: str
    ) -> BufferDelta:
        after_text = ""
        start = ensure_cursor(self.document, start)
        end = ensure_cursor(self.document, end)
        with Transaction(self, label) as tx:
            before_text = _flatten_lines(self.document.snapshot())
            start_offset = _offset_for_cursor(self.document, start)
            end_offset = _offset_for_cursor(self.document, end)
            new_text = before_text[:start_offset] + text + before_text[end_offset:]
            self.document = BufferDocument.from_text(new_text)
            self.state.set_cursor(
                *_cursor_from_offset(self.document, start_offset + len(text))
            )
            self.state.last_change_tick = self.document.version
            after_text = new_text
            tx.commit(before_text, after_text, start, self.state.cursor)

        return BufferDelta(
            version=self.document.version,
            text=after_text,
            cursor=self.state.cursor,
            selection=self.state.selection,
            label=label,
        )

    def insert_text(self, text: str, *, cursor: Optional[Cursor] = None) -> BufferDelta:
        position = cursor or self.state.cursor
        return self.replace_range(position, position, text, label="insert_text")

    def delete_range(self, start: Cursor, end: Cursor) -> BufferDelta:
        return self.replace_range(start, end, "", label="delete_range")

    def get_text_range(self, start: Cursor, end: Cursor) -> str:
        start = ensure_cursor(self.document, start)
        end = ensure_cursor(self.document, end)
        if start > end:
            start, end = end, start
        text = _flatten_lines(self.document.snapshot())
        start_offset = _offset_for_cursor(self.document, start)
        end_offset = _offset_for_cursor(self.document, end)
        return text[start_offset:end_offset]


class Transaction(AbstractContextManager["Transaction"]):
    def __init__(self, buffer: Buffer, label: str) -> None:
        self.buffer = buffer
        self.label = label
        self._span_cm: Optional[ContextManager[object]] = None
        self._before_cursor: Cursor | None = None

    def __enter__(self) -> "Transaction":
        self._before_cursor = self.buffer.state.cursor
        self._span_cm = telemetry.span(
            name=f"buffer::{self.label}",
            component=True,
            metadata={"buffer": self.buffer.name},
        )
        self._span_cm.__enter__()
        return self

    def commit(
        self,
        before_text: str,
        after_text: str,
        cursor_before: Cursor,
        cursor_after: Cursor,
    ) -> None:
        entry = UndoEntry(
            label=self.label,
            before_text=before_text,
            after_text=after_text,
            cursor_before=cursor_before,
            cursor_after=cursor_after,
        )
        self.buffer.undo.push(entry)

    def __exit__(self, exc_type, exc, tb) -> bool:
        if self._span_cm is not None:
            self._span_cm.__exit__(exc_type, exc, tb)
        return False


def _flatten_lines(lines) -> str:
    return "\n".join(lines)


def _offset_for_cursor(document: BufferDocument, cursor: Cursor) -> int:
    lines = document.snapshot()
    row, col = cursor
    offset = 0
    for i in range(row):
        offset += len(lines[i]) + 1  # newline
    offset += col
    return offset


def _cursor_from_offset(document: BufferDocument, offset: int) -> Cursor:
    lines = document.snapshot()
    running = 0
    for row, line in enumerate(lines):
        line_len = len(line)
        if offset <= running + line_len:
            return (row, offset - running)
        running += line_len + 1
    return (len(lines) - 1, len(lines[-1]))
