# TV2MT5 Bridge Architecture (Phase 1 Baseline)

## Goals
- Windows-only desktop product with local reliability and clear operator diagnostics.
- Strict separation between UI and trading execution runtime.
- Crash-safe storage and queue-first execution model.
- BYO ngrok account and user-owned stable public webhook URL.

## Process Model
- **Process 1: Background Agent**
  - FastAPI local receiver on `127.0.0.1:<port>`.
  - Alert authentication, validation, persistence, dedupe, queueing (Phase 2+).
  - Sequential queue worker and MT5 execution (Phase 3+).
  - ngrok child-process supervision (Phase 4+).
  - License enforcement gate for live execution (Phase 6+).
- **Process 2: Desktop UI**
  - PySide6 operator console.
  - Setup flows for license, MT5, ngrok, webhook token/secret.
  - Live log and diagnostics views (Phase 5+).
  - Never sends orders directly to MT5.

## Reliability Boundaries
- Webhook handler returns quickly after auth + persistence + enqueue.
- No MT5 execution in HTTP request path.
- SQLite in WAL mode for durability and concurrency.
- Queue is durable and strictly ordered by insert sequence.
- Worker is single-consumer in v1.

## Security Boundaries
- Listener binds to loopback only.
- Public exposure only through user-managed ngrok tunnel.
- Dual auth model for webhook:
  1. Secret path token.
  2. Shared secret in JSON payload.
- Sensitive data stored via pluggable secret store; Windows implementation uses OS secure storage in later phases.

## Observability
- Structured JSON machine logs.
- Human-readable UI event timeline.
- Correlation across all pipeline stages using `correlation_id`.
- Diagnostics exports include config snapshot (masked), health status, and recent logs.

## Data Flow (Target)
1. TradingView sends HTTPS request to user's ngrok URL.
2. ngrok forwards to local `127.0.0.1:<port>/webhook/<token>`.
3. Agent authenticates and validates payload.
4. Agent persists raw + normalized payload and enqueues.
5. Worker claims next queue item atomically.
6. Worker executes MT5 action and persists result.
7. UI reads state/log tables and renders operator diagnostics.
