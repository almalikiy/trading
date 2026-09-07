from __future__ import annotations

from typing import Any


class TradeRepository:
    def __init__(self, store: Any) -> None:
        self.store = store

    async def save_trade(self, trade: dict[str, Any]) -> None:
        return None

    async def list_trades(self) -> list[dict[str, Any]]:
        return []
