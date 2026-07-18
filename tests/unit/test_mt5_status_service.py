from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.models import MT5ConnectionResult, TerminalCandidate, TerminalSelection
from app.mt5.status_service import MT5StatusService


@dataclass
class FakeAdapter:
    def detect_terminals(self) -> list[TerminalCandidate]:
        return [
            TerminalCandidate(
                pid=9999,
                name="terminal64.exe",
                executable_path="C:\\MetaTrader\\terminal64.exe",
                cmdline=["terminal64.exe"],
            )
        ]

    def select_terminal(
        self,
        candidates: list[TerminalCandidate],
        preferred_pid: int | None = None,
        preferred_path: str | None = None,
    ) -> TerminalSelection:
        _ = preferred_pid
        _ = preferred_path
        return TerminalSelection(
            status="selected",
            selected=candidates[0],
            candidates=candidates,
            message="selected",
        )

    def initialize(self, config) -> MT5ConnectionResult:  # type: ignore[no-untyped-def]
        _ = config
        return MT5ConnectionResult(
            connected=True,
            message="connected",
            account_info={"login": 123456, "server": "Broker-Demo", "name": "Demo Account"},
        )

    def shutdown(self) -> None:
        return None


def test_status_snapshot_includes_pid_login_server() -> None:
    service = MT5StatusService(adapter_factory=lambda: FakeAdapter())
    payload = service.snapshot()
    assert payload["ok"] is True
    assert payload["selected_terminal_pid"] == 9999
    assert payload["account_login"] == 123456
    assert payload["account_server"] == "Broker-Demo"
