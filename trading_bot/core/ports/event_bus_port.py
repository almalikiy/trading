from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class EventBusPort(ABC):
    @abstractmethod
    async def publish(self, event: Any) -> None:
        """Publish an event."""
