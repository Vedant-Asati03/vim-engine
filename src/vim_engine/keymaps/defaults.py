"""Built-in keymaps that seed each mode with sensible defaults."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Mapping, Sequence

from vim_engine.actions import command as command_actions
from vim_engine.actions import core as core_actions
from vim_engine.actions import visual as visual_actions

from .models import ActionRef, Binding, KeySequence
from .registry import KeymapRegistry

DEFAULT_ACTIONS: tuple[ActionRef, ...] = (
    ActionRef(
        id="core.enter_insert",
        handler=core_actions.enter_insert_mode,
        description="Enter insert mode",
    ),
    ActionRef(
        id="core.exit_to_normal",
        handler=core_actions.exit_to_normal_mode,
        description="Return to normal mode",
    ),
    ActionRef(
        id="core.enter_visual",
        handler=core_actions.enter_visual_mode,
        description="Enter visual mode",
    ),
    ActionRef(
        id="core.enter_command",
        handler=core_actions.enter_command_mode,
        description="Enter command-line mode",
    ),
    ActionRef(
        id="visual.extend_left",
        handler=visual_actions.extend_left,
        description="Extend selection left",
    ),
    ActionRef(
        id="visual.extend_right",
        handler=visual_actions.extend_right,
        description="Extend selection right",
    ),
    ActionRef(
        id="visual.extend_up",
        handler=visual_actions.extend_up,
        description="Extend selection up",
    ),
    ActionRef(
        id="visual.extend_down",
        handler=visual_actions.extend_down,
        description="Extend selection down",
    ),
    ActionRef(
        id="visual.yank_selection",
        handler=visual_actions.yank_selection,
        description="Yank current visual selection",
    ),
    ActionRef(
        id="visual.swap_anchor",
        handler=visual_actions.swap_anchor,
        description="Swap selection anchor",
    ),
    ActionRef(
        id="visual.delete_selection",
        handler=visual_actions.delete_selection,
        description="Delete current selection",
    ),
    ActionRef(
        id="visual.change_selection",
        handler=visual_actions.change_selection,
        description="Change current selection",
    ),
    ActionRef(
        id="command.submit_line",
        handler=command_actions.submit_command_line,
        description="Evaluate the active command line",
    ),
)

DEFAULT_BINDINGS: tuple[Binding, ...] = (
    Binding(
        id="normal.enter_insert",
        mode="normal",
        sequence=KeySequence.from_strings("i"),
        action_id="core.enter_insert",
        description="Enter insert mode",
    ),
    Binding(
        id="normal.enter_visual",
        mode="normal",
        sequence=KeySequence.from_strings("v"),
        action_id="core.enter_visual",
        description="Enter visual mode",
    ),
    Binding(
        id="normal.enter_command",
        mode="normal",
        sequence=KeySequence.from_strings(":"),
        action_id="core.enter_command",
        description="Enter command-line mode",
    ),
    Binding(
        id="insert.exit_escape",
        mode="insert",
        sequence=KeySequence.from_strings("ESC"),
        action_id="core.exit_to_normal",
        description="Leave insert mode",
    ),
    Binding(
        id="insert.exit_escape_alt",
        mode="insert",
        sequence=KeySequence.from_strings("<Esc>"),
        action_id="core.exit_to_normal",
        description="Leave insert mode",
    ),
    Binding(
        id="visual.exit_escape",
        mode="visual",
        sequence=KeySequence.from_strings("ESC"),
        action_id="core.exit_to_normal",
        description="Leave visual mode",
    ),
    Binding(
        id="visual.exit_escape_alt",
        mode="visual",
        sequence=KeySequence.from_strings("<Esc>"),
        action_id="core.exit_to_normal",
        description="Leave visual mode",
    ),
    Binding(
        id="visual.extend_left",
        mode="visual",
        sequence=KeySequence.from_strings("h"),
        action_id="visual.extend_left",
        description="Extend selection left",
    ),
    Binding(
        id="visual.extend_right",
        mode="visual",
        sequence=KeySequence.from_strings("l"),
        action_id="visual.extend_right",
        description="Extend selection right",
    ),
    Binding(
        id="visual.extend_up",
        mode="visual",
        sequence=KeySequence.from_strings("k"),
        action_id="visual.extend_up",
        description="Extend selection up",
    ),
    Binding(
        id="visual.extend_down",
        mode="visual",
        sequence=KeySequence.from_strings("j"),
        action_id="visual.extend_down",
        description="Extend selection down",
    ),
    Binding(
        id="visual.yank_selection",
        mode="visual",
        sequence=KeySequence.from_strings("y"),
        action_id="visual.yank_selection",
        description="Yank the current selection",
    ),
    Binding(
        id="visual.swap_anchor",
        mode="visual",
        sequence=KeySequence.from_strings("o"),
        action_id="visual.swap_anchor",
        description="Swap selection anchor",
    ),
    Binding(
        id="visual.delete_selection",
        mode="visual",
        sequence=KeySequence.from_strings("d"),
        action_id="visual.delete_selection",
        description="Delete current selection",
    ),
    Binding(
        id="visual.change_selection",
        mode="visual",
        sequence=KeySequence.from_strings("c"),
        action_id="visual.change_selection",
        description="Change current selection",
    ),
    Binding(
        id="command.exit_escape",
        mode="command",
        sequence=KeySequence.from_strings("ESC"),
        action_id="core.exit_to_normal",
        description="Cancel command line",
    ),
    Binding(
        id="command.submit_enter",
        mode="command",
        sequence=KeySequence.from_strings("ENTER"),
        action_id="command.submit_line",
        description="Submit the command line",
    ),
    Binding(
        id="command.submit_return",
        mode="command",
        sequence=KeySequence.from_strings("RETURN"),
        action_id="command.submit_line",
        description="Submit the command line",
    ),
)


def load_default_keymaps(
    registry: KeymapRegistry,
    *,
    replace: bool = False,
    extra_bindings: Iterable[Binding] | None = None,
    default_sequence_timeout_ms: int | None = None,
    include_actions: Sequence[str] | None = None,
    exclude_actions: Sequence[str] | None = None,
    include_bindings: Sequence[str] | None = None,
    exclude_bindings: Sequence[str] | None = None,
    per_mode_overrides: Mapping[str, Iterable[Binding]] | None = None,
) -> None:
    """Register built-in actions and bindings for every mode."""

    allowed_actions = _build_filters(include_actions, exclude_actions)
    allowed_bindings = _build_filters(include_bindings, exclude_bindings)

    for action in DEFAULT_ACTIONS:
        if not _selected(action.id, allowed_actions):
            continue
        registry.register_action(action, replace=replace)

    for binding in DEFAULT_BINDINGS:
        if not _selected(binding.id, allowed_bindings):
            continue
        registry.register_binding(
            _binding_with_timeout(binding, default_sequence_timeout_ms),
            replace=replace,
        )

    if extra_bindings:
        for binding in extra_bindings:
            registry.register_binding(binding, replace=replace)

    if per_mode_overrides:
        for mode, bindings in per_mode_overrides.items():
            for binding in bindings:
                if binding.mode != mode:
                    raise ValueError(
                        f"Override binding '{binding.id}' must target mode '{mode}'"
                    )
                registry.register_binding(binding, replace=True)


def _binding_with_timeout(
    binding: Binding, timeout_ms: int | None
) -> Binding:  # pragma: no cover - exercised via public API
    if timeout_ms is None:
        return binding
    sequence = KeySequence(binding.sequence.strokes, timeout_ms=timeout_ms)
    return replace(binding, sequence=sequence)


__all__ = ["load_default_keymaps", "DEFAULT_ACTIONS", "DEFAULT_BINDINGS"]


def _build_filters(
    include: Sequence[str] | None, exclude: Sequence[str] | None
) -> tuple[set[str] | None, set[str]]:
    include_set = set(include) if include else None
    exclude_set = set(exclude or ())
    return include_set, exclude_set


def _selected(item_id: str, filters: tuple[set[str] | None, set[str]]) -> bool:
    include, exclude = filters
    if include is not None and item_id not in include:
        return False
    if item_id in exclude:
        return False
    return True
