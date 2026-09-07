from __future__ import annotations

from typing import Any

from .base_strategy import BaseStrategy


class TrendFollowingStrategy(BaseStrategy):
    name = "trend_following"

    async def evaluate(self, market_data: dict[str, Any]) -> dict[str, Any]:
        return {"signal": "hold", "confidence": 0.5, "market_data": market_data}
