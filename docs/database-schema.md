# Database Schema (Phase 1 Foundation)

SQLite with WAL mode.

## `alerts`
Stores raw ingress plus normalized command metadata.

Columns:
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `correlation_id` TEXT NOT NULL UNIQUE
- `event_id` TEXT NOT NULL UNIQUE
- `received_at` TEXT NOT NULL
- `source_ip` TEXT NULL
- `auth_path_ok` INTEGER NOT NULL
- `auth_secret_ok` INTEGER NOT NULL
- `schema_valid` INTEGER NOT NULL
- `dedupe_key` TEXT NOT NULL
- `is_duplicate` INTEGER NOT NULL DEFAULT 0
- `raw_payload_json` TEXT NOT NULL
- `normalized_payload_json` TEXT NULL
- `validation_error` TEXT NULL

Indexes:
- `ix_alerts_event_id_received_at(event_id, received_at DESC)`
- `ix_alerts_received_at(received_at DESC)`

## `webhook_receipts`
Stores every incoming webhook request (including duplicates and failures).

Columns:
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `correlation_id` TEXT NOT NULL UNIQUE
- `event_id` TEXT NULL
- `received_at` TEXT NOT NULL
- `source_ip` TEXT NULL
- `auth_path_ok` INTEGER NOT NULL
- `auth_secret_ok` INTEGER NOT NULL
- `schema_valid` INTEGER NOT NULL
- `intake_status` TEXT NOT NULL
- `raw_payload_json` TEXT NOT NULL
- `normalized_payload_json` TEXT NULL
- `validation_error` TEXT NULL

## `queue_items`
Durable execution queue with ordered processing.

Columns:
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `correlation_id` TEXT NOT NULL UNIQUE
- `event_id` TEXT NOT NULL
- `state` TEXT NOT NULL
- `created_at` TEXT NOT NULL
- `updated_at` TEXT NOT NULL
- `claimed_at` TEXT NULL
- `attempt_count` INTEGER NOT NULL DEFAULT 0
- `last_error` TEXT NULL

Indexes:
- `ix_queue_items_state_created(state, created_at, id)`
- `ix_queue_items_event_id(event_id)`

## `queue_transitions`
Audit trail for queue state machine changes.

Columns:
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `queue_item_id` INTEGER NOT NULL REFERENCES queue_items(id) ON DELETE CASCADE
- `from_state` TEXT NULL
- `to_state` TEXT NOT NULL
- `reason` TEXT NULL
- `created_at` TEXT NOT NULL

Index:
- `ix_queue_transitions_queue_item_id_created(queue_item_id, created_at)`

## `execution_attempts`
Execution-level result snapshots per queue attempt.

Columns:
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `queue_item_id` INTEGER NOT NULL REFERENCES queue_items(id) ON DELETE CASCADE
- `attempt_no` INTEGER NOT NULL
- `started_at` TEXT NOT NULL
- `ended_at` TEXT NULL
- `mt5_request_json` TEXT NULL
- `mt5_response_json` TEXT NULL
- `retcode` INTEGER NULL
- `last_error` TEXT NULL
- `outcome` TEXT NOT NULL
- `summary` TEXT NULL

Index:
- `ix_execution_attempts_queue_item_id_attempt_no(queue_item_id, attempt_no)`

## `app_kv`
Small key-value state store for lightweight runtime metadata.

Columns:
- `key` TEXT PRIMARY KEY
- `value` TEXT NOT NULL
- `updated_at` TEXT NOT NULL
