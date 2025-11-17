"""Utility classes for describing and executing command bindings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


CommandHandler = Callable[[int], None]


@dataclass(slots=True)
class CommandBinding:
    """Associates a key sequence with an executable action."""

    handler: CommandHandler
    description: str | None = None

    def run(self, repeat: int) -> None:
        self.handler(max(repeat, 1))
