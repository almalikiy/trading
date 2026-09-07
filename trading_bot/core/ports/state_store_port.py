from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class StateStorePort(ABC):
    @abstractmethod
    async def get(self, key: str) -> Any:
        """Get a value for key."""

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set a value for key."""
