from __future__ import annotations

from vim_engine.keymaps import (
    ActionRef,
    Binding,
    KeySequence,
    KeymapRegistry,
    KeymapResolver,
    WhenClause,
)


def make_action(action_id: str) -> ActionRef:
    return ActionRef(id=action_id, handler=lambda *args, **kwargs: None)


def make_binding(
    binding_id: str,
    *,
    mode: str = "normal",
    keys: tuple[str, ...] = ("g", "g"),
    action_id: str = "core.test",
    when: tuple[WhenClause, ...] = (),
    priority: int = 0,
    timeout_ms: int = 1000,
) -> Binding:
    return Binding(
        id=binding_id,
        mode=mode,
        sequence=KeySequence.from_strings(*keys, timeout_ms=timeout_ms),
        action_id=action_id,
        when=when,
        priority=priority,
    )


def build_registry(bindings: list[Binding]) -> KeymapRegistry:
    registry = KeymapRegistry()
    action_ids = {binding.action_id for binding in bindings}
    for action_id in action_ids:
        registry.register_action(make_action(action_id))
    for binding in bindings:
        registry.register_binding(binding)
    return registry


def test_resolver_matches_exact_sequence() -> None:
    binding = make_binding("normal.gg")
    registry = build_registry([binding])
    resolver = KeymapResolver(registry)

    result = resolver.resolve("normal", ("g", "g"))

    assert result.status == "match"
    assert result.match is not None
    assert result.match.binding.id == binding.id


def test_resolver_reports_pending_for_prefix() -> None:
    binding = make_binding("normal.gg")
    registry = build_registry([binding])
    resolver = KeymapResolver(registry)

    result = resolver.resolve("normal", ("g",))

    assert result.status == "pending"
    assert result.next_expected == ("g",)


def test_resolver_honors_when_clauses() -> None:
    gating = make_binding(
        "panel.gg",
        when=(WhenClause("panel_open"),),
        action_id="core.panel",
    )
    registry = build_registry([gating])
    resolver = KeymapResolver(registry)

    miss = resolver.resolve("normal", ("g", "g"), context={})
    assert miss.status == "miss"

    hit = resolver.resolve("normal", ("g", "g"), context={"panel_open": True})
    assert hit.status == "match"
    assert hit.match is not None
    assert hit.match.binding.id == gating.id


def test_resolver_pending_returns_timeout_hint() -> None:
    binding = make_binding("normal.gg", timeout_ms=1500)
    registry = build_registry([binding])
    resolver = KeymapResolver(registry)

    result = resolver.resolve("normal", ("g",))

    assert result.status == "pending"
    assert result.timeout_ms == 1500


def test_resolver_cache_refreshes_on_revision() -> None:
    registry = build_registry([])
    resolver = KeymapResolver(registry)

    miss = resolver.resolve("normal", ("x",))
    assert miss.status == "miss"

    new_binding = make_binding("normal.x", keys=("x",), action_id="core.x")
    registry.register_action(make_action("core.x"))
    registry.register_binding(new_binding)

    match = resolver.resolve("normal", ("x",))
    assert match.status == "match"
    assert match.match is not None
    assert match.match.binding.id == new_binding.id
