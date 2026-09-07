from __future__ import annotations

from typing import Any


class PostgresTradeRepository:
    def __init__(self, dsn: str = "postgresql://postgres:postgres@localhost:5432/trading") -> None:
        self.dsn = dsn

    async def list(self) -> list[dict[str, Any]]:
        return []

    async def save(self, record: dict[str, Any]) -> None:
        return None
