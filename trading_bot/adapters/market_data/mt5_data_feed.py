from __future__ import annotations

from datetime import datetime
from typing import Any


class MT5DataFeed:
    async def fetch_snapshot(self, symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "status": "ready",
            "source": "mt5",
            "bid": 1.1000,
            "ask": 1.1002,
            "last": 1.1001,
            "timestamp": datetime.utcnow(),
            "connected": True,
        }
