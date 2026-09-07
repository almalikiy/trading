from __future__ import annotations

from abc import ABC, abstractmethod


class DataProviderPort(ABC):
    @abstractmethod
    async def get_market_snapshot(self, symbol: str) -> dict[str, object]:
        """Return a normalized market snapshot."""
