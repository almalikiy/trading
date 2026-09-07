from __future__ import annotations

from typing import Any


class BinanceWSFeed:
    async def fetch_snapshot(self, symbol: str) -> dict[str, Any]:
        return {"symbol": symbol, "status": "not_implemented"}
