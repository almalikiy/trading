from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class MarketSnapshot:
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    timestamp: datetime | None = None
    source: str = "unknown"


@dataclass
class MarketBar:
    symbol: str
    timeframe: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    timestamp: datetime | None = None
    source: str = "unknown"
