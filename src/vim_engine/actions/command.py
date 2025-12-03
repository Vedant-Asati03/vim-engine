"""Actions that evaluate Ex-style command lines."""

from __future__ import annotations

from functools import partial
from typing import Callable, Dict, List, MutableMapping, cast

from vim_engine.modes.base_mode import ModeContext, ModeResult

CommandHandler = Callable[[ModeContext, List[str]], ModeResult]


def _command_state(context: ModeContext) -> MutableMapping[str, object]:
    state = cast(
        MutableMapping[str, object], context.extras.setdefault("command_state", {})
    )
    state.setdefault("text", "")
    state.setdefault("history", [])
    return state


def submit_command_line(context: ModeContext, match) -> ModeResult:
    del match
    state = _command_state(context)
    raw = str(state.get("text", ""))
    text = raw.strip()
    context.bus.emit("command.submit", text)
    history = state.get("history")
    if isinstance(history, list):
        history.append(text)
    state["text"] = ""
    if not text:
        return ModeResult(consumed=True, switch_to="normal", status="command_empty")
    parts = text.split()
    command = parts[0]
    args = parts[1:]
    handler = _COMMAND_HANDLERS.get(command)
    if handler is None:
        return _unknown_command(context, command)
    return handler(context, args)


def _unknown_command(context: ModeContext, command: str) -> ModeResult:
    context.bus.emit("command.error", command)
    return ModeResult(
        consumed=True,
        switch_to="normal",
        status="command_error",
        message=command,
    )


def _handle_echo(context: ModeContext, args: List[str]) -> ModeResult:
    message = " ".join(args)
    context.bus.emit("command.echo", message)
    return ModeResult(
        consumed=True,
        switch_to="normal",
        status="command_echo",
        message=message,
    )


def _handle_write(
    context: ModeContext, args: List[str], *, force: bool = False
) -> ModeResult:
    _emit_write(context, args, force=force)
    status = "command_write_force" if force else "command_write"
    message = "write!" if force else "write"
    return ModeResult(
        consumed=True,
        switch_to="normal",
        status=status,
        message=message,
    )


def _handle_quit(
    context: ModeContext, args: List[str], *, force: bool = False
) -> ModeResult:
    _emit_quit(context, force=force)
    status = "command_quit_force" if force else "command_quit"
    message = "quit!" if force else "quit"
    return ModeResult(
        consumed=True,
        switch_to="normal",
        status=status,
        message=message,
    )


def _handle_wq(
    context: ModeContext, args: List[str], *, force: bool = False
) -> ModeResult:
    _emit_write(context, args, force=force)
    _emit_quit(context, force=force)
    status = "command_wq_force" if force else "command_wq"
    message = "wq!" if force else "wq"
    return ModeResult(
        consumed=True,
        switch_to="normal",
        status=status,
        message=message,
    )


def _handle_x(
    context: ModeContext, args: List[str], *, force: bool = False
) -> ModeResult:
    _emit_write(context, args, force=force)
    _emit_quit(context, force=force)
    status = "command_x_force" if force else "command_x"
    message = "x!" if force else "x"
    return ModeResult(
        consumed=True,
        switch_to="normal",
        status=status,
        message=message,
    )


def _handle_edit(
    context: ModeContext, args: List[str], *, force: bool = False
) -> ModeResult:
    _emit_edit(context, args, force=force)
    status = "command_edit_force" if force else "command_edit"
    message = "edit!" if force else "edit"
    return ModeResult(
        consumed=True,
        switch_to="normal",
        status=status,
        message=message,
    )


def _emit_write(context: ModeContext, args: List[str], *, force: bool) -> None:
    payload = {
        "force": force,
        "args": list(args),
        "snapshot": context.buffer.snapshot(),
    }
    context.bus.emit("command.write", payload)


def _emit_quit(context: ModeContext, *, force: bool) -> None:
    payload = {"force": force}
    context.bus.emit("command.quit", payload)


def _emit_edit(context: ModeContext, args: List[str], *, force: bool) -> None:
    payload = {
        "force": force,
        "args": list(args),
        "snapshot": context.buffer.snapshot(),
    }
    context.bus.emit("command.edit", payload)


_COMMAND_HANDLERS: Dict[str, CommandHandler] = {
    "echo": _handle_echo,
    "write": _handle_write,
    "w": _handle_write,
    "write!": partial(_handle_write, force=True),
    "w!": partial(_handle_write, force=True),
    "quit": _handle_quit,
    "q": _handle_quit,
    "quit!": partial(_handle_quit, force=True),
    "q!": partial(_handle_quit, force=True),
    "wq": _handle_wq,
    "wq!": partial(_handle_wq, force=True),
    "x": _handle_x,
    "x!": partial(_handle_x, force=True),
    "exit": _handle_x,
    "exit!": partial(_handle_x, force=True),
    "edit": _handle_edit,
    "e": _handle_edit,
    "edit!": partial(_handle_edit, force=True),
    "e!": partial(_handle_edit, force=True),
}


__all__ = ["submit_command_line"]
