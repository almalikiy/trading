from __future__ import annotations

from typing import Any


class MarketDataService:
    def __init__(self, adapter: Any) -> None:
        self.adapter = adapter

    async def get_snapshot(self, symbol: str) -> dict[str, Any]:
        return await self.adapter.fetch_snapshot(symbol)

    async def get_bars(self, symbol: str, timeframe: str, limit: int = 200) -> list[dict[str, Any]]:
        return await self.adapter.fetch_bars(symbol, timeframe, limit)
