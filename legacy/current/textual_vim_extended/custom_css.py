class ThemeManager:
    """Applies editor-specific theming without relying on inheritance."""

    def __init__(self, editor) -> None:
        self._editor = editor

    def apply(self) -> None:
        """Apply a consistent border theme to the attached editor widget."""
        styles = self._editor.styles
        styles.border = ("blank", "#0C0C0C")
        styles.border_title_align = "right"
        styles.border_title_color = "#F5F5F5"
        styles.border_title_background = "#3C3D37"
        styles.border_subtitle_align = "right"
        styles.border_subtitle_style = "bold"
