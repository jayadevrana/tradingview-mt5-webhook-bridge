from __future__ import annotations

from enum import Enum

try:
    from enum import StrEnum
except ImportError:  # pragma: no cover - compatibility fallback for non-3.11 environments
    class StrEnum(str, Enum):
        pass


class QueueState(StrEnum):
    RECEIVED = "received"
    VALIDATED = "validated"
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_PERMANENT = "failed_permanent"
    DUPLICATE_IGNORED = "duplicate_ignored"
    CANCELLED = "cancelled"


class CommandType(StrEnum):
    OPEN_MARKET = "open_market"
    CLOSE_POSITIONS = "close_positions"
    CLOSE_ALL_SYMBOL = "close_all_symbol"
    CLOSE_ALL_POSITIONS = "close_all_positions"
    REVERSE_MARKET = "reverse_market"


class LicenseStatus(StrEnum):
    ACTIVE = "active"
    INVALID = "invalid"
    EXPIRED = "expired"
    REVOKED = "revoked"
    MACHINE_LIMIT_REACHED = "machine_limit_reached"
