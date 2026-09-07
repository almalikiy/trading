from __future__ import annotations

from typing import Any

from trading_bot.core.domain.models import AccountSummary, Candle, OrderExecution, OrderRequest, Position, SymbolQuote
from trading_bot.core.ports.broker_port import BaseBroker


class BaseAdapter(BaseBroker):
    """Concrete base adapter for shared broker behavior."""

    name = "base"

    async def connect(self) -> None:
        return None

    async def disconnect(self) -> None:
        return None

    async def health_check(self) -> bool:
        return True

    async def get_account_summary(self) -> AccountSummary:
        raise NotImplementedError

    async def get_ticker(self, symbol: str) -> SymbolQuote:
        raise NotImplementedError

    async def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> list[Candle]:
        raise NotImplementedError

    async def get_positions(self) -> list[Position]:
        raise NotImplementedError

    async def get_position(self, symbol: str) -> Position | None:
        raise NotImplementedError

    async def place_order(self, request: OrderRequest) -> OrderExecution:
        raise NotImplementedError

    async def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError

    async def get_order_status(self, order_id: str) -> dict[str, Any]:
        raise NotImplementedError

    async def get_symbol_info(self, symbol: str) -> dict[str, Any]:
        raise NotImplementedError


__all__ = ["BaseAdapter"]
