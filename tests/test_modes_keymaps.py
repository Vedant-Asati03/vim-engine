from __future__ import annotations

from typing import Any, Dict, Optional

import pytest

from vim_engine.buffer import Buffer
from vim_engine.keymaps import (
    Binding,
    KeySequence,
    KeymapRegistry,
    KeymapResolver,
    load_default_keymaps,
)
from vim_engine.modes import (
    CommandMode,
    InsertMode,
    KeyInput,
    ModeBus,
    ModeContext,
    NormalMode,
    VisualMode,
)
from vim_engine.modes.mode_manager import ModeManager


def make_context(
    registry: KeymapRegistry,
    resolver: KeymapResolver,
    *,
    buffer: Optional[Buffer] = None,
) -> ModeContext:
    buffer_obj = buffer or Buffer()
    registers = buffer_obj.registers
    extras: Dict[str, Any] = {
        "keymap_registry": registry,
        "keymap_resolver": resolver,
        "keymap_flags": {},
    }
    return ModeContext(
        buffer=buffer_obj,
        registers=registers,
        bus=ModeBus(),
        extras=extras,
    )


def test_normal_mode_uses_keymap_binding() -> None:
    registry = KeymapRegistry()
    load_default_keymaps(registry)
    resolver = KeymapResolver(registry)
    context = make_context(registry, resolver)
    mode = NormalMode(context)

    result = mode.handle_key(KeyInput(key="i"))

    assert result.switch_to == "insert"
    assert result.consumed is True


def test_insert_mode_escape_binding() -> None:
    registry = KeymapRegistry()
    load_default_keymaps(registry)
    resolver = KeymapResolver(registry)
    context = make_context(registry, resolver)
    mode = InsertMode(context)

    result = mode.handle_key(KeyInput(key="ESC"))

    assert result.switch_to == "normal"
    assert result.consumed is True


def test_normal_mode_pending_sequence() -> None:
    registry = KeymapRegistry()
    load_default_keymaps(registry)
    resolver = KeymapResolver(registry)
    context = make_context(registry, resolver)

    custom_binding = Binding(
        id="normal.gg",
        mode="normal",
        sequence=KeySequence.from_strings("g", "g"),
        action_id="core.enter_insert",
    )
    registry.register_binding(custom_binding)

    mode = NormalMode(context)

    pending = mode.handle_key(KeyInput(key="g"))
    assert pending.status == "pending"
    assert pending.consumed is True

    match = mode.handle_key(KeyInput(key="g"))
    assert match.switch_to == "insert"


def test_pending_sequence_timeout_via_mode_manager() -> None:
    registry = KeymapRegistry()
    load_default_keymaps(registry)
    custom_binding = Binding(
        id="normal.gg",
        mode="normal",
        sequence=KeySequence.from_strings("g", "g"),
        action_id="core.enter_insert",
    )
    registry.register_binding(custom_binding)
    resolver = KeymapResolver(registry)
    context = make_context(registry, resolver)
    manager = ModeManager(
        context,
        keymap_registry=registry,
        keymap_resolver=resolver,
        load_defaults=False,
    )
    manager.register_mode(NormalMode)

    pending = manager.handle_key(KeyInput(key="g"))
    assert pending.status == "pending"
    assert pending.timeout_ms is not None

    timeouts = manager.force_timeout("normal")
    assert "normal" in timeouts
    timeout_result = timeouts["normal"]
    assert timeout_result.status == "timeout"
    assert timeout_result.consumed is False


def test_normal_mode_custom_default_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = KeymapRegistry()
    load_default_keymaps(registry)
    custom_binding = Binding(
        id="normal.gg",
        mode="normal",
        sequence=KeySequence.from_strings("g", "g"),
        action_id="core.enter_insert",
    )
    registry.register_binding(custom_binding)
    resolver = KeymapResolver(registry)
    # Force resolver to skip timeout hints so the mode fallback is used.
    monkeypatch.setattr(KeymapResolver, "_pending_timeout", lambda self, node: None)
    context = make_context(registry, resolver)
    mode = NormalMode(context, default_pending_timeout_ms=250)

    pending = mode.handle_key(KeyInput(key="g"))

    assert pending.status == "pending"
    assert pending.timeout_ms == 250


