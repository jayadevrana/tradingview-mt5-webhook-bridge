from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.domain.enums import CommandType

SideType = Literal["buy", "sell"]
SideFilterType = Literal["buy", "sell", "both"]
CloseModeType = Literal["fifo", "lifo", "largest_first", "smallest_first", "all_matching"]


class AlertOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    side: Optional[SideType] = None
    quantity_lots: Optional[float] = Field(default=None, gt=0)
    close_opposite_first: Optional[bool] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    slippage_points: Optional[int] = Field(default=None, ge=0)
    comment: Optional[str] = Field(default=None, max_length=128)
    strategy: Optional[str] = Field(default=None, max_length=128)
    magic: Optional[int] = None
    symbol_alias: Optional[str] = Field(default=None, max_length=64)
    side_filter: Optional[SideFilterType] = None
    ticket: Optional[int] = Field(default=None, gt=0)
    close_mode: Optional[CloseModeType] = None


class TradingViewWebhookAlert(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: Literal["1.0"]
    event_id: str = Field(min_length=1, max_length=128)
    sent_at: datetime
    source: Literal["tradingview"]
    command: CommandType
    account_scope: str = Field(min_length=1, max_length=64)
    symbol: Optional[str] = Field(default=None, min_length=1, max_length=64)
    secret: str = Field(min_length=1, max_length=256)
    options: AlertOptions

    @field_validator("sent_at")
    @classmethod
    def validate_sent_at_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("sent_at must include timezone")
        return value

    @model_validator(mode="after")
    def validate_command_requirements(self) -> "TradingViewWebhookAlert":
        requires_symbol = {
            CommandType.OPEN_MARKET,
            CommandType.CLOSE_POSITIONS,
            CommandType.CLOSE_ALL_SYMBOL,
            CommandType.REVERSE_MARKET,
        }
        if self.command in requires_symbol and not self.symbol:
            raise ValueError(f"symbol is required for command '{self.command.value}'")
        if self.command == CommandType.CLOSE_ALL_POSITIONS and self.symbol:
            raise ValueError("symbol must be omitted for command 'close_all_positions'")
        if self.command in {CommandType.OPEN_MARKET, CommandType.REVERSE_MARKET}:
            if self.options.side is None:
                raise ValueError(f"options.side is required for command '{self.command.value}'")
            if self.options.quantity_lots is None:
                raise ValueError(f"options.quantity_lots is required for command '{self.command.value}'")
        return self

    def normalized_payload(self) -> Dict[str, Any]:
        payload = self.model_dump(mode="json")
        if payload.get("symbol"):
            payload["symbol"] = str(payload["symbol"]).upper()
        options = payload.get("options")
        if isinstance(options, dict):
            side = options.get("side")
            if isinstance(side, str):
                options["side"] = side.lower()
            side_filter = options.get("side_filter")
            if isinstance(side_filter, str):
                options["side_filter"] = side_filter.lower()
        payload["secret"] = "***"
        return payload


def validate_webhook_payload(payload: Dict[str, Any]) -> TradingViewWebhookAlert:
    try:
        return TradingViewWebhookAlert.model_validate(payload)
    except ValidationError:
        raise
