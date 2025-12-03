"""Actions dedicated to Visual mode selection management."""

from __future__ import annotations

from typing import MutableMapping, Tuple, cast

from vim_engine.buffer import Buffer
from vim_engine.buffer.state import Cursor
from vim_engine.modes.base_mode import ModeContext, ModeResult

CursorVector = Tuple[int, int]


def _visual_state(context: ModeContext) -> MutableMapping[str, Cursor]:
    state = cast(
        MutableMapping[str, Cursor], context.extras.setdefault("visual_state", {})
    )
    if "anchor" not in state:
        state["anchor"] = context.buffer.state.cursor
    return state


def _clamp_cursor(buffer: Buffer, row: int, col: int) -> Cursor:
    lines = buffer.document.snapshot()
    max_row = max(0, len(lines) - 1)
    row = max(0, min(row, max_row))
    line = lines[row]
    col = max(0, min(col, len(line)))
    return (row, col)


def _apply_selection(context: ModeContext, target: Cursor) -> ModeResult:
    buffer = context.buffer
    target = _clamp_cursor(buffer, *target)
    buffer.state.set_cursor(*target)
    anchor = _visual_state(context)["anchor"]
    buffer.state.set_selection(anchor, target)
    context.bus.emit("visual.selection", {"anchor": anchor, "cursor": target})
    return ModeResult(consumed=True, status="visual_select")


def _move_by_delta(context: ModeContext, delta: CursorVector) -> ModeResult:
    row, col = context.buffer.state.cursor
    d_row, d_col = delta
    target = (row + d_row, col + d_col)
    return _apply_selection(context, target)


def extend_left(context: ModeContext, match) -> ModeResult:
    del match
    row, col = context.buffer.state.cursor
    if col > 0:
        return _apply_selection(context, (row, col - 1))
    if row == 0:
        return _apply_selection(context, (0, 0))
    prev_line = row - 1
    prev_col = len(context.buffer.document.get_line(prev_line))
    return _apply_selection(context, (prev_line, prev_col))


def extend_right(context: ModeContext, match) -> ModeResult:
    del match
    row, col = context.buffer.state.cursor
    line = context.buffer.document.get_line(row)
    if col < len(line):
        return _apply_selection(context, (row, col + 1))
    if row >= context.buffer.document.line_count - 1:
        return _apply_selection(context, (row, len(line)))
    return _apply_selection(context, (row + 1, 0))


def extend_up(context: ModeContext, match) -> ModeResult:
    del match
    row, col = context.buffer.state.cursor
    if row == 0:
        return _apply_selection(context, (0, col))
    target_row = row - 1
    target_col = min(col, len(context.buffer.document.get_line(target_row)))
    return _apply_selection(context, (target_row, target_col))


def extend_down(context: ModeContext, match) -> ModeResult:
    del match
    row, col = context.buffer.state.cursor
    if row >= context.buffer.document.line_count - 1:
        line = context.buffer.document.get_line(row)
        return _apply_selection(context, (row, len(line)))
    target_row = row + 1
    target_col = min(col, len(context.buffer.document.get_line(target_row)))
    return _apply_selection(context, (target_row, target_col))


def yank_selection(context: ModeContext, match) -> ModeResult:
    del match
    selection = context.buffer.state.selection
    if not selection:
        return ModeResult(consumed=False, status="no_selection")
    start, end = selection
    text = context.buffer.get_text_range(start, end)
    register_name = context.buffer.state.active_register or '"'
    context.buffer.registers.yank_to(register_name, text, register_type="character")
    context.bus.emit(
        "visual.yank",
        {"register": register_name, "text": text, "range": (start, end)},
    )
    return ModeResult(consumed=True, status="visual_yank", message=register_name)


def swap_anchor(context: ModeContext, match) -> ModeResult:
    del match
    state = _visual_state(context)
    cursor = context.buffer.state.cursor
    anchor = cast(Cursor, state.get("anchor", cursor))
    state["anchor"] = cursor
    context.buffer.state.set_cursor(*anchor)
    context.buffer.state.set_selection(state["anchor"], anchor)
    context.bus.emit(
        "visual.selection",
        {"anchor": state["anchor"], "cursor": anchor, "swap": True},
    )
    return ModeResult(consumed=True, status="visual_swap")


def delete_selection(context: ModeContext, match) -> ModeResult:
    del match
    text = _delete_selection(context, label="visual_delete")
    if text is None:
        return ModeResult(consumed=False, status="no_selection")
    return ModeResult(
        consumed=True,
        switch_to="normal",
        status="visual_delete",
        message=text,
    )


def change_selection(context: ModeContext, match) -> ModeResult:
    del match
    text = _delete_selection(context, label="visual_change")
    if text is None:
        return ModeResult(consumed=False, status="no_selection")
    return ModeResult(
        consumed=True,
        switch_to="insert",
        status="visual_change",
        message=text,
    )


def _delete_selection(context: ModeContext, *, label: str) -> str | None:
    selection = _selection_range(context)
    if selection is None:
        return None
    start, end = selection
    text = context.buffer.get_text_range(start, end)
    register_name = context.buffer.state.active_register or '"'
    context.buffer.registers.yank_to(register_name, text, register_type="character")
    context.buffer.replace_range(start, end, "", label=label)
    context.buffer.state.clear_selection()
    _visual_state(context)["anchor"] = context.buffer.state.cursor
    context.bus.emit(
        "visual.delete",
        {
            "label": label,
            "text": text,
            "register": register_name,
            "range": (start, end),
        },
    )
    return text


def _selection_range(context: ModeContext) -> tuple[Cursor, Cursor] | None:
    selection = context.buffer.state.selection
    if not selection:
        return None
    start, end = selection
    if start <= end:
        return start, end
    return end, start


__all__ = [
    "extend_left",
    "extend_right",
    "extend_up",
    "extend_down",
    "yank_selection",
    "swap_anchor",
    "delete_selection",
    "change_selection",
]
