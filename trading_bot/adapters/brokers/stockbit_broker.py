from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from trading_bot.adapters.brokers.base_adapter import BaseAdapter
from trading_bot.core.domain.enums import OrderType
from trading_bot.core.domain.models import AccountSummary, Candle, OrderExecution, OrderRequest, Position, SymbolQuote


class StockbitBrokerAdapter(BaseAdapter):
    name = "stockbit"

    def __init__(self) -> None:
        self.connected = False

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def health_check(self) -> bool:
        return self.connected

    async def get_account_summary(self) -> AccountSummary:
        if not self.connected:
            raise RuntimeError("Stockbit broker is not connected")

        raise RuntimeError("Stockbit broker account data is unavailable until a live connection is established")

    async def get_ticker(self, symbol: str) -> SymbolQuote:
        if not self.connected:
            raise RuntimeError("Stockbit broker is not connected")

        raise RuntimeError("Stockbit broker ticker data is unavailable until a live connection is established")

    async def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> list[Candle]:
        if not self.connected:
            return []
        return []

    async def get_positions(self) -> list[Position]:
        return []

    async def get_position(self, symbol: str) -> Position | None:
        return None

    async def place_order(self, request: OrderRequest) -> OrderExecution:
        status = "queued" if request.order_type != OrderType.MARKET else "filled"
        return OrderExecution(
            broker=self.name,
            symbol=request.symbol,
            order_id=f"stockbit-{request.symbol.lower()}-{request.side.value.lower()}",
            client_order_id=request.client_order_id,
            side=request.side,
            status=status,
            filled_volume=request.volume,
            average_price=request.price or Decimal("0"),
            raw_response={"source": "stockbit_adapter", "request": request.metadata},
        )

    async def cancel_order(self, order_id: str) -> bool:
        return False

    async def get_order_status(self, order_id: str) -> dict[str, Any]:
        return {"order_id": order_id, "status": "queued"}

    async def get_symbol_info(self, symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "status": "offline",
            "lot_size": 1,
            "tick_size": 1,
            "currency": "IDR",
        }
