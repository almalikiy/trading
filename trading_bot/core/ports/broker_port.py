from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from trading_bot.core.domain.models import AccountSummary, Candle, OrderExecution, OrderRequest, Position, SymbolQuote


class BaseBroker(ABC):
    """Unified adapter contract for all broker/exchange integrations."""

    name: str

    @abstractmethod
    async def connect(self) -> None:
        """Establish session/authentication."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close session."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return broker health."""

    @abstractmethod
    async def get_account_summary(self) -> AccountSummary:
        """Return account metrics."""

    @abstractmethod
    async def get_ticker(self, symbol: str) -> SymbolQuote:
        """Return quote for a symbol."""

    @abstractmethod
    async def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> list[Candle]:
        """Return normalized OHLCV history."""

    @abstractmethod
    async def get_positions(self) -> list[Position]:
        """Return open positions."""

    @abstractmethod
    async def get_position(self, symbol: str) -> Position | None:
        """Return the current position for a single symbol."""

    @abstractmethod
    async def place_order(self, request: OrderRequest) -> OrderExecution:
        """Submit an order request."""

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel order by id."""

    @abstractmethod
    async def get_order_status(self, order_id: str) -> dict[str, Any]:
        """Return order-state metadata."""

    @abstractmethod
    async def get_symbol_info(self, symbol: str) -> dict[str, Any]:
        """Return market constraints and precision data."""


__all__ = ["BaseBroker"]
