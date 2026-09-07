import asyncio

from trading_bot.adapters.brokers.broker_factory import BrokerFactory
from trading_bot.core.application.broker_orchestrator import BrokerOrchestrator
from trading_bot.core.domain.enums import OrderSide, OrderType
from trading_bot.core.domain.models import OrderRequest


def test_broker_factory_creates_supported_brokers():
    mt5 = BrokerFactory.create("mt5")
    binance = BrokerFactory.create("binance")

    assert mt5.name == "mt5"
    assert binance.name == "binance"
    assert "mt5" in BrokerFactory.available()
    assert "binance" in BrokerFactory.available()


def test_broker_orchestrator_approval_flow():
    async def _run():
        orchestrator = BrokerOrchestrator("binance")
        request = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            volume=0.01,
            client_order_id="abc-123",
        )

        result = await orchestrator.handle_signal("BTCUSDT", "BUY", 0.5, 2.0, request)

        assert result["approved"] is True
        assert result["signal"].symbol == "BTCUSDT"
        assert result["order"].status in {"filled", "new"}

    asyncio.run(_run())
