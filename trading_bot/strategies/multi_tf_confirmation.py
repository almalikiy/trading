from __future__ import annotations

from typing import Any

from .base_strategy import BaseStrategy


class MultiTimeframeConfirmationStrategy(BaseStrategy):
    name = "multi_tf_confirmation"

    async def evaluate(self, market_data: dict[str, Any]) -> dict[str, Any]:
        return {"signal": "hold", "confidence": 0.5, "market_data": market_data}
