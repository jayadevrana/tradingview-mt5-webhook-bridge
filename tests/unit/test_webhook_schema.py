from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.webhook.schema import TradingViewWebhookAlert


def _base_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "event_id": "evt-schema-001",
        "sent_at": "2026-03-09T10:30:00Z",
        "source": "tradingview",
        "command": "open_market",
        "account_scope": "primary",
        "symbol": "xauusd",
        "secret": "shared-secret",
        "options": {"side": "buy", "quantity_lots": 0.01},
    }


def test_schema_accepts_valid_open_market() -> None:
    alert = TradingViewWebhookAlert.model_validate(_base_payload())
    normalized = alert.normalized_payload()
    assert normalized["symbol"] == "XAUUSD"
    assert normalized["secret"] == "***"


def test_schema_requires_symbol_for_open_market() -> None:
    payload = _base_payload()
    payload.pop("symbol")
    with pytest.raises(ValidationError):
        TradingViewWebhookAlert.model_validate(payload)


def test_schema_requires_lots_for_open_market() -> None:
    payload = _base_payload()
    payload["options"] = {"side": "buy"}
    with pytest.raises(ValidationError):
        TradingViewWebhookAlert.model_validate(payload)


def test_schema_rejects_symbol_for_close_all_positions() -> None:
    payload = _base_payload()
    payload["command"] = "close_all_positions"
    payload["options"] = {}
    with pytest.raises(ValidationError):
        TradingViewWebhookAlert.model_validate(payload)


def test_schema_rejects_non_positive_lots() -> None:
    payload = _base_payload()
    payload["options"] = {"side": "buy", "quantity_lots": 0}
    with pytest.raises(ValidationError):
        TradingViewWebhookAlert.model_validate(payload)
