"""Editor mode configuration and constants."""

from dataclasses import dataclass
from enum import Enum


@dataclass
class ModeConfig:
    """Configuration for editor modes."""

    subtitle: str
    read_only: bool
    bg_color: str


class VimMode(str, Enum):
    """Available editor modes."""

    NORMAL = "normal"
    INSERT = "insert"
    VISUAL = "visual"
    VISUAL_LINE = "v_line"
    VISUAL_BLOCK = "v_block"
    COMMAND = "command"


MODE_CONFIGS = {
    VimMode.NORMAL: ModeConfig("NORMAL", True, "#98C379"),
    VimMode.INSERT: ModeConfig("INSERT", False, "#E8B86D"),
    VimMode.VISUAL: ModeConfig("VISUAL", True, "#6EACDA"),
    VimMode.VISUAL_LINE: ModeConfig("V-LINE", True, "#6EACDA"),
    VimMode.VISUAL_BLOCK: ModeConfig("V-BLOCK", True, "#6EACDA"),
    VimMode.COMMAND: ModeConfig(":", True, "#E06C75"),
}
