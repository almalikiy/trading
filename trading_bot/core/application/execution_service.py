from __future__ import annotations

from typing import Any


class ExecutionService:
    def __init__(self, broker: Any) -> None:
        self.broker = broker

    async def execute(self, request: Any) -> Any:
        return await self.broker.place_order(request)
