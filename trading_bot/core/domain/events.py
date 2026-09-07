from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass
class TradingEvent:
    event_type: str
    symbol: str | None = None
    timestamp: datetime | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderFilled(TradingEvent):
    order_id: str | None = None
    filled_volume: Decimal = Decimal("0")
    filled_price: Decimal | None = None


@dataclass
class RiskBreached(TradingEvent):
    reason: str | None = None
    severity: str = "warning"


__all__ = ["TradingEvent", "OrderFilled", "RiskBreached"]
