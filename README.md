# TV2MT5 Bridge

Production-oriented Windows desktop bridge for TradingView webhook alerts to MetaTrader 5, with a split architecture:
- Background Agent process for webhook intake, queueing, and execution pipeline.
- Desktop UI process for setup, diagnostics, and observability.

This repository currently delivers **Phase 3** foundations:
- project scaffold and typed contracts
- SQLite/WAL data foundation and migration baseline
- structured JSON logging
- process bootstrap (`UI` + separate `agent` process)
- queue repository with deterministic ordering claim behavior
- strict webhook schema validation and normalization
- dual-auth webhook intake (path token + payload secret)
- durable raw receipt persistence for every request
- dedupe by unique `event_id` with duplicate-ignore behavior
- MT5 adapter layer using the official `MetaTrader5` package interface
- command execution engine for `open_market`, `close_positions`, `close_all_symbol`, `close_all_positions`, `reverse_market`
- terminal discovery/selection model and manual login connection flow
- docs and initial tests

## Current Status
- Implemented: architecture foundation, webhook persistence/idempotency intake, MT5 command execution foundation, reliability scaffolding.
- Not implemented yet: ngrok supervision, full licensing backend, full UI screens, queue worker integration with MT5 executor.

## Quick Start (Developer)

1. Create a Python 3.11 environment.
2. Install dependencies:
   ```bash
   pip install -e .[dev]
   ```
3. Run desktop shell:
   ```bash
   python -m app.main
   ```
4. Run agent only:
   ```bash
   python -m app.main --agent
   ```
   Required env vars for non-default auth:
   - `TV2MT5_AGENT__ENDPOINT_TOKEN`
   - `TV2MT5_AGENT__PAYLOAD_SECRET`
5. Run tests:
   ```bash
   pytest
   ```

## Windows EXE Build (Scaffold)
Phase 1 includes a build scaffold script and spec:
- `scripts/build_windows_exe.ps1`
- `tv2mt5_bridge.spec`

Build is intended on **Windows 10/11 x64** with Python 3.11.

## Docs
- Architecture: `docs/architecture.md`
- Folder layout: `docs/folder-structure.md`
- DB schema: `docs/database-schema.md`
- Interface contracts: `docs/interface-contracts.md`
- Delivery phases: `docs/phased-implementation-plan.md`

## Notes
Trading automation is infrastructure, not financial advice. No profit guarantees. Test in dry-run/paper before going live.

## Author
Built by [Jayadev Rana](https://jayadevrana.in) — @bluealgocapital · [YouTube](https://www.youtube.com/@jayadevrana3657) · [GitHub](https://github.com/jayadevrana)

## License

MIT © 2026 [Jayadev Rana](https://jayadevrana.in). Free to use, modify and share: please keep the copyright notice and credit **Jayadev Rana** with a link back to this repository.
