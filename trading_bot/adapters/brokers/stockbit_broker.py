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
        return AccountSummary(
            broker=self.name,
            balance=Decimal("5000000.00"),
            equity=Decimal("5000000.00"),
            margin_used=Decimal("0.00"),
            free_margin=Decimal("5000000.00"),
            leverage=Decimal("1"),
            currency="IDR",
        )

    async def get_ticker(self, symbol: str) -> SymbolQuote:
        price = Decimal("1000")
        return SymbolQuote(
            symbol=symbol,
            bid=price,
            ask=price + Decimal("5"),
            last=price,
            timestamp=datetime.utcnow(),
            spread=Decimal("5"),
        )

    async def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> list[Candle]:
        return [
            Candle(
                symbol=symbol,
                timeframe=timeframe,
                open=Decimal("990"),
                high=Decimal("1015"),
                low=Decimal("985"),
                close=Decimal("1005"),
                volume=Decimal("5000"),
                timestamp=datetime.utcnow(),
            )
        ]

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
            raw_response={"source": "stockbit_skeleton", "request": request.metadata},
        )

    async def cancel_order(self, order_id: str) -> bool:
        return False

    async def get_order_status(self, order_id: str) -> dict[str, Any]:
        return {"order_id": order_id, "status": "queued"}

    async def get_symbol_info(self, symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "status": "skeleton",
            "lot_size": 1,
            "tick_size": 1,
            "currency": "IDR",
        }
