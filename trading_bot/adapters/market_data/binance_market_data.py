from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from trading_bot.adapters.market_data.base_market_data import BaseMarketDataAdapter


class BinanceMarketDataAdapter(BaseMarketDataAdapter):
    source = "binance"

    async def fetch_snapshot(self, symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "bid": Decimal("50000.00"),
            "ask": Decimal("50001.50"),
            "last": Decimal("50000.75"),
            "timestamp": datetime.utcnow(),
            "source": self.source,
        }

    async def fetch_bars(self, symbol: str, timeframe: str, limit: int = 200) -> list[dict[str, Any]]:
        return [{
            "symbol": symbol,
            "timeframe": timeframe,
            "open": Decimal("49980"),
            "high": Decimal("50120"),
            "low": Decimal("49950"),
            "close": Decimal("50040"),
            "volume": Decimal("12.5"),
            "timestamp": datetime.utcnow(),
            "source": self.source,
        }]
