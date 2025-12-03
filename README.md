![logo](./assets/logo.png)

# Vim Engine

> A UI-agnostic Vim editing core with first-party adapters for Textual (and soon Ratatui).

Vim Engine provides the data structures, modes, keymaps, and telemetry needed to bolt classic Vim behavior onto any terminal UI. The library is intentionally decoupled from rendering so you can embed it in Textual, Ratatui, TUI frameworks, or even headless automation.

## Highlights

- **Modern buffer model** – Document snapshots, cursor/selection state, registers, undo timeline, and transactions instrumented via Telelog.
- **Mode pipeline** – Normal, Insert, Visual, and Command modes coordinated by `ModeManager`, including timeouts, pending operators, and Ex command bus events.
- **Data-driven keymaps** – Bundled bindings for the common Vim verbs and motions with runtime overrides, custom actions, and per-mode sequencing.
- **Adapter hooks** – `TextualVimAdapter` turns engine events into UI callbacks; a Ratatui adapter is under active development so Rust-inspired TUIs get the same ergonomics.
- **Live telemetry** – Optional TCP stream emits every key/result/event so you can observe behavior from another terminal or ingest it into external tooling.

## Requirements & Installation

- Python **3.13+**
- `uv` (recommended) or pip/poetry for dependency management

Clone and install in editable mode:

```bash
git clone https://github.com/Vedant-Asati03/vim-engine.git
cd vim-engine
uv pip install -e .
```

To hack on the demos and tooling:

```bash
uv pip install -e .[demo,dev]
```

`demo` pulls in Textual, while `dev` adds pytest, ruff, and other contributor utilities.

## Try the Textual Demo

```bash
# Install demo extras if you skipped them earlier
uv pip install textual

# Run the sample Textual host
uv run python -m vim_engine.adapters.textual.app --log-port 8765

# (Optional) Observe the live feed from another terminal
nc 127.0.0.1 8765
```

Use standard Vim keystrokes: `i` to enter insert mode, `<Esc>` to return to normal, `:` to enter command mode, etc. Quit with `Ctrl+C` or `Ctrl+Q`. Pass `--log-port 0` for an ephemeral port or `--no-log-server` to disable telemetry.

## Embedding in Your App

You can integrate at three levels:

1. **Drop-in Textual host** – Reuse `vim_engine.adapters.textual.app.VimEngineApp` if you just need a ready-made editor window.
2. **Adapter hooks** – Instantiate `TextualVimAdapter` (or the upcoming Ratatui equivalent) inside your UI, supply callbacks for `update_buffer`, `update_status`, and `show_command`, then forward key events through `handle_textual_key`.
3. **Bare engine** – Wire `ModeManager`, `Buffer`, and `KeymapRegistry` directly for maximum control.

The adapter API was designed so integrations stay minimal: provide a buffer-rendering callback, a status/command-line sink, and a key forwarding function. Everything else—modes, operators, macros, Ex commands—lives inside the engine.

## Telemetry & Logging

`vim_engine.logging.NetworkLogStreamer` exposes a lightweight TCP server that mirrors every key dispatch, mode result, timeout, and bus event. Hosts can reuse it to pipe structured logs into another TUI, a dashboard, or automated tests. The Textual demo enables it by default; other adapters can opt in with just a few lines.

## Contributing & License

1. Fork the repo and create a feature branch.
2. Follow the development workflow above.
3. Open a PR describing the motivation, behavior, and testing.

Licensed under the MIT License. See [LICENSE](LICENSE) for details.
