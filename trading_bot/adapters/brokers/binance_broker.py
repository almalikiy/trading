from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from trading_bot.adapters.brokers.base_adapter import BaseAdapter
from trading_bot.core.domain.enums import OrderType
from trading_bot.core.domain.models import AccountSummary, Candle, OrderExecution, OrderRequest, Position, SymbolQuote


class BinanceBrokerAdapter(BaseAdapter):
    name = "binance"

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
            raise RuntimeError("Binance broker is not connected")

        return AccountSummary(
            broker=self.name,
            balance=Decimal("0.00"),
            equity=Decimal("0.00"),
            margin_used=Decimal("0.00"),
            free_margin=Decimal("0.00"),
            leverage=Decimal("1"),
            currency="USDT",
        )

    async def get_ticker(self, symbol: str) -> SymbolQuote:
        if not self.connected:
            raise RuntimeError("Binance broker is not connected")

        raise RuntimeError("Binance broker market data is unavailable until a live connection is established")

    async def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> list[Candle]:
        if not self.connected:
            return []
        return []

    async def get_positions(self) -> list[Position]:
        return []

    async def get_position(self, symbol: str) -> Position | None:
        return None

    async def place_order(self, request: OrderRequest) -> OrderExecution:
        status = "filled" if request.order_type == OrderType.MARKET else "new"
        return OrderExecution(
            broker=self.name,
            symbol=request.symbol,
            order_id=f"binance-{request.symbol.lower()}-{request.side.value.lower()}",
            client_order_id=request.client_order_id,
            side=request.side,
            status=status,
            filled_volume=request.volume,
            average_price=request.price or Decimal("0"),
            raw_response={"source": "binance_adapter", "request": request.metadata},
        )

    async def cancel_order(self, order_id: str) -> bool:
        return False

    async def get_order_status(self, order_id: str) -> dict[str, Any]:
        return {"order_id": order_id, "status": "new"}

    async def get_symbol_info(self, symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "status": "offline",
            "base_precision": 8,
            "quote_precision": 2,
            "min_notional": 10,
        }
