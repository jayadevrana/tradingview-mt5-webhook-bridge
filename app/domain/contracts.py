from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from app.domain.enums import QueueState
from app.domain.models import (
    LicenseState,
    MT5ConnectionConfig,
    MT5ConnectionResult,
    MT5ExecutionResult,
    MT5OrderFlowResult,
    QueueItemRef,
    SymbolResolution,
    TerminalCandidate,
    TerminalSelection,
)


class QueueRepository(Protocol):
    def enqueue(self, correlation_id: str, event_id: str, created_at: datetime) -> QueueItemRef:
        ...

    def claim_next(self, now_utc: datetime) -> QueueItemRef | None:
        ...

    def transition(self, queue_item_id: int, to_state: QueueState, reason: str | None = None) -> None:
        ...


class MT5Adapter(Protocol):
    def initialize(self, config: MT5ConnectionConfig) -> MT5ConnectionResult:
        ...

    def account_info(self) -> dict[str, Any]:
        ...

    def detect_terminals(self) -> list[TerminalCandidate]:
        ...

    def select_terminal(
        self,
        candidates: list[TerminalCandidate],
        preferred_pid: int | None = None,
        preferred_path: str | None = None,
    ) -> TerminalSelection:
        ...

    def order_check_send(self, request: dict[str, Any]) -> MT5OrderFlowResult:
        ...

    def symbol_resolve(self, symbol: str, alias_map: dict[str, str]) -> SymbolResolution:
        ...

    def execute(self, command: dict[str, Any], correlation_id: str) -> MT5ExecutionResult:
        ...

    def shutdown(self) -> None:
        ...


class NgrokSupervisor(Protocol):
    def start(self, config: dict[str, Any]) -> bool:
        ...

    def stop(self, graceful_timeout_s: float = 5.0) -> None:
        ...

    def health(self) -> dict[str, Any]:
        ...

    def current_public_url(self) -> str | None:
        ...


class LicenseService(Protocol):
    def activate(self, license_key: str, machine_fingerprint: str) -> LicenseState:
        ...

    def refresh(self) -> LicenseState:
        ...

    def current_state(self) -> LicenseState:
        ...


class SecretStore(Protocol):
    def set_secret(self, namespace: str, key: str, value: str) -> None:
        ...

    def get_secret(self, namespace: str, key: str) -> str | None:
        ...

    def delete_secret(self, namespace: str, key: str) -> None:
        ...
