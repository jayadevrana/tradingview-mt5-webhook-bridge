from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.models import MT5ConnectionConfig
from app.mt5.adapter import OfficialMT5Adapter


@dataclass
class FakeProcess:
    info: dict[str, Any]


class FakeTupleResult:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def _asdict(self) -> dict[str, Any]:
        return dict(self._data)


@dataclass
class SymbolRow:
    name: str


class FakeMT5Module:
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_DONE_PARTIAL = 10010
    TRADE_RETCODE_PLACED = 10008
    SYMBOL_TRADE_MODE_DISABLED = 0

    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1

    def __init__(self) -> None:
        self.initialize_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self.login_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self.shutdown_calls = 0
        self.symbol_db: dict[str, Any] = {}
        self._symbols_get: list[Any] = []
        self._order_check: FakeTupleResult | None = None
        self._order_send: FakeTupleResult | None = None

    def initialize(self, *args: Any, **kwargs: Any) -> bool:
        self.initialize_calls.append((args, kwargs))
        return True

    def login(self, *args: Any, **kwargs: Any) -> bool:
        self.login_calls.append((args, kwargs))
        return True

    def shutdown(self) -> None:
        self.shutdown_calls += 1

    def account_info(self) -> FakeTupleResult:
        return FakeTupleResult({"login": 123456, "name": "Test Account"})

    def terminal_info(self) -> FakeTupleResult:
        return FakeTupleResult({"name": "MetaTrader", "connected": True})

    def last_error(self) -> tuple[int, str]:
        return (0, "ok")

    def symbol_info(self, symbol: str) -> Any:
        return self.symbol_db.get(symbol)

    def symbol_select(self, symbol: str, value: bool) -> bool:
        _ = symbol
        _ = value
        return True

    def symbols_get(self, group: str) -> list[Any]:
        _ = group
        return self._symbols_get

    def order_check(self, request: dict[str, Any]) -> FakeTupleResult | None:
        _ = request
        return self._order_check

    def order_send(self, request: dict[str, Any]) -> FakeTupleResult | None:
        _ = request
        return self._order_send


def test_detect_terminals_and_selection_model() -> None:
    fake_mt5 = FakeMT5Module()
    processes = [
        FakeProcess(info={"pid": 1, "name": "python", "exe": "/usr/bin/python", "cmdline": ["python"]}),
        FakeProcess(
            info={
                "pid": 222,
                "name": "terminal64.exe",
                "exe": "C:\\Program Files\\MetaTrader\\terminal64.exe",
                "cmdline": ["terminal64.exe"],
            }
        ),
        FakeProcess(
            info={
                "pid": 333,
                "name": "metatrader64.exe",
                "exe": "C:\\MetaTrader\\metatrader64.exe",
                "cmdline": ["metatrader64.exe"],
            }
        ),
    ]
    adapter = OfficialMT5Adapter(mt5_module=fake_mt5, process_iter_factory=lambda: processes)

    candidates = adapter.detect_terminals()
    assert len(candidates) == 2
    assert candidates[0].pid == 222
    assert candidates[1].pid == 333

    selection = adapter.select_terminal(candidates)
    assert selection.status == "requires_selection"
    assert selection.selected is None

    selected = adapter.select_terminal(candidates, preferred_pid=333)
    assert selected.status == "selected"
    assert selected.selected is not None
    assert selected.selected.pid == 333


def test_initialize_supports_manual_login() -> None:
    fake_mt5 = FakeMT5Module()
    adapter = OfficialMT5Adapter(mt5_module=fake_mt5, process_iter_factory=lambda: [])
    result = adapter.initialize(
        MT5ConnectionConfig(
            terminal_path="C:\\Program Files\\MetaTrader\\terminal64.exe",
            login=987654,
            password="masked-in-tests",
            server="Broker-Demo",
            timeout_ms=45000,
            portable=False,
        )
    )
    assert result.connected is True
    assert len(fake_mt5.initialize_calls) == 1
    assert len(fake_mt5.login_calls) == 1
    login_args, login_kwargs = fake_mt5.login_calls[0]
    assert login_args[0] == 987654
    assert login_kwargs["server"] == "Broker-Demo"


def test_symbol_resolver_uses_exact_then_alias_and_suggestions() -> None:
    fake_mt5 = FakeMT5Module()
    fake_mt5.symbol_db = {
        "EURUSD": {"name": "EURUSD"},
        "XAUUSD.a": {"name": "XAUUSD.a"},
    }
    fake_mt5._symbols_get = [SymbolRow(name="XAUUSD.a"), SymbolRow(name="XAUUSDmicro")]
    adapter = OfficialMT5Adapter(mt5_module=fake_mt5, process_iter_factory=lambda: [])

    exact = adapter.symbol_resolve("EURUSD", {})
    assert exact.resolved == "EURUSD"
    assert exact.source == "exact"

    aliased = adapter.symbol_resolve("XAUUSD", {"XAUUSD": "XAUUSD.a"})
    assert aliased.resolved == "XAUUSD.a"
    assert aliased.source == "alias_map"

    unresolved = adapter.symbol_resolve("GBPJPY", {})
    assert unresolved.resolved is None
    assert unresolved.source == "unresolved"
    assert unresolved.suggestions is not None


def test_order_check_send_calls_both_steps_and_returns_success() -> None:
    fake_mt5 = FakeMT5Module()
    fake_mt5._order_check = FakeTupleResult({"retcode": fake_mt5.TRADE_RETCODE_DONE})
    fake_mt5._order_send = FakeTupleResult({"retcode": fake_mt5.TRADE_RETCODE_DONE, "order": 123})
    adapter = OfficialMT5Adapter(mt5_module=fake_mt5, process_iter_factory=lambda: [])
    flow = adapter.order_check_send({"symbol": "EURUSD"})
    assert flow.ok is True
    assert flow.stage == "completed"
    assert flow.retcode == fake_mt5.TRADE_RETCODE_DONE
