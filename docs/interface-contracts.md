# Interface Contracts

## Queue Repository
- `enqueue(...) -> QueueItemRef`
- `claim_next(now_utc) -> QueueItemRef | None`
- `transition(queue_id, to_state, reason)`
- `get_by_correlation(correlation_id) -> QueueItemRef | None`
- `mark_result(queue_id, outcome, details)`

Contract:
- `claim_next` must be atomic.
- Item claim order is insertion order (`id ASC`) for queued state.
- Writes are durable before webhook returns success.

## MT5 Adapter
- `initialize(config) -> MT5ConnectionResult`
- `detect_terminals() -> list[TerminalCandidate]`
- `select_terminal(...) -> TerminalSelection`
- `account_info() -> MT5AccountInfo`
- `symbol_resolve(symbol, alias_map) -> SymbolResolution`
- `order_check_send(request) -> MT5OrderFlowResult`
- `shutdown()`

Contract:
- Must wrap official `MetaTrader5` Python package only.
- No hidden retries that can cause duplicate executions.
- Response must include request snapshot and broker/retcode info.

## ngrok Supervisor
- `start(config) -> NgrokStartResult`
- `health() -> NgrokHealth`
- `current_public_url() -> str | None`
- `stop(graceful_timeout_s) -> None`

Contract:
- Supervisor owns process lifecycle and log capture.
- Exposes crash reason and last health timestamp.

## License Service
- `activate(license_key, machine_fingerprint) -> LicenseState`
- `refresh() -> LicenseState`
- `current_state() -> LicenseState`

Contract:
- Swappable backend transport.
- Supports local cache and offline grace behavior.
- Exposes clear states (`active`, `invalid`, `expired`, etc.).

## Secret Store
- `set_secret(namespace, key, value)`
- `get_secret(namespace, key) -> str | None`
- `delete_secret(namespace, key)`

Contract:
- App code never logs secret values.
- Windows implementation uses OS secure storage.

## Health Service
- `collect() -> HealthSnapshot`

Contract:
- Includes listener, ngrok, MT5, DB, and license components.
- Returns actionable message for each degraded component.
