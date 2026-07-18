from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

try:
    import psutil
except ImportError:  # pragma: no cover - environment-dependent
    psutil = None  # type: ignore[assignment]

from app.domain.models import (
    MT5ConnectionConfig,
    MT5ConnectionResult,
    MT5ExecutionResult,
    MT5OrderFlowResult,
    SymbolResolution,
    TerminalCandidate,
    TerminalSelection,
)

_TERMINAL_HINTS = ("terminal64.exe", "terminal.exe", "metatrader64.exe", "metatrader.exe")


def _scan_terminal_processes(process_iter_factory: Callable[[], Iterable[Any]]) -> list[TerminalCandidate]:
    candidates: list[TerminalCandidate] = []
    for process in process_iter_factory():
        info = getattr(process, "info", None)
        if not isinstance(info, dict):
            continue
        name = str(info.get("name") or "")
        exe = info.get("exe")
        cmdline_value = info.get("cmdline") or []
        if not isinstance(cmdline_value, list):
            cmdline_value = []
        name_lc = name.lower()
        exe_lc = str(exe).lower() if exe else ""
        if any(hint in name_lc or hint in exe_lc for hint in _TERMINAL_HINTS):
            candidates.append(
                TerminalCandidate(
                    pid=int(info.get("pid") or 0),
                    name=name,
                    executable_path=str(exe) if exe else None,
                    cmdline=[str(item) for item in cmdline_value],
                )
            )
    candidates.sort(key=lambda item: item.pid)
    return candidates


