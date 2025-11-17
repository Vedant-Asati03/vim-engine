# Vim Engine (WIP)

This repository hosts a UI-agnostic Vim-style editing engine that can be embedded
into any text widget. The previous Textual-focused implementation now lives under
`legacy/current` for reference while we rebuild the core from the ground up.

## Roadmap

1. **Buffer + Undo Model** – standalone text buffer with cursor state, registers,
   and linear undo history.
2. **Mode / Operator Pipeline** – mode manager, operator contexts, and command
   sequencing independent of UI bindings.
3. **Configurable Keymaps** – data-driven bindings with runtime overrides and
   extension points for host applications.
4. **Macro & Register Services** – persistence hooks for registers, command
   history, and search patterns.
5. **Text Objects** – shared selectors (word, paragraph, block) powering motions
   and operators alike.
6. **Host Adapter Protocols** – small surface area every UI must expose plus
   first-party adapters for Textual and Ratatui.
7. **Testing & Tooling** – `uv` powered workflow with pytest + ruff coverage.

Stay tuned as each milestone lands; contributions and design feedback are welcome.