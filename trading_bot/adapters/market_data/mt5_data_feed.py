from __future__ import annotations

from typing import Any


class MT5DataFeed:
    async def fetch_snapshot(self, symbol: str) -> dict[str, Any]:
        return {"symbol": symbol, "status": "not_implemented"}
