from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseMarketDataAdapter(ABC):
    source: str = "base"

    @abstractmethod
    async def fetch_snapshot(self, symbol: str) -> dict[str, Any]:
        """Fetch normalized market snapshot."""

    @abstractmethod
    async def fetch_bars(self, symbol: str, timeframe: str, limit: int = 200) -> list[dict[str, Any]]:
        """Fetch normalized OHLCV bar history."""
