from __future__ import annotations

from dataclasses import dataclass
from math import inf
from typing import Any, Protocol

from app.domain.models import MT5ExecutionResult, MT5OrderFlowResult, SymbolResolution


class MT5ExecutionAdapter(Protocol):
    def account_info(self) -> dict[str, Any]:
        ...

    def symbol_resolve(self, symbol: str, alias_map: dict[str, str]) -> SymbolResolution:
        ...

    def ensure_symbol_tradable(self, symbol: str) -> tuple[bool, str]:
        ...

    def symbol_tick(self, symbol: str) -> dict[str, Any] | None:
        ...

    def positions(self, symbol: str | None = None, ticket: int | None = None) -> list[dict[str, Any]]:
        ...

    def order_check_send(self, request: dict[str, Any]) -> MT5OrderFlowResult:
        ...

    def get_constant(self, name: str, default: Any = None) -> Any:
        ...


@dataclass
class CloseComputation:
    ok: bool
    summary: str
    actions: list[dict[str, Any]]
    retcode: int | None = None
    last_error: str | None = None


class MT5CommandExecutor:
    def __init__(self, adapter: MT5ExecutionAdapter, alias_map: dict[str, str] | None = None) -> None:
        self._adapter = adapter
        self._alias_map = {key.upper(): value for key, value in (alias_map or {}).items()}

    def execute(self, command: dict[str, Any], correlation_id: str) -> MT5ExecutionResult:
        command_value = self._command_value(command)
        if not self._adapter.account_info():
            return MT5ExecutionResult(
                ok=False,
                summary="MT5 is not connected or account_info unavailable",
                command=command_value,
                correlation_id=correlation_id,
            )

        handlers = {
            "open_market": self._execute_open_market,
            "close_positions": self._execute_close_positions,
            "close_all_symbol": self._execute_close_all_symbol,
            "close_all_positions": self._execute_close_all_positions,
            "reverse_market": self._execute_reverse_market,
        }
        handler = handlers.get(command_value)
        if handler is None:
            return MT5ExecutionResult(
                ok=False,
                summary=f"Unsupported command '{command_value}'",
                command=command_value,
                correlation_id=correlation_id,
            )
        return handler(command, correlation_id)

    def _execute_open_market(self, command: dict[str, Any], correlation_id: str) -> MT5ExecutionResult:
        options = self._options(command)
        side = str(options.get("side") or "").lower()
        lots = self._to_float_or_none(options.get("quantity_lots"))
        if side not in {"buy", "sell"} or lots is None or lots <= 0:
            return MT5ExecutionResult(
                ok=False,
                summary="open_market requires options.side and positive options.quantity_lots",
                command="open_market",
                correlation_id=correlation_id,
            )

        symbol_resolution = self._resolve_symbol(command, options)
        if symbol_resolution.resolved is None:
            return MT5ExecutionResult(
                ok=False,
                summary=f"Unable to resolve symbol '{command.get('symbol')}'",
                command="open_market",
                correlation_id=correlation_id,
                resolved_symbol=None,
            )
        resolved_symbol = symbol_resolution.resolved

        tradable_ok, tradable_message = self._adapter.ensure_symbol_tradable(resolved_symbol)
        if not tradable_ok:
            return MT5ExecutionResult(
                ok=False,
                summary=tradable_message,
                command="open_market",
                correlation_id=correlation_id,
                resolved_symbol=resolved_symbol,
            )

        actions: list[dict[str, Any]] = []
        close_opposite_first = bool(options.get("close_opposite_first", False))
        if close_opposite_first:
            opposite_filter = "sell" if side == "buy" else "buy"
            close_result = self._close_positions_internal(
                symbol=resolved_symbol,
                side_filter=opposite_filter,
                quantity_lots=None,
                ticket=None,
                close_mode="all_matching",
                options=options,
            )
            actions.extend(close_result.actions)
            if not close_result.ok:
                return MT5ExecutionResult(
                    ok=False,
                    summary=f"close_opposite_first failed: {close_result.summary}",
                    command="open_market",
                    correlation_id=correlation_id,
                    resolved_symbol=resolved_symbol,
                    retcode=close_result.retcode,
                    last_error=close_result.last_error,
                    actions=actions,
                )

        try:
            order_request = self._build_market_request(
                symbol=resolved_symbol,
                side=side,
                volume=lots,
                options=options,
                position_ticket=None,
            )
        except ValueError as exc:
            return MT5ExecutionResult(
                ok=False,
                summary=str(exc),
                command="open_market",
                correlation_id=correlation_id,
                resolved_symbol=resolved_symbol,
                actions=actions,
            )
        flow = self._adapter.order_check_send(order_request)
        actions.append(self._action_record("open_market", resolved_symbol, lots, flow, position_ticket=None))
        return MT5ExecutionResult(
            ok=flow.ok,
            summary="open_market executed" if flow.ok else f"open_market failed at {flow.stage}",
            command="open_market",
            correlation_id=correlation_id,
            resolved_symbol=resolved_symbol,
            retcode=flow.retcode,
            last_error=flow.last_error,
            request_snapshot=flow.request_snapshot,
            response_snapshot=flow.send_snapshot,
            actions=actions,
        )

    def _execute_close_positions(self, command: dict[str, Any], correlation_id: str) -> MT5ExecutionResult:
        options = self._options(command)
        symbol_resolution = self._resolve_symbol(command, options)
        if symbol_resolution.resolved is None:
            return MT5ExecutionResult(
                ok=False,
                summary=f"Unable to resolve symbol '{command.get('symbol')}'",
                command="close_positions",
                correlation_id=correlation_id,
            )
        resolved_symbol = symbol_resolution.resolved
        close_result = self._close_positions_internal(
            symbol=resolved_symbol,
            side_filter=str(options.get("side_filter") or "both"),
            quantity_lots=self._to_float_or_none(options.get("quantity_lots")),
            ticket=self._to_int_or_none(options.get("ticket")),
            close_mode=str(options.get("close_mode") or "fifo"),
            options=options,
        )
        return MT5ExecutionResult(
            ok=close_result.ok,
            summary=close_result.summary,
            command="close_positions",
            correlation_id=correlation_id,
            resolved_symbol=resolved_symbol,
            retcode=close_result.retcode,
            last_error=close_result.last_error,
            actions=close_result.actions,
        )

    def _execute_close_all_symbol(self, command: dict[str, Any], correlation_id: str) -> MT5ExecutionResult:
        options = self._options(command)
        options.setdefault("close_mode", "all_matching")
        options["quantity_lots"] = None
        return self._execute_close_positions(
            {
                **command,
                "command": "close_positions",
                "options": options,
            },
            correlation_id,
        )

    def _execute_close_all_positions(self, command: dict[str, Any], correlation_id: str) -> MT5ExecutionResult:
        options = self._options(command)
        side_filter = str(options.get("side_filter") or "both")
        close_mode = str(options.get("close_mode") or "fifo")
        positions = self._filter_positions(self._adapter.positions(), side_filter=side_filter)
        ordered = self._order_positions(positions, close_mode=close_mode)
        actions: list[dict[str, Any]] = []
        closed_count = 0
        for position in ordered:
            symbol = str(position.get("symbol") or "")
            volume = self._to_float_or_none(position.get("volume"))
            ticket = self._to_int_or_none(position.get("ticket"))
            if not symbol or volume is None or volume <= 0 or ticket is None:
                continue
            tradable_ok, tradable_message = self._adapter.ensure_symbol_tradable(symbol)
            if not tradable_ok:
                return MT5ExecutionResult(
                    ok=False,
                    summary=tradable_message,
                    command="close_all_positions",
                    correlation_id=correlation_id,
                    actions=actions,
                )
            side = self._opposite_side_for_position(position)
            if side is None:
                continue
            try:
                request = self._build_market_request(
                    symbol=symbol,
                    side=side,
                    volume=volume,
                    options=options,
                    position_ticket=ticket,
                )
            except ValueError as exc:
                return MT5ExecutionResult(
                    ok=False,
                    summary=str(exc),
                    command="close_all_positions",
                    correlation_id=correlation_id,
                    actions=actions,
                )
            flow = self._adapter.order_check_send(request)
            actions.append(self._action_record("close_all_positions", symbol, volume, flow, position_ticket=ticket))
            if not flow.ok:
                return MT5ExecutionResult(
                    ok=False,
                    summary=f"close_all_positions failed at {flow.stage}",
                    command="close_all_positions",
                    correlation_id=correlation_id,
                    retcode=flow.retcode,
                    last_error=flow.last_error,
                    actions=actions,
                )
            closed_count += 1

        return MT5ExecutionResult(
            ok=True,
            summary=f"close_all_positions completed, closed {closed_count} position(s)",
            command="close_all_positions",
            correlation_id=correlation_id,
            actions=actions,
        )

    def _execute_reverse_market(self, command: dict[str, Any], correlation_id: str) -> MT5ExecutionResult:
        options = self._options(command)
        side = str(options.get("side") or "").lower()
        lots = self._to_float_or_none(options.get("quantity_lots"))
        if side not in {"buy", "sell"} or lots is None or lots <= 0:
            return MT5ExecutionResult(
                ok=False,
                summary="reverse_market requires options.side and positive options.quantity_lots",
                command="reverse_market",
                correlation_id=correlation_id,
            )

        symbol_resolution = self._resolve_symbol(command, options)
        if symbol_resolution.resolved is None:
            return MT5ExecutionResult(
                ok=False,
                summary=f"Unable to resolve symbol '{command.get('symbol')}'",
                command="reverse_market",
                correlation_id=correlation_id,
            )
        resolved_symbol = symbol_resolution.resolved
        opposite_filter = "sell" if side == "buy" else "buy"
        close_result = self._close_positions_internal(
            symbol=resolved_symbol,
            side_filter=opposite_filter,
            quantity_lots=None,
            ticket=None,
            close_mode="all_matching",
            options=options,
        )
        actions = list(close_result.actions)
        if not close_result.ok:
            return MT5ExecutionResult(
                ok=False,
                summary=f"reverse_market close phase failed: {close_result.summary}",
                command="reverse_market",
                correlation_id=correlation_id,
                resolved_symbol=resolved_symbol,
                retcode=close_result.retcode,
                last_error=close_result.last_error,
                actions=actions,
            )

        tradable_ok, tradable_message = self._adapter.ensure_symbol_tradable(resolved_symbol)
        if not tradable_ok:
            return MT5ExecutionResult(
                ok=False,
                summary=tradable_message,
                command="reverse_market",
                correlation_id=correlation_id,
                resolved_symbol=resolved_symbol,
                actions=actions,
            )

        try:
            request = self._build_market_request(
                symbol=resolved_symbol,
                side=side,
                volume=lots,
                options=options,
                position_ticket=None,
            )
        except ValueError as exc:
            return MT5ExecutionResult(
                ok=False,
                summary=str(exc),
                command="reverse_market",
                correlation_id=correlation_id,
                resolved_symbol=resolved_symbol,
                actions=actions,
            )
        flow = self._adapter.order_check_send(request)
        actions.append(self._action_record("reverse_market_open", resolved_symbol, lots, flow))
        return MT5ExecutionResult(
            ok=flow.ok,
            summary="reverse_market executed" if flow.ok else f"reverse_market failed at {flow.stage}",
            command="reverse_market",
            correlation_id=correlation_id,
            resolved_symbol=resolved_symbol,
            retcode=flow.retcode,
            last_error=flow.last_error,
            request_snapshot=flow.request_snapshot,
            response_snapshot=flow.send_snapshot,
            actions=actions,
        )

    def _close_positions_internal(
        self,
        symbol: str,
        side_filter: str,
        quantity_lots: float | None,
        ticket: int | None,
        close_mode: str,
        options: dict[str, Any],
    ) -> CloseComputation:
        tradable_ok, tradable_message = self._adapter.ensure_symbol_tradable(symbol)
        if not tradable_ok:
            return CloseComputation(ok=False, summary=tradable_message, actions=[])

        rows = self._adapter.positions(symbol=symbol, ticket=ticket)
        filtered = self._filter_positions(rows, side_filter=side_filter)
        ordered = self._order_positions(filtered, close_mode=close_mode)
        if not ordered:
            return CloseComputation(ok=True, summary="No matching positions to close", actions=[])

        remaining = quantity_lots if quantity_lots is not None else inf
        actions: list[dict[str, Any]] = []
        closed_lots = 0.0
        for position in ordered:
            if remaining <= 1e-9:
                break
            position_volume = self._to_float_or_none(position.get("volume"))
            ticket_value = self._to_int_or_none(position.get("ticket"))
            if position_volume is None or position_volume <= 0 or ticket_value is None:
                continue
            close_side = self._opposite_side_for_position(position)
            if close_side is None:
                continue
            close_volume = min(position_volume, remaining)
            try:
                request = self._build_market_request(
                    symbol=symbol,
                    side=close_side,
                    volume=close_volume,
                    options=options,
                    position_ticket=ticket_value,
                )
            except ValueError as exc:
                return CloseComputation(
                    ok=False,
                    summary=str(exc),
                    actions=actions,
                )
            flow = self._adapter.order_check_send(request)
            actions.append(
                self._action_record("close_position", symbol, close_volume, flow, position_ticket=ticket_value)
            )
            if not flow.ok:
                return CloseComputation(
                    ok=False,
                    summary=f"close_positions failed at {flow.stage}",
                    actions=actions,
                    retcode=flow.retcode,
                    last_error=flow.last_error,
                )
            closed_lots += close_volume
            remaining -= close_volume

        if quantity_lots is not None and remaining > 1e-9:
            return CloseComputation(
                ok=False,
                summary=f"Requested {quantity_lots} lots but only closed {closed_lots}",
                actions=actions,
            )
        return CloseComputation(
            ok=True,
            summary=f"Closed {closed_lots:.2f} lots across {len(actions)} action(s)",
            actions=actions,
        )

    def _resolve_symbol(self, command: dict[str, Any], options: dict[str, Any]) -> SymbolResolution:
        raw_symbol = str(command.get("symbol") or "")
        symbol_alias = options.get("symbol_alias")
        alias_map = dict(self._alias_map)
        if raw_symbol and isinstance(symbol_alias, str) and symbol_alias:
            alias_map[raw_symbol.upper()] = symbol_alias
        return self._adapter.symbol_resolve(raw_symbol, alias_map)

    def _build_market_request(
        self,
        symbol: str,
        side: str,
        volume: float,
        options: dict[str, Any],
        position_ticket: int | None,
    ) -> dict[str, Any]:
        tick = self._adapter.symbol_tick(symbol)
        if tick is None:
            raise ValueError(f"Missing tick for symbol '{symbol}'")

        buy_type = self._adapter.get_constant("ORDER_TYPE_BUY")
        sell_type = self._adapter.get_constant("ORDER_TYPE_SELL")
        order_type = buy_type if side == "buy" else sell_type
        price = self._to_float_or_none(tick.get("ask")) if side == "buy" else self._to_float_or_none(tick.get("bid"))
        if order_type is None or price is None:
            raise ValueError("Missing required MT5 constants or tick prices")

        request: dict[str, Any] = {
            "action": self._adapter.get_constant("TRADE_ACTION_DEAL"),
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type,
            "price": float(price),
            "deviation": int(options.get("slippage_points") or 20),
        }
        order_time = self._adapter.get_constant("ORDER_TIME_GTC")
        if order_time is not None:
            request["type_time"] = order_time
        filling = self._adapter.get_constant("ORDER_FILLING_RETURN")
        if filling is None:
            filling = self._adapter.get_constant("ORDER_FILLING_IOC")
        if filling is not None:
            request["type_filling"] = filling
        sl = self._to_float_or_none(options.get("sl"))
        tp = self._to_float_or_none(options.get("tp"))
        if sl is not None:
            request["sl"] = sl
        if tp is not None:
            request["tp"] = tp
        comment = options.get("comment")
        if isinstance(comment, str) and comment:
            request["comment"] = comment
        magic = self._to_int_or_none(options.get("magic"))
        if magic is not None:
            request["magic"] = magic
        if position_ticket is not None:
            request["position"] = int(position_ticket)
        return request

    def _filter_positions(self, positions: list[dict[str, Any]], side_filter: str) -> list[dict[str, Any]]:
        normalized_filter = side_filter.lower()
        if normalized_filter == "both":
            return positions
        filtered: list[dict[str, Any]] = []
        for position in positions:
            side = self._position_side(position)
            if side == normalized_filter:
                filtered.append(position)
        return filtered

    def _order_positions(self, positions: list[dict[str, Any]], close_mode: str) -> list[dict[str, Any]]:
        mode = close_mode.lower()
        if mode == "lifo":
            return sorted(positions, key=self._position_sort_key, reverse=True)
        if mode == "largest_first":
            return sorted(positions, key=lambda item: self._to_float_or_none(item.get("volume")) or 0, reverse=True)
        if mode == "smallest_first":
            return sorted(positions, key=lambda item: self._to_float_or_none(item.get("volume")) or 0)
        return sorted(positions, key=self._position_sort_key)

    def _position_sort_key(self, position: dict[str, Any]) -> tuple[int, int]:
        time_value = self._to_int_or_none(position.get("time")) or 0
        ticket_value = self._to_int_or_none(position.get("ticket")) or 0
        return time_value, ticket_value

    def _position_side(self, position: dict[str, Any]) -> str | None:
        pos_type = position.get("type")
        buy_type = self._adapter.get_constant("ORDER_TYPE_BUY")
        sell_type = self._adapter.get_constant("ORDER_TYPE_SELL")
        if pos_type == buy_type:
            return "buy"
        if pos_type == sell_type:
            return "sell"
        return None

    def _opposite_side_for_position(self, position: dict[str, Any]) -> str | None:
        current_side = self._position_side(position)
        if current_side == "buy":
            return "sell"
        if current_side == "sell":
            return "buy"
        return None

    @staticmethod
    def _command_value(command: dict[str, Any]) -> str:
        raw = command.get("command")
        if hasattr(raw, "value"):
            return str(raw.value)
        return str(raw or "")

    @staticmethod
    def _options(command: dict[str, Any]) -> dict[str, Any]:
        options = command.get("options")
        if isinstance(options, dict):
            return dict(options)
        return {}

    @staticmethod
    def _to_float_or_none(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_int_or_none(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _action_record(
        operation: str,
        symbol: str,
        volume: float,
        flow: MT5OrderFlowResult,
        position_ticket: int | None = None,
    ) -> dict[str, Any]:
        return {
            "operation": operation,
            "symbol": symbol,
            "volume": volume,
            "position_ticket": position_ticket,
            "ok": flow.ok,
            "stage": flow.stage,
            "message": flow.message,
            "retcode": flow.retcode,
            "last_error": flow.last_error,
            "request": flow.request_snapshot,
            "check": flow.check_snapshot,
            "send": flow.send_snapshot,
        }
