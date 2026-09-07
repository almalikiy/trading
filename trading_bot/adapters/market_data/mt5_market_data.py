from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from trading_bot.adapters.market_data.base_market_data import BaseMarketDataAdapter


class MT5MarketDataAdapter(BaseMarketDataAdapter):
    source = "mt5"

    async def fetch_snapshot(self, symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "bid": Decimal("1.1000"),
            "ask": Decimal("1.1002"),
            "last": Decimal("1.1001"),
            "timestamp": datetime.utcnow(),
            "source": self.source,
        }

    async def fetch_bars(self, symbol: str, timeframe: str, limit: int = 200) -> list[dict[str, Any]]:
        return [{
            "symbol": symbol,
            "timeframe": timeframe,
            "open": Decimal("1.0995"),
            "high": Decimal("1.1010"),
            "low": Decimal("1.0992"),
            "close": Decimal("1.1004"),
            "volume": Decimal("1200"),
            "timestamp": datetime.utcnow(),
            "source": self.source,
        }]
