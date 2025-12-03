"""Register storage and clipboard integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Optional


@dataclass(slots=True)
class RegisterValue:
    text: str
    type: str = "character"  # could be character, line, block


class RegisterBank:
    """Tracks unnamed, named, numbered, and special registers."""

    def __init__(self) -> None:
        self._registers: Dict[str, RegisterValue] = {}
        self._registers['"'] = RegisterValue(text="")

    def get(self, name: str) -> RegisterValue:
        return self._registers.get(name, RegisterValue(text=""))

    def set(self, name: str, value: RegisterValue) -> None:
        self._registers[name] = value
        if name != '"':
            self._registers['"'] = value

    def append(self, name: str, text: str) -> None:
        existing = self.get(name)
        combined = RegisterValue(text=existing.text + text, type=existing.type)
        self.set(name, combined)

    def serialize(self) -> Mapping[str, RegisterValue]:
        return dict(self._registers)

    def load(self, data: Mapping[str, RegisterValue]) -> None:
        self._registers.update(
            {k: RegisterValue(text=v.text, type=v.type) for k, v in data.items()}
        )

    def yank_to(
        self, name: str, text: str, *, register_type: str = "character"
    ) -> None:
        self.set(name, RegisterValue(text=text, type=register_type))

    def clipboard_get(self) -> Optional[str]:  # stub, host adapters override
        return None

    def clipboard_set(self, value: str) -> None:  # stub, host adapters override
        _ = value
