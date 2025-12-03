"""High-level editing verbs reused across modes."""

from .core import enter_insert_mode, exit_to_normal_mode, noop_action
from .visual import (
    extend_down,
    extend_left,
    extend_right,
    extend_up,
    swap_anchor,
    yank_selection,
    delete_selection,
    change_selection,
)
from .command import submit_command_line

__all__ = [
    "enter_insert_mode",
    "exit_to_normal_mode",
    "noop_action",
    "extend_left",
    "extend_right",
    "extend_up",
    "extend_down",
    "swap_anchor",
    "yank_selection",
    "delete_selection",
    "change_selection",
    "submit_command_line",
]
