"""Core document data structures for vim_engine buffers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Sequence


@dataclass(slots=True)
class BufferDocument:
    """Immutable-ish text storage built on a simple list-of-lines model.

    The first milestone keeps the implementation intentionally lightweight.
    Rope-backed or gap-buffer variants can be introduced later without
    changing the public API.
    """

    _lines: List[str] = field(default_factory=lambda: [""])
    version: int = 0
    dirty: bool = False

    @classmethod
    def from_text(cls, text: str) -> "BufferDocument":
        lines = text.splitlines()
        if not lines:
            lines = [""]
        elif text.endswith("\n"):
            lines.append("")
        return cls(_lines=list(lines), version=0, dirty=False)

    def snapshot(self) -> Sequence[str]:
        """Return the current lines without exposing internal mutability."""

        return tuple(self._lines)

    def replace(
        self, *, lines: Iterable[str], dirty: bool | None = None
    ) -> "BufferDocument":
        """Return a new document with the provided lines and bumped version."""

        updated = BufferDocument(_lines=list(lines), version=self.version + 1)
        updated.dirty = bool(dirty if dirty is not None else self.dirty)
        return updated

    def update_lines(
        self, start: int, end: int, new_lines: Iterable[str]
    ) -> "BufferDocument":
        """Return a document with ``[start:end]`` replaced by ``new_lines``."""

        lines = list(self._lines)
        lines[start:end] = list(new_lines)
        updated = BufferDocument(_lines=lines, version=self.version + 1, dirty=True)
        return updated

    @property
    def line_count(self) -> int:
        return len(self._lines)

    def get_line(self, index: int) -> str:
        return self._lines[index]
