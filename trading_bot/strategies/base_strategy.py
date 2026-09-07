from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseStrategy(ABC):
    name: str = "base"

    @abstractmethod
    async def evaluate(self, market_data: dict[str, Any]) -> dict[str, Any]:
        """Return a normalized signal payload."""
