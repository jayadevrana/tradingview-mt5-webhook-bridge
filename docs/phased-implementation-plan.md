# Phased Implementation Plan

## Phase 1 (This delivery)
- Repository scaffold and module boundaries.
- Typed domain enums and interface contracts.
- SQLite schema models + migration SQL baseline.
- Structured logging foundation.
- Config layer and app data paths.
- Minimal background agent + UI shell bootstrap.
- Test harness and first reliability tests (queue order + config).

## Phase 2
- Strict webhook schema (Pydantic v2) and normalization.
- Path-token + shared-secret authentication.
- Raw payload persistence and dedupe by `event_id`.
- Queue insertion and immediate-ack webhook behavior.

## Phase 3
- MT5 adapter implementation using official package.
- Symbol resolution + alias mapping + tradability checks.
- Command execution flows (open/close/reverse).
- Execution result persistence and state transitions.

## Phase 4
- ngrok configuration validation and process supervision.
- Public URL/domain health checks and end-to-end tunnel test.
- Restart with bounded backoff and diagnostics.

## Phase 5
- Full PySide6 screens (Dashboard, Logs, Settings, Diagnostics).
- Live event stream and searchable log views.
- Export support (CSV/JSON/support bundle).

## Phase 6
- License activation + machine binding + local cache/offline grace.
- Unlicensed execution gating.
- Mock activation server and production API contract doc.

## Phase 7
- Packaging and installer hardening (PyInstaller + installer).
- Windows service/auto-start option.
- Final acceptance test automation and operational runbooks.
