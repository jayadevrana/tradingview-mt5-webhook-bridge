PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  correlation_id TEXT NOT NULL UNIQUE,
  event_id TEXT NOT NULL UNIQUE,
  received_at TEXT NOT NULL,
  source_ip TEXT NULL,
  auth_path_ok INTEGER NOT NULL,
  auth_secret_ok INTEGER NOT NULL,
  schema_valid INTEGER NOT NULL,
  dedupe_key TEXT NOT NULL,
  is_duplicate INTEGER NOT NULL DEFAULT 0,
  raw_payload_json TEXT NOT NULL,
  normalized_payload_json TEXT NULL,
  validation_error TEXT NULL
);

CREATE INDEX IF NOT EXISTS ix_alerts_event_id_received_at
ON alerts(event_id, received_at DESC);

CREATE INDEX IF NOT EXISTS ix_alerts_received_at
ON alerts(received_at DESC);

CREATE TABLE IF NOT EXISTS webhook_receipts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  correlation_id TEXT NOT NULL UNIQUE,
  event_id TEXT NULL,
  received_at TEXT NOT NULL,
  source_ip TEXT NULL,
  auth_path_ok INTEGER NOT NULL,
  auth_secret_ok INTEGER NOT NULL,
  schema_valid INTEGER NOT NULL,
  intake_status TEXT NOT NULL,
  raw_payload_json TEXT NOT NULL,
  normalized_payload_json TEXT NULL,
  validation_error TEXT NULL
);

CREATE INDEX IF NOT EXISTS ix_webhook_receipts_event_id_received_at
ON webhook_receipts(event_id, received_at DESC);

CREATE TABLE IF NOT EXISTS queue_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  correlation_id TEXT NOT NULL UNIQUE,
  event_id TEXT NOT NULL,
  state TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  claimed_at TEXT NULL,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  last_error TEXT NULL
);

CREATE INDEX IF NOT EXISTS ix_queue_items_state_created
ON queue_items(state, created_at, id);

CREATE INDEX IF NOT EXISTS ix_queue_items_event_id
ON queue_items(event_id);

CREATE TABLE IF NOT EXISTS queue_transitions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  queue_item_id INTEGER NOT NULL,
  from_state TEXT NULL,
  to_state TEXT NOT NULL,
  reason TEXT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(queue_item_id) REFERENCES queue_items(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_queue_transitions_queue_item_id_created
ON queue_transitions(queue_item_id, created_at);

CREATE TABLE IF NOT EXISTS execution_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  queue_item_id INTEGER NOT NULL,
  attempt_no INTEGER NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT NULL,
  mt5_request_json TEXT NULL,
  mt5_response_json TEXT NULL,
  retcode INTEGER NULL,
  last_error TEXT NULL,
  outcome TEXT NOT NULL,
  summary TEXT NULL,
  FOREIGN KEY(queue_item_id) REFERENCES queue_items(id) ON DELETE CASCADE,
  CONSTRAINT uq_execution_attempt UNIQUE (queue_item_id, attempt_no)
);

CREATE INDEX IF NOT EXISTS ix_execution_attempts_queue_item_id_attempt_no
ON execution_attempts(queue_item_id, attempt_no);

CREATE TABLE IF NOT EXISTS app_kv (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
