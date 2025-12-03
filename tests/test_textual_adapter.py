from __future__ import annotations

from typing import Any, Dict, List

from vim_engine.buffer import Buffer
from vim_engine.keymaps import KeymapRegistry, KeymapResolver, load_default_keymaps
from vim_engine.modes import (
    CommandMode,
    InsertMode,
    ModeBus,
    ModeContext,
    NormalMode,
    VisualMode,
)
from vim_engine.modes.mode_manager import ModeManager
from vim_engine.adapters.textual import TextualUIHooks, TextualVimAdapter


def make_manager() -> ModeManager:
    registry = KeymapRegistry()
    load_default_keymaps(registry)
    resolver = KeymapResolver(registry)
    buffer = Buffer()
    context = ModeContext(
        buffer=buffer, registers=buffer.registers, bus=ModeBus(), extras={}
    )
    manager = ModeManager(
        context, keymap_registry=registry, keymap_resolver=resolver, load_defaults=False
    )
    manager.register_mode(NormalMode)
    manager.register_mode(InsertMode)
    manager.register_mode(VisualMode)
    manager.register_mode(CommandMode)
    return manager


def test_adapter_updates_buffer_and_status() -> None:
    manager = make_manager()
    updates: List[str] = []
    statuses: List[str] = []
    hooks = TextualUIHooks(
        update_buffer=lambda mirror: updates.append(mirror.text),
        update_status=lambda status: statuses.append(status),
    )
    adapter = TextualVimAdapter(manager, hooks)

    adapter.handle_textual_key("i")
    adapter.handle_textual_key("ESC")

    assert updates  # buffer snapshots captured
    assert "enter_insert" in statuses
    assert any(status.startswith("timeout") is False for status in statuses)


def test_adapter_relays_command_events() -> None:
    manager = make_manager()
    command_lines: List[str] = []
    events: List[tuple[str, object | None]] = []
    hooks = TextualUIHooks(
        update_buffer=lambda mirror: None,
        show_command=lambda text: command_lines.append(text),
        handle_event=lambda name, payload: events.append((name, payload)),
        update_status=lambda status: None,
    )
    adapter = TextualVimAdapter(manager, hooks)

    adapter.handle_textual_key(":", text=":")
    adapter.handle_textual_key("w", text="w")
    adapter.handle_textual_key("q", text="q")
    adapter.handle_textual_key("ENTER")

    assert command_lines[-1] == ""
    assert ("command.submit", "wq") in events
    written = next(payload for name, payload in events if name == "command.write")
    assert isinstance(written, dict)
    assert written["force"] is False


def test_adapter_surfaces_visual_selection_events() -> None:
    manager = make_manager()
    events: List[Dict[str, Any]] = []
    hooks = TextualUIHooks(
        update_buffer=lambda mirror: None,
        handle_event=lambda name, payload: events.append(
            {"name": name, "payload": payload}
        ),
        update_status=lambda status: None,
    )
    adapter = TextualVimAdapter(manager, hooks)

    adapter.handle_textual_key("v")
    adapter.handle_textual_key("l")

    visual_payloads = [event for event in events if event["name"] == "visual.selection"]
    assert visual_payloads
    assert visual_payloads[-1]["payload"] is not None


def test_adapter_emits_log_lines() -> None:
    manager = make_manager()
    logs: List[str] = []
    hooks = TextualUIHooks(
        update_buffer=lambda mirror: None,
        update_status=lambda status: None,
        show_command=lambda _: None,
        handle_event=lambda _name, _payload: None,
        log=lambda line: logs.append(line),
    )
    adapter = TextualVimAdapter(manager, hooks)

    adapter.handle_textual_key("i")

    assert any(line.startswith("key ->") for line in logs)
