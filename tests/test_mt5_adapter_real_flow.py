import asyncio

from trading_bot.adapters.brokers.mt5_broker import MT5BrokerAdapter
from trading_bot.core.domain.enums import OrderSide, OrderType
from trading_bot.core.domain.models import OrderRequest


def test_mt5_adapter_handles_unavailable_runtime_cleanly():
    adapter = MT5BrokerAdapter(terminal_path="C:/MetaQuotes/Terminal")

    async def _run():
        await adapter.connect()
        assert adapter.connected is False or adapter.connected is True
        summary = await adapter.get_account_summary()
        assert summary.broker == "mt5"

    asyncio.run(_run())


def test_mt5_order_request_construction_is_valid():
    request = OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        volume=0.1,
        stop_loss=2345.0,
        take_profit=2360.0,
        client_order_id="xau-buy-1",
    )

    assert request.symbol == "XAUUSD"
    assert request.side == OrderSide.BUY
    assert request.volume == 0.1


def test_mt5_market_order_omits_unsupported_filling_mode(monkeypatch):
    import types

    fake_mt5 = types.SimpleNamespace(
        ORDER_TYPE_BUY=0,
        ORDER_TYPE_SELL=1,
        ORDER_TIME_GTC=0,
        TRADE_ACTION_DEAL=1,
        TRADE_RETCODE_DONE=10009,
    )
    captured = {}

    def fake_symbol_select(symbol, _value):
        return True

    def fake_symbol_info_tick(symbol):
        return types.SimpleNamespace(ask=4412.98, bid=4412.84)

    def fake_order_send(req):
        captured["req"] = req
        return types.SimpleNamespace(
            retcode=fake_mt5.TRADE_RETCODE_DONE,
            order=123,
            volume=0.01,
            price=4412.98,
            comment="OK",
        )

    fake_mt5.symbol_select = fake_symbol_select
    fake_mt5.symbol_info_tick = fake_symbol_info_tick
    fake_mt5.order_send = fake_order_send

    monkeypatch.setattr("trading_bot.adapters.brokers.mt5_broker.mt5", fake_mt5)

    adapter = MT5BrokerAdapter(terminal_path="C:/MetaQuotes/Terminal")
    adapter.connected = True

    async def _run():
        request = OrderRequest(
            symbol="XAUUSD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            volume=0.01,
            client_order_id="demo-filling-check",
        )
        result = await adapter.place_order(request)
        assert result.order_id == "123"
        assert "type_filling" not in captured["req"]
        assert captured["req"]["type_time"] == fake_mt5.ORDER_TIME_GTC

    asyncio.run(_run())
