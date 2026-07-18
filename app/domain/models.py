from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.domain.enums import QueueState


@dataclass(frozen=True)
class QueueItemRef:
    queue_item_id: int
    correlation_id: str
    event_id: str
    state: QueueState
    created_at: datetime
    attempt_count: int


@dataclass(frozen=True)
class SymbolResolution:
    requested: str
    resolved: str | None
    source: str
    notes: str | None = None
    suggestions: list[str] | None = None


@dataclass(frozen=True)
class TerminalCandidate:
    pid: int
    name: str
    executable_path: str | None
    cmdline: list[str]


@dataclass(frozen=True)
class TerminalSelection:
    status: str
    selected: TerminalCandidate | None
    candidates: list[TerminalCandidate]
    message: str


@dataclass(frozen=True)
class MT5ConnectionConfig:
    terminal_path: str | None = None
    login: int | None = None
    password: str | None = None
    server: str | None = None
    timeout_ms: int = 60000
    portable: bool = False


@dataclass(frozen=True)
class MT5ConnectionResult:
    connected: bool
    message: str
    last_error: str | None = None
    account_info: dict[str, Any] | None = None
    terminal_info: dict[str, Any] | None = None


@dataclass(frozen=True)
class MT5OrderFlowResult:
    ok: bool
    stage: str
    message: str
    retcode: int | None = None
    last_error: str | None = None
    request_snapshot: dict[str, Any] | None = None
    check_snapshot: dict[str, Any] | None = None
    send_snapshot: dict[str, Any] | None = None


@dataclass(frozen=True)
class MT5ExecutionResult:
    ok: bool
    summary: str
    command: str | None = None
    correlation_id: str | None = None
    resolved_symbol: str | None = None
    retcode: int | None = None
    last_error: str | None = None
    request_snapshot: dict[str, Any] | None = None
    response_snapshot: dict[str, Any] | None = None
    actions: list[dict[str, Any]] | None = None


@dataclass(frozen=True)
class LicenseState:
    status: str
    message: str
    valid_until: datetime | None = None
    offline_grace_until: datetime | None = None