def test_mode_manager_forwards_mode_kwargs(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = KeymapRegistry()
    load_default_keymaps(registry)
    custom_binding = Binding(
        id="normal.gg",
        mode="normal",
        sequence=KeySequence.from_strings("g", "g"),
        action_id="core.enter_insert",
    )
    registry.register_binding(custom_binding)
    resolver = KeymapResolver(registry)
    monkeypatch.setattr(KeymapResolver, "_pending_timeout", lambda self, node: None)
    context = make_context(registry, resolver)
    manager = ModeManager(
        context,
        keymap_registry=registry,
        keymap_resolver=resolver,
        load_defaults=False,
    )
    manager.register_mode(NormalMode, default_pending_timeout_ms=300)

    pending = manager.handle_key(KeyInput(key="g"))

    assert pending.timeout_ms == 300


def test_mode_manager_switches_to_visual_mode() -> None:
    registry = KeymapRegistry()
    load_default_keymaps(registry)
    resolver = KeymapResolver(registry)
    context = make_context(registry, resolver)
    manager = ModeManager(
        context,
        keymap_registry=registry,
        keymap_resolver=resolver,
        load_defaults=False,
    )
    manager.register_mode(NormalMode)
    manager.register_mode(VisualMode)

    result = manager.handle_key(KeyInput(key="v"))

    assert result.switch_to == "visual"
    assert manager.active_mode and manager.active_mode.name == "visual"


def test_visual_mode_operator_pipeline_emits_plan() -> None:
    registry = KeymapRegistry()
    load_default_keymaps(registry)
    resolver = KeymapResolver(registry)
    context = make_context(registry, resolver)
    events: list[object] = []
    context.bus.subscribe("operator.plan", lambda payload: events.append(payload))
    mode = VisualMode(context)
    mode.on_enter("normal")

    first = mode.handle_key(KeyInput(key="z"))
    assert first.status == "pending"

    second = mode.handle_key(KeyInput(key="w"))

    assert second.status == "operator"
    assert events and events[0] is not None


def test_command_mode_text_entry_and_submit() -> None:
    registry = KeymapRegistry()
    load_default_keymaps(registry)
    resolver = KeymapResolver(registry)
    context = make_context(registry, resolver)
    submitted: list[str] = []
    context.bus.subscribe("command.submit", lambda payload: submitted.append(payload))
    mode = CommandMode(context)
    mode.on_enter("normal")

    mode.handle_key(KeyInput(key="w", text="w"))
    mode.handle_key(KeyInput(key="q", text="q"))
    result = mode.handle_key(KeyInput(key="ENTER"))

    assert result.switch_to == "normal"
    assert submitted == ["wq"]


def test_visual_mode_selection_and_yank() -> None:
    registry = KeymapRegistry()
    load_default_keymaps(registry)
    resolver = KeymapResolver(registry)
    buffer = Buffer.from_text("alpha")
    context = make_context(registry, resolver, buffer=buffer)
    mode = VisualMode(context)
    mode.on_enter("normal")

    move = mode.handle_key(KeyInput(key="l"))

    assert move.status == "visual_select"
    assert context.buffer.state.selection == ((0, 0), (0, 1))

    yank = mode.handle_key(KeyInput(key="y"))

    assert yank.status == "visual_yank"
    assert context.buffer.registers.get('"').text == "a"


def test_command_mode_submit_binding_executes_action() -> None:
    registry = KeymapRegistry()
    load_default_keymaps(registry)
    resolver = KeymapResolver(registry)
    context = make_context(registry, resolver)
    submissions: list[str] = []
    writes: list[object] = []
    quits: list[object] = []
    context.bus.subscribe("command.submit", lambda payload: submissions.append(payload))
    context.bus.subscribe("command.write", lambda payload: writes.append(payload))
    context.bus.subscribe("command.quit", lambda payload: quits.append(payload))
    mode = CommandMode(context)
    mode.on_enter("normal")

    mode.handle_key(KeyInput(key="w", text="w"))
    mode.handle_key(KeyInput(key="q", text="q"))
    result = mode.handle_key(KeyInput(key="ENTER"))

    assert result.switch_to == "normal"
    assert submissions == ["wq"]
    assert len(writes) == 1
    assert writes[0]["force"] is False
    assert len(quits) == 1
    assert quits[0]["force"] is False


def test_visual_mode_swap_anchor() -> None:
    registry = KeymapRegistry()
    load_default_keymaps(registry)
    resolver = KeymapResolver(registry)
    buffer = Buffer.from_text("abcd")
    context = make_context(registry, resolver, buffer=buffer)
    mode = VisualMode(context)
    mode.on_enter("normal")

    mode.handle_key(KeyInput(key="l"))
    swap = mode.handle_key(KeyInput(key="o"))

    assert swap.status == "visual_swap"
    assert context.buffer.state.cursor == (0, 0)
    assert context.buffer.state.selection == ((0, 1), (0, 0))


def test_visual_mode_delete_selection_returns_to_normal() -> None:
    registry = KeymapRegistry()
    load_default_keymaps(registry)
    resolver = KeymapResolver(registry)
    buffer = Buffer.from_text("alpha")
    context = make_context(registry, resolver, buffer=buffer)
    mode = VisualMode(context)
    mode.on_enter("normal")
    mode.handle_key(KeyInput(key="l"))

    result = mode.handle_key(KeyInput(key="d"))

    assert result.switch_to == "normal"
    assert context.buffer.snapshot().text.startswith("lpha")
    assert context.buffer.registers.get('"').text == "a"


def test_visual_mode_change_selection_switches_to_insert() -> None:
    registry = KeymapRegistry()
    load_default_keymaps(registry)
    resolver = KeymapResolver(registry)
    buffer = Buffer.from_text("alpha")
    context = make_context(registry, resolver, buffer=buffer)
    mode = VisualMode(context)
    mode.on_enter("normal")
    mode.handle_key(KeyInput(key="l"))

    result = mode.handle_key(KeyInput(key="c"))

    assert result.switch_to == "insert"
    assert context.buffer.snapshot().text.startswith("lpha")


def test_command_mode_write_force_event() -> None:
    registry = KeymapRegistry()
    load_default_keymaps(registry)
    resolver = KeymapResolver(registry)
    context = make_context(registry, resolver)
    writes: list[Dict[str, object]] = []
    context.bus.subscribe("command.write", lambda payload: writes.append(payload))
    mode = CommandMode(context)
    mode.on_enter("normal")

    mode.handle_key(KeyInput(key="w", text="w"))
    mode.handle_key(KeyInput(key="!", text="!"))
    mode.handle_key(KeyInput(key="ENTER"))

    assert writes and writes[0]["force"] is True


def test_command_mode_x_command_triggers_write_and_quit() -> None:
    registry = KeymapRegistry()
    load_default_keymaps(registry)
    resolver = KeymapResolver(registry)
    context = make_context(registry, resolver)
    writes: list[Dict[str, object]] = []
    quits: list[Dict[str, object]] = []
    context.bus.subscribe("command.write", lambda payload: writes.append(payload))
    context.bus.subscribe("command.quit", lambda payload: quits.append(payload))
    mode = CommandMode(context)
    mode.on_enter("normal")

    mode.handle_key(KeyInput(key="x", text="x"))
    mode.handle_key(KeyInput(key="ENTER"))

    assert writes and writes[0]["force"] is False
    assert quits and quits[0]["force"] is False


def test_command_mode_edit_force_event() -> None:
    registry = KeymapRegistry()
    load_default_keymaps(registry)
    resolver = KeymapResolver(registry)
    context = make_context(registry, resolver)
    edits: list[Dict[str, object]] = []
    context.bus.subscribe("command.edit", lambda payload: edits.append(payload))
    mode = CommandMode(context)
    mode.on_enter("normal")

    for key in ["e", "d", "i", "t", "!"]:
        mode.handle_key(KeyInput(key=key, text=key))
    mode.handle_key(KeyInput(key="ENTER"))

    assert edits and edits[0]["force"] is True
