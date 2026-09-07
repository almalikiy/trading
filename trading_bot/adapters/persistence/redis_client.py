from __future__ import annotations

from typing import Any


class RedisClient:
    def __init__(self, url: str = "redis://localhost:6379/0") -> None:
        self.url = url

    async def get(self, key: str) -> Any:
        return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        return None