class OfficialMT5Adapter:
    """Official MetaTrader5 package adapter.

    This adapter only wraps documented Python integration calls and exposes
    deterministic methods for terminal selection, symbol resolution, and
    order_check/order_send flow.
    """

    def __init__(
        self,
        mt5_module: Any | None = None,
        process_iter_factory: Callable[[], Iterable[Any]] | None = None,
    ) -> None:
        if mt5_module is None:
            try:
                import MetaTrader5 as imported_mt5  # type: ignore[import-not-found]
            except ImportError as exc:  # pragma: no cover - only when package missing
                raise RuntimeError("MetaTrader5 package is not installed") from exc
            self._mt5 = imported_mt5
        else:
            self._mt5 = mt5_module
        self._process_iter_factory = process_iter_factory

    def detect_terminals(self) -> list[TerminalCandidate]:
        if self._process_iter_factory is not None:
            process_iter = self._process_iter_factory
        elif psutil is not None:
            process_iter = lambda: psutil.process_iter(attrs=["pid", "name", "exe", "cmdline"])
        else:
            return []
        return _scan_terminal_processes(process_iter)

    def select_terminal(
        self,
        candidates: list[TerminalCandidate],
        preferred_pid: int | None = None,
        preferred_path: str | None = None,
    ) -> TerminalSelection:
        if not candidates:
            return TerminalSelection(
                status="none_found",
                selected=None,
                candidates=[],
                message="No running MetaTrader terminal detected",
            )
        if preferred_pid is not None:
            for candidate in candidates:
                if candidate.pid == preferred_pid:
                    return TerminalSelection(
                        status="selected",
                        selected=candidate,
                        candidates=candidates,
                        message=f"Selected terminal pid={preferred_pid}",
                    )
        if preferred_path:
            preferred_path_lc = preferred_path.lower()
            for candidate in candidates:
                path = (candidate.executable_path or "").lower()
                if path == preferred_path_lc:
                    return TerminalSelection(
                        status="selected",
                        selected=candidate,
                        candidates=candidates,
                        message=f"Selected terminal path={preferred_path}",
                    )
        if len(candidates) == 1:
            return TerminalSelection(
                status="auto_selected",
                selected=candidates[0],
                candidates=candidates,
                message="Exactly one terminal found and auto-selected",
            )
        return TerminalSelection(
            status="requires_selection",
            selected=None,
            candidates=candidates,
            message="Multiple terminals detected; explicit selection required",
        )

    def initialize(self, config: MT5ConnectionConfig) -> MT5ConnectionResult:
        init_ok = self._initialize_terminal(config)
        if not init_ok:
            return MT5ConnectionResult(
                connected=False,
                message="MT5 initialize failed",
                last_error=self._last_error_text(),
            )

        if config.login is not None:
            login_kwargs: dict[str, Any] = {"timeout": config.timeout_ms}
            if config.password is not None:
                login_kwargs["password"] = config.password
            if config.server is not None:
                login_kwargs["server"] = config.server
            login_ok = bool(self._mt5.login(config.login, **login_kwargs))
            if not login_ok:
                last_error = self._last_error_text()
                self.shutdown()
                return MT5ConnectionResult(
                    connected=False,
                    message="MT5 login failed",
                    last_error=last_error,
                )

        account = self.account_info()
        terminal = self.terminal_info()
        if not account:
            return MT5ConnectionResult(
                connected=False,
                message="MT5 initialized but account_info unavailable",
                last_error=self._last_error_text(),
                terminal_info=terminal or None,
            )
        return MT5ConnectionResult(
            connected=True,
            message="MT5 connected",
            last_error=self._last_error_text(),
            account_info=account,
            terminal_info=terminal or None,
        )

    def _initialize_terminal(self, config: MT5ConnectionConfig) -> bool:
        kwargs: dict[str, Any] = {"timeout": config.timeout_ms, "portable": config.portable}
        if config.terminal_path:
            return bool(self._mt5.initialize(config.terminal_path, **kwargs))
        return bool(self._mt5.initialize(**kwargs))

    def shutdown(self) -> None:
        self._mt5.shutdown()

    def account_info(self) -> dict[str, Any]:
        account = self._mt5.account_info()
        if account is None:
            return {}
        return self._namedtuple_to_dict(account)

    def terminal_info(self) -> dict[str, Any]:
        terminal = self._mt5.terminal_info()
        if terminal is None:
            return {}
        return self._namedtuple_to_dict(terminal)

    def symbol_resolve(self, symbol: str, alias_map: dict[str, str]) -> SymbolResolution:
        requested = symbol.upper()
        if self._symbol_exists(requested):
            return SymbolResolution(
                requested=symbol,
                resolved=requested,
                source="exact",
                notes="Exact broker symbol match",
            )

        normalized_alias_map = {key.upper(): value for key, value in alias_map.items()}
        alias_target = normalized_alias_map.get(requested)
        if alias_target and self._symbol_exists(alias_target):
            return SymbolResolution(
                requested=symbol,
                resolved=alias_target,
                source="alias_map",
                notes=f"Resolved by alias map {requested}->{alias_target}",
            )

        suggestions = self._suggest_symbols(requested)
        return SymbolResolution(
            requested=symbol,
            resolved=None,
            source="unresolved",
            notes="No exact or alias match",
            suggestions=suggestions if suggestions else None,
        )

    def ensure_symbol_tradable(self, symbol: str) -> tuple[bool, str]:
        info = self._mt5.symbol_info(symbol)
        if info is None:
            return False, f"Symbol '{symbol}' not found in terminal"
        if not bool(getattr(info, "visible", True)):
            selected = bool(self._mt5.symbol_select(symbol, True))
            if not selected:
                return False, f"Symbol '{symbol}' is not visible and symbol_select failed"
            info = self._mt5.symbol_info(symbol)
            if info is None:
                return False, f"Symbol '{symbol}' unavailable after symbol_select"

        disabled_trade_mode = getattr(self._mt5, "SYMBOL_TRADE_MODE_DISABLED", None)
        trade_mode = getattr(info, "trade_mode", None)
        if disabled_trade_mode is not None and trade_mode == disabled_trade_mode:
            return False, f"Symbol '{symbol}' is not tradable (trade_mode disabled)"
        return True, "ok"

    def symbol_tick(self, symbol: str) -> dict[str, Any] | None:
        tick = self._mt5.symbol_info_tick(symbol)
        if tick is None:
            return None
        return self._namedtuple_to_dict(tick)

    def positions(self, symbol: str | None = None, ticket: int | None = None) -> list[dict[str, Any]]:
        if ticket is not None:
            rows = self._mt5.positions_get(ticket=ticket)
        elif symbol is not None:
            rows = self._mt5.positions_get(symbol=symbol)
        else:
            rows = self._mt5.positions_get()
        if rows is None:
            return []
        return [self._namedtuple_to_dict(item) for item in rows]

    def order_check_send(self, request: dict[str, Any]) -> MT5OrderFlowResult:
        check_result = self._mt5.order_check(request)
        if check_result is None:
            return MT5OrderFlowResult(
                ok=False,
                stage="order_check",
                message="order_check returned None",
                last_error=self._last_error_text(),
                request_snapshot=request.copy(),
            )
        check_snapshot = self._namedtuple_to_dict(check_result)
        check_retcode = check_snapshot.get("retcode")
        if not self._retcode_success(check_retcode):
            return MT5OrderFlowResult(
                ok=False,
                stage="order_check",
                message="order_check rejected request",
                retcode=self._to_int_or_none(check_retcode),
                last_error=self._last_error_text(),
                request_snapshot=request.copy(),
                check_snapshot=check_snapshot,
            )

        send_result = self._mt5.order_send(request)
        if send_result is None:
            return MT5OrderFlowResult(
                ok=False,
                stage="order_send",
                message="order_send returned None",
                last_error=self._last_error_text(),
                request_snapshot=request.copy(),
                check_snapshot=check_snapshot,
            )
        send_snapshot = self._namedtuple_to_dict(send_result)
        send_retcode = send_snapshot.get("retcode")
        if not self._retcode_success(send_retcode):
            return MT5OrderFlowResult(
                ok=False,
                stage="order_send",
                message="order_send rejected request",
                retcode=self._to_int_or_none(send_retcode),
                last_error=self._last_error_text(),
                request_snapshot=request.copy(),
                check_snapshot=check_snapshot,
                send_snapshot=send_snapshot,
            )

        return MT5OrderFlowResult(
            ok=True,
            stage="completed",
            message="order_send completed",
            retcode=self._to_int_or_none(send_retcode),
            last_error=self._last_error_text(),
            request_snapshot=request.copy(),
            check_snapshot=check_snapshot,
            send_snapshot=send_snapshot,
        )

    def get_constant(self, name: str, default: Any = None) -> Any:
        return getattr(self._mt5, name, default)

    def execute(self, command: dict[str, Any], correlation_id: str) -> MT5ExecutionResult:
        _ = command
        _ = correlation_id
        return MT5ExecutionResult(ok=False, summary="Use MT5CommandExecutor for command execution")

    def _last_error_text(self) -> str | None:
        last_error = self._mt5.last_error()
        if isinstance(last_error, tuple) and len(last_error) >= 2:
            return f"{last_error[0]}: {last_error[1]}"
        if last_error is None:
            return None
        return str(last_error)

    def _retcode_success(self, retcode: Any) -> bool:
        success_codes = {
            getattr(self._mt5, "TRADE_RETCODE_DONE", None),
            getattr(self._mt5, "TRADE_RETCODE_DONE_PARTIAL", None),
            getattr(self._mt5, "TRADE_RETCODE_PLACED", None),
        }
        success_codes.discard(None)
        return retcode in success_codes

    def _symbol_exists(self, symbol: str) -> bool:
        return self._mt5.symbol_info(symbol) is not None

    def _suggest_symbols(self, requested: str) -> list[str]:
        suggestions: list[str] = []
        symbols = self._mt5.symbols_get(group=f"*{requested}*")
        if not symbols:
            return suggestions
        for item in symbols[:10]:
            name = getattr(item, "name", None)
            if name is not None:
                suggestions.append(str(name))
        return suggestions

    @staticmethod
    def _to_int_or_none(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _namedtuple_to_dict(item: Any) -> dict[str, Any]:
        if hasattr(item, "_asdict"):
            return dict(item._asdict())
        if isinstance(item, dict):
            return dict(item)
        return {"value": item}


class StubMT5Adapter:
    """Non-trading fallback adapter."""

    def initialize(self, config: MT5ConnectionConfig) -> MT5ConnectionResult:
        _ = config
        return MT5ConnectionResult(
            connected=False,
            message="MT5 package not available",
            last_error="Stub adapter in use",
        )

    def account_info(self) -> dict[str, object]:
        return {"connected": False}

    def detect_terminals(self) -> list[TerminalCandidate]:
        if self._process_iter_factory is not None:
            process_iter = self._process_iter_factory
        elif psutil is not None:
            process_iter = lambda: psutil.process_iter(attrs=["pid", "name", "exe", "cmdline"])
        else:
            return []
        return _scan_terminal_processes(process_iter)

    def select_terminal(
        self,
        candidates: list[TerminalCandidate],
        preferred_pid: int | None = None,
        preferred_path: str | None = None,
    ) -> TerminalSelection:
        if preferred_pid is not None:
            for candidate in candidates:
                if candidate.pid == preferred_pid:
                    return TerminalSelection(
                        status="selected",
                        selected=candidate,
                        candidates=candidates,
                        message=f"Selected terminal pid={preferred_pid}",
                    )
        if preferred_path is not None:
            preferred_path_lc = preferred_path.lower()
            for candidate in candidates:
                if (candidate.executable_path or "").lower() == preferred_path_lc:
                    return TerminalSelection(
                        status="selected",
                        selected=candidate,
                        candidates=candidates,
                        message=f"Selected terminal path={preferred_path}",
                    )
        return TerminalSelection(
            status="selected" if len(candidates) == 1 else "requires_selection" if candidates else "none_found",
            selected=candidates[0] if len(candidates) == 1 else None,
            candidates=candidates,
            message="Stub adapter cannot query MT5 account/server state",
        )

    def symbol_resolve(self, symbol: str, alias_map: dict[str, str]) -> SymbolResolution:
        if symbol in alias_map:
            return SymbolResolution(requested=symbol, resolved=alias_map[symbol], source="alias_map")
        return SymbolResolution(requested=symbol, resolved=None, source="unresolved")

    def ensure_symbol_tradable(self, symbol: str) -> tuple[bool, str]:
        _ = symbol
        return False, "Stub adapter does not trade"

    def symbol_tick(self, symbol: str) -> dict[str, Any] | None:
        _ = symbol
        return None

    def positions(self, symbol: str | None = None, ticket: int | None = None) -> list[dict[str, Any]]:
        _ = symbol
        _ = ticket
        return []

    def order_check_send(self, request: dict[str, Any]) -> MT5OrderFlowResult:
        return MT5OrderFlowResult(
            ok=False,
            stage="unsupported",
            message="Stub adapter does not place orders",
            request_snapshot=request,
        )

    def get_constant(self, name: str, default: Any = None) -> Any:
        _ = name
        return default

    def execute(self, command: dict[str, Any], correlation_id: str) -> MT5ExecutionResult:
        _ = command
        _ = correlation_id
        return MT5ExecutionResult(ok=False, summary="MT5 execution unavailable")

    def shutdown(self) -> None:
        return None
    def __init__(self, process_iter_factory: Callable[[], Iterable[Any]] | None = None) -> None:
        self._process_iter_factory = process_iter_factory
