from __future__ import annotations

from datetime import datetime
from typing import Any


class BinanceWSFeed:
    async def fetch_snapshot(self, symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "status": "ready",
            "source": "binance_ws",
            "bid": 50000.0,
            "ask": 50001.5,
            "last": 50000.75,
            "timestamp": datetime.utcnow(),
            "connected": True,
        }
