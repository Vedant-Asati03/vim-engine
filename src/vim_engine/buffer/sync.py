"""Adapter boundary types for syncing buffers with host widgets."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol

from .state import Cursor, Selection


@dataclass(slots=True)
class BufferMirror:
    """Host-friendly snapshot describing the current buffer state."""

    text: str
    cursor: Cursor
    selection: Optional[Selection]
    attributes: dict[str, str] = field(default_factory=dict)


class BufferSync(Protocol):
    """Protocol describing how adapters exchange data with the buffer layer."""

    def pull_buffer(self) -> BufferMirror:
        """Return the latest buffer snapshot that the host should render."""
        ...

    def push_host_edit(self, mirror: BufferMirror) -> None:
        """Submit an external edit (e.g., IME insert, clipboard paste) to the buffer."""
        ...
        """Submit an external edit (e.g., IME insert, clipboard paste) to the buffer."""


class BufferValidationError(RuntimeError):
    """Raised when adapters or buffers provide out-of-bounds cursor info."""

    def __init__(self, message: str, *, cursor: Cursor | None = None) -> None:
        super().__init__(message)
        self.cursor = cursor
