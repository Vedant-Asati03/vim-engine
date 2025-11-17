"""Shared helpers for configuring the editor when switching modes."""

from textual_vim_extended.config import MODE_CONFIGS, VimMode


class ModeState:
    """Applies mode-specific styling and state updates to the editor widget."""

    def __init__(self, editor) -> None:
        self._editor = editor

    def apply(self, mode: VimMode) -> None:
        config = MODE_CONFIGS[mode]
        editor = self._editor
        editor.mode = mode
        editor.read_only = config.read_only
        editor.can_focus = True
        editor.border_subtitle = config.subtitle
        editor.styles.border_subtitle_background = config.bg_color
