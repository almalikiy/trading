from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, TypeVar, cast

T = TypeVar("T")


class RetryPolicy:
    def __init__(self, max_attempts: int = 3, delay_seconds: float = 1.0) -> None:
        self.max_attempts = max_attempts
        self.delay_seconds = delay_seconds

    async def run(self, func: Callable[[], T] | Callable[[], Awaitable[T]], *, on_error: Callable[[Exception], None] | None = None) -> T:
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                result = func()
                if asyncio.iscoroutine(result):
                    result = await result
                return cast(T, result)
            except Exception as exc:  # pragma: no cover - retry policy
                last_error = exc
                if on_error:
                    on_error(exc)
                if attempt == self.max_attempts:
                    raise
                await asyncio.sleep(self.delay_seconds)
        if last_error is not None:
            raise last_error
        raise RuntimeError("retry policy failed without error")
