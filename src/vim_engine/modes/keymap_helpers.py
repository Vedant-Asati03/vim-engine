"""Helper utilities for keymap-driven modes."""

from __future__ import annotations

from typing import Mapping, MutableMapping, cast

from vim_engine.keymaps import KeymapResolver

from .base_mode import KeyInput, ModeContext


def key_to_token(key: KeyInput) -> str:
    if key.modifiers:
        modifier = "+".join(key.modifiers)
        return f"{modifier}+{key.key}"
    return key.key


def require_keymap_resolver(context: ModeContext) -> KeymapResolver:
    resolver = context.extras.get("keymap_resolver")
    if not isinstance(resolver, KeymapResolver):
        raise RuntimeError("ModeContext.extras missing 'keymap_resolver'")
    return resolver


def keymap_flag_context(context: ModeContext) -> Mapping[str, bool]:
    flags = context.extras.setdefault("keymap_flags", {})
    return cast(Mapping[str, bool], flags)


def update_flag(context: ModeContext, key: str, value: bool) -> None:
    flags = cast(
        MutableMapping[str, bool], context.extras.setdefault("keymap_flags", {})
    )
    flags[key] = value


__all__ = [
    "key_to_token",
    "require_keymap_resolver",
    "keymap_flag_context",
    "update_flag",
]
