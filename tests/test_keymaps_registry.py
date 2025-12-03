import pytest

from vim_engine.keymaps import (
    ActionRef,
    Binding,
    KeySequence,
    KeymapConflictError,
    KeymapRegistry,
    WhenClause,
    load_default_keymaps,
)


def make_action(action_id: str = "core.test") -> ActionRef:
    return ActionRef(id=action_id, handler=lambda *args, **kwargs: None)


def make_sequence(*keys: str) -> KeySequence:
    return KeySequence.from_strings(*keys)


def make_binding(
    *,
    binding_id: str,
    mode: str = "normal",
    sequence: KeySequence | None = None,
    action_id: str = "core.test",
    when: tuple[WhenClause, ...] = (),
) -> Binding:
    return Binding(
        id=binding_id,
        mode=mode,
        sequence=sequence or make_sequence("g", "g"),
        action_id=action_id,
        when=when,
    )


def test_register_binding_success() -> None:
    registry = KeymapRegistry()
    action = make_action()
    registry.register_action(action)
    binding = make_binding(binding_id="normal.gg")

    registry.register_binding(binding)

    assert registry.stats().binding_count == 1
    assert list(registry.iter_bindings(mode="normal")) == [binding]


def test_register_binding_conflict_detection() -> None:
    registry = KeymapRegistry()
    registry.register_action(make_action())

    binding = make_binding(binding_id="normal.gg")
    registry.register_binding(binding)

    with pytest.raises(KeymapConflictError):
        registry.register_binding(make_binding(binding_id="normal.gg.duplicate"))


def test_register_binding_non_overlapping_when() -> None:
    registry = KeymapRegistry()
    registry.register_action(make_action())

    binding_default = make_binding(binding_id="default")
    binding_panel = make_binding(
        binding_id="panel",
        when=(WhenClause("panel_open"),),
    )
    binding_no_panel = make_binding(
        binding_id="no_panel",
        when=(WhenClause.parse("!panel_open"),),
    )

    registry.register_binding(binding_default)
    registry.register_binding(binding_panel)
    registry.register_binding(binding_no_panel)

    assert registry.stats().binding_count == 3


def test_register_binding_with_replace() -> None:
    registry = KeymapRegistry()
    registry.register_action(make_action())

    first = make_binding(binding_id="binding")
    second = make_binding(binding_id="binding")

    registry.register_binding(first)
    registry.register_binding(second, replace=True)

    assert list(registry.iter_bindings()) == [second]


def test_update_binding_changes_sequence() -> None:
    registry = KeymapRegistry()
    registry.register_action(make_action())
    binding = make_binding(binding_id="binding")
    registry.register_binding(binding)

    updated = registry.update_binding(
        "binding", sequence=make_sequence("d", "d"), description="delete line"
    )

    assert updated.sequence.tokens == ("d", "d")
    assert updated.description == "delete line"


def test_unregister_binding() -> None:
    registry = KeymapRegistry()
    registry.register_action(make_action())
    binding = make_binding(binding_id="binding")
    registry.register_binding(binding)

    removed = registry.unregister_binding("binding")

    assert removed == binding
    assert registry.stats().binding_count == 0


def test_load_default_keymaps_timeout_override() -> None:
    registry = KeymapRegistry()

    load_default_keymaps(registry, default_sequence_timeout_ms=1500)

    binding = registry.get_binding("normal.enter_insert")
    assert binding.sequence.timeout_ms == 1500


def test_load_default_keymaps_include_filters() -> None:
    registry = KeymapRegistry()

    load_default_keymaps(
        registry,
        include_actions=("core.enter_insert",),
        include_bindings=("normal.enter_insert",),
    )

    assert registry.stats().binding_count == 1
    assert registry.get_binding("normal.enter_insert").action_id == "core.enter_insert"


def test_load_default_keymaps_per_mode_override() -> None:
    registry = KeymapRegistry()
    custom_binding = Binding(
        id="normal.enter_insert",
        mode="normal",
        sequence=KeySequence.from_strings("a"),
        action_id="core.enter_insert",
    )

    load_default_keymaps(
        registry,
        per_mode_overrides={"normal": (custom_binding,)},
    )

    binding = registry.get_binding("normal.enter_insert")
    assert binding.sequence.tokens == ("a",)


def test_registry_override_sequence_timeouts_mode_scope() -> None:
    registry = KeymapRegistry()
    load_default_keymaps(registry)
    before = registry.revision()

    registry.override_sequence_timeouts(timeout_ms=2200, mode="normal")

    assert registry.get_binding("normal.enter_insert").sequence.timeout_ms == 2200
    assert registry.revision() == before + 1


def test_registry_override_sequence_timeouts_binding_subset() -> None:
    registry = KeymapRegistry()
    load_default_keymaps(registry)

    registry.override_sequence_timeouts(
        timeout_ms=1800,
        binding_ids=["insert.exit_escape"],
    )

    assert registry.get_binding("insert.exit_escape").sequence.timeout_ms == 1800
