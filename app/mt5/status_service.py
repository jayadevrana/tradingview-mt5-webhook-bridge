from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.domain.models import MT5ConnectionConfig
from app.mt5.adapter import OfficialMT5Adapter, StubMT5Adapter


class MT5StatusService:
    def __init__(self, adapter_factory: Callable[[], Any] | None = None) -> None:
        self._adapter_factory = adapter_factory or self._default_adapter_factory

    def snapshot(self) -> dict[str, Any]:
        adapter_name = "official"
        try:
            adapter = self._adapter_factory()
        except Exception as exc:
            return {
                "ok": False,
                "adapter": "none",
                "message": f"MT5 adapter initialization failed: {exc}",
                "detected_terminals": [],
                "selection_status": "error",
                "selected_terminal_pid": None,
                "account_login": None,
                "account_server": None,
                "account_name": None,
            }

        if isinstance(adapter, StubMT5Adapter):
            adapter_name = "stub"

        try:
            candidates = adapter.detect_terminals()
            selection = adapter.select_terminal(candidates=candidates)
            selected = selection.selected
            base_payload: dict[str, Any] = {
                "ok": True,
                "adapter": adapter_name,
                "message": selection.message,
                "detected_terminals": [
                    {
                        "pid": item.pid,
                        "name": item.name,
                        "path": item.executable_path,
                    }
                    for item in candidates
                ],
                "selection_status": selection.status,
                "selected_terminal_pid": selected.pid if selected else None,
                "selected_terminal_path": selected.executable_path if selected else None,
                "account_login": None,
                "account_server": None,
                "account_name": None,
                "connected": False,
                "last_error": None,
            }
            if selected is None:
                return base_payload

            config = MT5ConnectionConfig(terminal_path=selected.executable_path)
            connection = adapter.initialize(config)
            base_payload["connected"] = connection.connected
            base_payload["message"] = connection.message
            base_payload["last_error"] = connection.last_error

            account = connection.account_info or {}
            if isinstance(account, dict):
                base_payload["account_login"] = account.get("login")
                base_payload["account_server"] = account.get("server")
                base_payload["account_name"] = account.get("name")
            adapter.shutdown()
            return base_payload
        except Exception as exc:
            return {
                "ok": False,
                "adapter": adapter_name,
                "message": str(exc),
                "detected_terminals": [],
                "selection_status": "error",
                "selected_terminal_pid": None,
                "account_login": None,
                "account_server": None,
                "account_name": None,
            }

    @staticmethod
    def _default_adapter_factory() -> Any:
        try:
            return OfficialMT5Adapter()
        except Exception:
            return StubMT5Adapter()
