import asyncio

from trading_bot.adapters.market_data.binance_market_data import BinanceMarketDataAdapter
from trading_bot.adapters.market_data.mt5_market_data import MT5MarketDataAdapter
from trading_bot.adapters.persistence.state_repository import StateRepository
from trading_bot.adapters.persistence.trade_log_repository import TradeLogRepository
from trading_bot.core.application.market_data_service import MarketDataService


def test_market_data_services_normalize_snapshot():
    async def _run():
        mt5 = MarketDataService(MT5MarketDataAdapter())
        binance = MarketDataService(BinanceMarketDataAdapter())

        mt5_snapshot = await mt5.get_snapshot("EURUSD")
        binance_snapshot = await binance.get_snapshot("BTCUSDT")

        assert mt5_snapshot["source"] == "mt5"
        assert binance_snapshot["source"] == "binance"
        assert mt5_snapshot["symbol"] == "EURUSD"
        assert binance_snapshot["symbol"] == "BTCUSDT"

    asyncio.run(_run())


def test_mt5_market_data_does_not_fake_prices_when_unavailable(monkeypatch):
    import trading_bot.adapters.market_data.mt5_market_data as mt5_market_data_module

    async def _run():
        monkeypatch.setattr(mt5_market_data_module, "MetaTrader5", None)
        adapter = MT5MarketDataAdapter()

        snapshot = await adapter.fetch_snapshot("EURUSD")
        bars = await adapter.fetch_bars("EURUSD", "M1", limit=20)

        assert snapshot["symbol"] == "EURUSD"
        assert snapshot["connected"] is False
        assert snapshot.get("last") is None
        assert snapshot.get("bid") is None
        assert snapshot.get("ask") is None
        assert bars == []

    asyncio.run(_run())


def test_persistence_repositories_store_state():
    async def _run():
        state = StateRepository()
        trade_log = TradeLogRepository()

        await state.set("mode", "live")
        await trade_log.append({"symbol": "EURUSD", "status": "open"})

        assert await state.get("mode") == "live"
        assert (await trade_log.list())[0]["symbol"] == "EURUSD"

    asyncio.run(_run())
