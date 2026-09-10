import asyncio
from decimal import Decimal

from trading_bot.core.application.production_guard_service import ProductionGuardService


def test_guard_rejects_lot_above_limit(monkeypatch):
    async def fake_get_account_summary(self):
        return type(
            "Summary",
            (),
            {"balance": Decimal("10000"), "equity": Decimal("10000"), "margin_used": Decimal("200"), "free_margin": Decimal("9800")},
        )()

    async def fake_health_check(self):
        return True

    async def fake_get_symbol_info(self, symbol):
        return {"symbol": symbol, "status": "available"}

    class FakeBroker:
        name = "mt5"

        async def health_check(self):
            return await fake_health_check(self)

        async def get_account_summary(self):
            return await fake_get_account_summary(self)

        async def get_symbol_info(self, symbol):
            return await fake_get_symbol_info(self, symbol)

    monkeypatch.setattr("trading_bot.core.application.production_guard_service.BrokerFactory.create", lambda name: FakeBroker())

    async def _run():
        service = ProductionGuardService()
        result = await service.validate_order_request(
            broker_name="mt5",
            symbol="XAUUSD",
            side="BUY",
            volume=Decimal("2.0"),
            max_lot=Decimal("0.1"),
        )
        assert result["allowed"] is False
        assert any("max_lot" in item.lower() for item in result["errors"])

    asyncio.run(_run())


def test_guard_blocks_when_open_positions_reach_limit(monkeypatch):
    async def fake_get_account_summary(self):
        return type(
            "Summary",
            (),
            {"balance": Decimal("10000"), "equity": Decimal("10000"), "margin_used": Decimal("200"), "free_margin": Decimal("9800")},
        )()

    async def fake_health_check(self):
        return True

    async def fake_get_symbol_info(self, symbol):
        return {"symbol": symbol, "status": "available"}

    async def fake_get_positions(self):
        return [{"symbol": "XAUUSD"}, {"symbol": "EURUSD"}]

    class FakeBroker:
        name = "mt5"

        async def health_check(self):
            return await fake_health_check(self)

        async def get_account_summary(self):
            return await fake_get_account_summary(self)

        async def get_symbol_info(self, symbol):
            return await fake_get_symbol_info(self, symbol)

        async def get_positions(self):
            return await fake_get_positions(self)

    monkeypatch.setattr("trading_bot.core.application.production_guard_service.BrokerFactory.create", lambda name: FakeBroker())

    async def _run():
        service = ProductionGuardService()
        result = await service.validate_order_request(
            broker_name="mt5",
            symbol="XAUUSD",
            side="BUY",
            volume=Decimal("0.05"),
            max_lot=Decimal("0.1"),
            max_open_positions=1,
        )
        assert result["allowed"] is False
        assert any("max_open_positions" in item.lower() for item in result["errors"])

    asyncio.run(_run())


def test_guard_accepts_safe_request(monkeypatch):
    async def fake_get_account_summary(self):
        return type(
            "Summary",
            (),
            {"balance": Decimal("10000"), "equity": Decimal("10000"), "margin_used": Decimal("200"), "free_margin": Decimal("9800")},
        )()

    async def fake_health_check(self):
        return True

    async def fake_get_symbol_info(self, symbol):
        return {"symbol": symbol, "status": "available"}

    async def fake_get_positions(self):
        return [{"symbol": "XAUUSD"}]

    class FakeBroker:
        name = "mt5"

        async def health_check(self):
            return await fake_health_check(self)

        async def get_account_summary(self):
            return await fake_get_account_summary(self)

        async def get_symbol_info(self, symbol):
            return await fake_get_symbol_info(self, symbol)

        async def get_positions(self):
            return await fake_get_positions(self)

    monkeypatch.setattr("trading_bot.core.application.production_guard_service.BrokerFactory.create", lambda name: FakeBroker())

    async def _run():
        service = ProductionGuardService()
        result = await service.validate_order_request(
            broker_name="mt5",
            symbol="XAUUSD",
            side="BUY",
            volume=Decimal("0.05"),
            max_lot=Decimal("0.1"),
            max_open_positions=2,
        )
        assert result["allowed"] is True
        assert result["errors"] == []

    asyncio.run(_run())


def test_guard_blocks_when_kill_switch_is_enabled(monkeypatch):
    async def fake_get_account_summary(self):
        return type(
            "Summary",
            (),
            {"balance": Decimal("10000"), "equity": Decimal("10000"), "margin_used": Decimal("200"), "free_margin": Decimal("9800")},
        )()

    async def fake_health_check(self):
        return True

    async def fake_get_symbol_info(self, symbol):
        return {"symbol": symbol, "status": "available"}

    async def fake_get_positions(self):
        return []

    class FakeBroker:
        name = "mt5"

        async def health_check(self):
            return await fake_health_check(self)

        async def get_account_summary(self):
            return await fake_get_account_summary(self)

        async def get_symbol_info(self, symbol):
            return await fake_get_symbol_info(self, symbol)

        async def get_positions(self):
            return await fake_get_positions(self)

    monkeypatch.setattr("trading_bot.core.application.production_guard_service.BrokerFactory.create", lambda name: FakeBroker())

    async def _run():
        service = ProductionGuardService()
        result = await service.validate_order_request(
            broker_name="mt5",
            symbol="XAUUSD",
            side="BUY",
            volume=Decimal("0.05"),
            max_lot=Decimal("0.1"),
            kill_switch_enabled=True,
        )
        assert result["allowed"] is False
        assert any("kill_switch" in item.lower() for item in result["errors"])

    asyncio.run(_run())


def test_guard_blocks_when_drawdown_exceeds_limit(monkeypatch):
    async def fake_get_account_summary(self):
        return type(
            "Summary",
            (),
            {"balance": Decimal("10000"), "equity": Decimal("10000"), "margin_used": Decimal("200"), "free_margin": Decimal("9800")},
        )()

    async def fake_health_check(self):
        return True

    async def fake_get_symbol_info(self, symbol):
        return {"symbol": symbol, "status": "available"}

    async def fake_get_positions(self):
        return []

    class FakeBroker:
        name = "mt5"

        async def health_check(self):
            return await fake_health_check(self)

        async def get_account_summary(self):
            return await fake_get_account_summary(self)

        async def get_symbol_info(self, symbol):
            return await fake_get_symbol_info(self, symbol)

        async def get_positions(self):
            return await fake_get_positions(self)

    monkeypatch.setattr("trading_bot.core.application.production_guard_service.BrokerFactory.create", lambda name: FakeBroker())

    async def _run():
        service = ProductionGuardService()
        result = await service.validate_order_request(
            broker_name="mt5",
            symbol="XAUUSD",
            side="BUY",
            volume=Decimal("0.05"),
            max_lot=Decimal("0.1"),
            current_drawdown_pct=Decimal("12"),
            max_drawdown_pct=Decimal("10"),
        )
        assert result["allowed"] is False
        assert any("drawdown" in item.lower() for item in result["errors"])

    asyncio.run(_run())
