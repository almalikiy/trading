from __future__ import annotations

from typing import Any


class PostgresRepository:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    async def fetch(self, query: str) -> list[dict[str, Any]]:
        return []

    async def execute(self, query: str, params: dict[str, Any] | None = None) -> None:
        return None
