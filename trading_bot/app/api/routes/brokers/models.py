from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class BrokerCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    platform: Literal["mt4", "mt5"] = "mt5"
    default_symbol: str | None = None
    terminal_path: str | None = None
    execution_mode: Literal["mouse", "direct"] = "mouse"
    window_hint: str | None = "FinexBisnisSolusi"


class BrokerUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    platform: Literal["mt4", "mt5"] | None = None
    default_symbol: str | None = None
    terminal_path: str | None = None
    execution_mode: Literal["mouse", "direct"] | None = None
    window_hint: str | None = None
    is_active: bool | None = None


class TradeOpenRequest(BaseModel):
    symbol: str
    lot: float = 0.01
    trade_type: Literal["buy", "sell"]
    signal_time: float | None = None
    broker_id: int | None = None
    order_method: Literal["mouse", "direct"] | None = None


class TradeCloseRequest(BaseModel):
    symbol: str
    lot: float = 0.01
    ticket: int
    broker_id: int | None = None
