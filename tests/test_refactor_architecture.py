from decimal import Decimal

from trading_bot.core.domain.models import Candle, OrderRequest, OrderSide, OrderType, Position, PositionSide, SymbolQuote
from trading_bot.core.ports.broker_port import BaseBroker


def test_base_broker_contract_is_abstract():
    assert BaseBroker.__abstractmethods__


def test_trade_models_are_normalized():
    quote = SymbolQuote(
        symbol="XAUUSD",
        bid=Decimal("2330.10"),
        ask=Decimal("2330.30"),
        last=Decimal("2330.20"),
        timestamp=None,
    )
    assert quote.symbol == "XAUUSD"
    assert quote.ask > quote.bid

    order = OrderRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        volume=Decimal("0.01"),
    )
    assert order.side == OrderSide.BUY
    assert order.volume == Decimal("0.01")

    candle = Candle(
        symbol="EURUSD",
        timeframe="M1",
        open=Decimal("1.0900"),
        high=Decimal("1.0910"),
        low=Decimal("1.0890"),
        close=Decimal("1.0905"),
        volume=Decimal("1000"),
        timestamp=None,
    )
    assert candle.close > candle.open

    position = Position(
        broker="binance",
        symbol="BTCUSDT",
        side=PositionSide.LONG,
        volume=Decimal("0.01"),
        entry_price=Decimal("60000"),
        mark_price=Decimal("61000"),
    )
    assert position.side == PositionSide.LONG
    assert position.pnl == Decimal("0")
