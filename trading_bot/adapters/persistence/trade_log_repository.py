from __future__ import annotations

from typing import Any


class TradeLogRepository:
    def __init__(self) -> None:
        self._items: list[dict[str, Any]] = []

    async def append(self, record: dict[str, Any]) -> None:
        self._items.append(record)

    async def list(self) -> list[dict[str, Any]]:
        return list(self._items)
