from __future__ import annotations

from typing import Any
from unittest.mock import Mock

from app.domain.models import MT5OrderFlowResult, SymbolResolution
from app.mt5.executor import MT5CommandExecutor


def _base_constants() -> dict[str, Any]:
    return {
        "ORDER_TYPE_BUY": 0,
        "ORDER_TYPE_SELL": 1,
        "TRADE_ACTION_DEAL": 10,
        "ORDER_TIME_GTC": 20,
        "ORDER_FILLING_RETURN": 30,
        "ORDER_FILLING_IOC": 31,
    }


def _build_adapter_mock() -> Mock:
    constants = _base_constants()
    adapter = Mock()
    adapter.account_info.return_value = {"login": 123}
    adapter.ensure_symbol_tradable.return_value = (True, "ok")
    adapter.symbol_tick.return_value = {"ask": 2500.0, "bid": 2499.5}
    adapter.positions.return_value = []
    adapter.get_constant.side_effect = lambda name, default=None: constants.get(name, default)
    adapter.symbol_resolve.return_value = SymbolResolution(
        requested="XAUUSD",
        resolved="XAUUSD.a",
        source="alias_map",
    )
    return adapter


def _flow_success(request: dict[str, Any]) -> MT5OrderFlowResult:
    return MT5OrderFlowResult(
        ok=True,
        stage="completed",
        message="ok",
        retcode=10009,
        request_snapshot=request.copy(),
        check_snapshot={"retcode": 10009},
        send_snapshot={"retcode": 10009},
    )


def test_open_market_uses_order_check_and_send_with_resolved_symbol() -> None:
    adapter = _build_adapter_mock()
    captured: list[dict[str, Any]] = []
    adapter.order_check_send.side_effect = lambda request: (captured.append(request.copy()) or _flow_success(request))

    executor = MT5CommandExecutor(adapter=adapter, alias_map={"XAUUSD": "XAUUSD.a"})
    result = executor.execute(
        {
            "command": "open_market",
            "symbol": "XAUUSD",
            "options": {"side": "buy", "quantity_lots": 0.02, "slippage_points": 15},
        },
        correlation_id="corr-open-01",
    )

    assert result.ok is True
    assert result.command == "open_market"
    assert result.resolved_symbol == "XAUUSD.a"
    assert len(captured) == 1
    assert captured[0]["symbol"] == "XAUUSD.a"
    assert captured[0]["volume"] == 0.02
    assert captured[0]["type"] == 0


def test_close_positions_partial_quantity_in_order() -> None:
    adapter = _build_adapter_mock()
    adapter.positions.return_value = [
        {"ticket": 11, "symbol": "XAUUSD.a", "type": 0, "volume": 1.0, "time": 100},
        {"ticket": 12, "symbol": "XAUUSD.a", "type": 0, "volume": 1.0, "time": 200},
    ]
    captured: list[dict[str, Any]] = []
    adapter.order_check_send.side_effect = lambda request: (captured.append(request.copy()) or _flow_success(request))

    executor = MT5CommandExecutor(adapter=adapter, alias_map={"XAUUSD": "XAUUSD.a"})
    result = executor.execute(
        {
            "command": "close_positions",
            "symbol": "XAUUSD",
            "options": {"quantity_lots": 1.5, "side_filter": "buy", "close_mode": "fifo"},
        },
        correlation_id="corr-close-01",
    )

    assert result.ok is True
    assert len(captured) == 2
    assert captured[0]["position"] == 11
    assert captured[0]["volume"] == 1.0
    assert captured[1]["position"] == 12
    assert captured[1]["volume"] == 0.5
    assert captured[0]["type"] == 1


def test_reverse_market_closes_opposite_then_opens() -> None:
    adapter = _build_adapter_mock()
    adapter.positions.return_value = [
        {"ticket": 31, "symbol": "XAUUSD.a", "type": 1, "volume": 0.4, "time": 10},
        {"ticket": 32, "symbol": "XAUUSD.a", "type": 0, "volume": 0.3, "time": 20},
    ]
    captured: list[dict[str, Any]] = []
    adapter.order_check_send.side_effect = lambda request: (captured.append(request.copy()) or _flow_success(request))

    executor = MT5CommandExecutor(adapter=adapter, alias_map={"XAUUSD": "XAUUSD.a"})
    result = executor.execute(
        {
            "command": "reverse_market",
            "symbol": "XAUUSD",
            "options": {"side": "buy", "quantity_lots": 0.25},
        },
        correlation_id="corr-reverse-01",
    )

    assert result.ok is True
    assert len(captured) == 2
    assert captured[0]["position"] == 31
    assert "position" not in captured[1]
    assert captured[1]["volume"] == 0.25
    assert captured[1]["type"] == 0


def test_close_all_positions_operates_over_all_symbols() -> None:
    adapter = _build_adapter_mock()
    adapter.positions.return_value = [
        {"ticket": 1001, "symbol": "EURUSD", "type": 0, "volume": 0.1, "time": 2},
        {"ticket": 1002, "symbol": "XAUUSD.a", "type": 1, "volume": 0.2, "time": 1},
    ]
    captured: list[dict[str, Any]] = []
    adapter.order_check_send.side_effect = lambda request: (captured.append(request.copy()) or _flow_success(request))

    executor = MT5CommandExecutor(adapter=adapter)
    result = executor.execute(
        {
            "command": "close_all_positions",
            "account_scope": "primary",
            "options": {"close_mode": "fifo"},
        },
        correlation_id="corr-close-all-01",
    )

    assert result.ok is True
    assert len(captured) == 2
    assert {captured[0]["position"], captured[1]["position"]} == {1001, 1002}


def test_executor_fails_when_mt5_not_connected() -> None:
    adapter = _build_adapter_mock()
    adapter.account_info.return_value = {}
    executor = MT5CommandExecutor(adapter=adapter)
    result = executor.execute(
        {"command": "open_market", "symbol": "XAUUSD", "options": {"side": "buy", "quantity_lots": 0.01}},
        correlation_id="corr-disconnected",
    )
    assert result.ok is False
    assert "not connected" in result.summary.lower()
