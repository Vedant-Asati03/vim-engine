"""Core action implementations shared across modes."""

from __future__ import annotations

from vim_engine.keymaps import ResolutionMatch
from vim_engine.modes.base_mode import ModeContext, ModeResult


def enter_insert_mode(context: ModeContext, match: ResolutionMatch) -> ModeResult:
    del match  # unused for now
    return ModeResult(consumed=True, switch_to="insert", message="enter_insert")


def exit_to_normal_mode(context: ModeContext, match: ResolutionMatch) -> ModeResult:
    del match  # unused for now
    return ModeResult(consumed=True, switch_to="normal", message="exit_insert")


def enter_visual_mode(context: ModeContext, match: ResolutionMatch) -> ModeResult:
    del match
    return ModeResult(consumed=True, switch_to="visual", message="enter_visual")


def enter_command_mode(context: ModeContext, match: ResolutionMatch) -> ModeResult:
    del match
    return ModeResult(consumed=True, switch_to="command", message="enter_command")


def noop_action(context: ModeContext, match: ResolutionMatch) -> ModeResult:
    del context, match
    return ModeResult(consumed=True, status="noop")


__all__ = [
    "enter_insert_mode",
    "exit_to_normal_mode",
    "enter_visual_mode",
    "enter_command_mode",
    "noop_action",
]
