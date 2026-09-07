from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from .enums import OrderSide, OrderType, PositionSide


@dataclass
class SymbolQuote:
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    timestamp: datetime | None = None
    spread: Decimal | None = None


@dataclass
class Candle:
    symbol: str
    timeframe: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    timestamp: datetime | None = None


@dataclass
class Position:
    broker: str
    symbol: str
    side: PositionSide
    volume: Decimal
    entry_price: Decimal
    mark_price: Decimal
    pnl: Decimal = Decimal("0")
    open_time: datetime | None = None


@dataclass
class OrderRequest:
    symbol: str
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    volume: Decimal = Decimal("0")
    price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    client_order_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderExecution:
    broker: str
    symbol: str
    order_id: str
    client_order_id: str | None
    side: OrderSide
    status: str
    filled_volume: Decimal
    average_price: Decimal | None
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass
class AccountSummary:
    broker: str
    balance: Decimal
    equity: Decimal
    margin_used: Decimal
    free_margin: Decimal
    leverage: Decimal
    currency: str


__all__ = [
    "AccountSummary",
    "Candle",
    "OrderExecution",
    "OrderRequest",
    "Position",
    "SymbolQuote",
]
