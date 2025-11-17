from textual import events
from textual.binding import Binding
from textual.containers import Horizontal
from textual.app import App, ComposeResult
from textual.widgets import TextArea


from src.editor import VimEditor


class AutoComplete(TextArea):
    """A subclass of TextArea with parenthesis-closing functionality."""

    def _on_key(self, event: events.Key) -> None:
        bracket_quote_pair = {"(": ")", "{": "}", "[": "]", '"': '"', "'": "'"}
        if event.character in bracket_quote_pair.keys():
            self.insert(event.character + bracket_quote_pair[event.character])
            self.move_cursor_relative(columns=-1)
            event.prevent_default()


class CustomTextArea(AutoComplete, VimEditor):
    pass


class Tusk(App):
    BINDINGS = [
        Binding("ctrl+shift+q", "command_palette", "Command palette"),
    ]

    CSS = """
Screen {
    layout: horizontal;
}

#input-box {
    width: 100%;
    height: 100%;
    border: blank #0C0C0C;
    background: #0C0C0C;
    color: #d4d4d4;
}
"""

    def __init__(self, markdown: str = "") -> None:
        self.markdown = markdown
        super().__init__()

    def compose(self) -> ComposeResult:
        input_box = CustomTextArea(
            show_line_numbers=True,
            id="input-box",
            language="go",
            tab_behavior="indent",
            theme="dracula",
        )

        yield Horizontal(input_box)


if __name__ == "__main__":
    app = Tusk()
    app.run()
