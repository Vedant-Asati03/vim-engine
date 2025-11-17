from textual.events import Key
from typing import Optional, List, Dict, Any
from datetime import datetime


class MacroEvent:
    """Simulates a Key event for macro playback."""

    def __init__(self, key: str):
        self.key = key
        self.character = key
        self.is_printable = len(key) == 1

    def prevent_default(self) -> None:
        """Simulate prevent_default() method."""
        pass


class MacroRecorder:
    """Handles recording and playing back vim macros."""

    def __init__(self, editor=None):
        self.recording_macro: Optional[str] = None
        self.macros: Dict[str, List[str]] = {}
        self.last_played: Optional[str] = None
        self.recording_keys: List[str] = []
        self.editor = editor
        self.recorded_macros: Dict[str, List[datetime]] = {}
        self.temp_sequence = ""
        self.current_command = ""

    def start_recording(self, register: str) -> None:
        """Start recording keys to the specified macro register."""
        self.recording_macro = register
        self.recording_keys = []

    def stop_recording(self) -> None:
        """Stop recording and save the macro."""
        if self.recording_macro:
            self.macros[self.recording_macro] = self.recording_keys
            self.recording_macro = None
            self.recording_keys = []
            self.temp_sequence = ""

    def record_key(self, key: str) -> None:
        """Record a keypress in the current macro."""
        if not self.recording_macro or key in ["q", "@"]:
            return
        self.recording_keys.append(key)

    def play_macro(self, register: str) -> List[str]:
        """Play back a recorded macro."""
        if register == "@":
            if self.last_played and self.last_played in self.macros:
                register = self.last_played
            else:
                return []

        if register in self.macros:
            self.last_played = register
            if register not in self.recorded_macros:
                self.recorded_macros[register] = []
            self.recorded_macros[register].append(datetime.now())
            return self.macros[register]
        return []

    def get_macro_info(self) -> List[str]:
        """Get formatted info about recorded macros."""
        info = []
        for register, keys in self.macros.items():
            uses = len(self.recorded_macros.get(register, []))
            last_used = (
                self.recorded_macros.get(register, [])[-1].strftime("%H:%M:%S")
                if uses > 0
                else "Never"
            )
            info.append(
                f"@{register}: {len(keys)} keys, used {uses} times, last: {last_used}"
            )
        return sorted(info)

    def handle_q_press(self) -> None:
        """Handle q press for macro recording."""
        if self.recording_macro:
            self.stop_recording()
            self.editor.reset_sequence()
            self.editor.enter_normal_mode()
        else:

            def on_register(event):
                register = event.key
                if register.isalpha():  # Only allow letter registers
                    self.start_recording(register)
                    self.editor.border_subtitle = f"Recording @{register}"
                self.editor.reset_sequence()

            self.editor.capture_next_key(on_register)

    def handle_at_press(self) -> None:
        """Handle @ press for macro playback."""

        def on_register(event):
            register = event.key
            if register == "@":
                register = self.last_played

            if register and register in self.macros:
                keys = self.play_macro(register)
                for key in keys:
                    # Send each key as a separate event
                    self.editor.handle_mode_switch(MacroEvent(key))
                    # Important: Wait for command to complete
                    self.editor.reset_sequence()
            self.editor.reset_sequence()

        self.editor.capture_next_key(on_register)
