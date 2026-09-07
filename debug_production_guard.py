from decimal import Decimal
import asyncio
from trading_bot.core.application.production_guard_service import ProductionGuardService

async def fake_get_account_summary(self):
    return type('Summary', (), {'balance': Decimal('10000'), 'equity': Decimal('10000'), 'margin_used': Decimal('200'), 'free_margin': Decimal('9800')})()

async def fake_health_check(self):
    return True

async def fake_get_symbol_info(self, symbol):
    return {'symbol': symbol, 'status': 'available'}

class FakeBroker:
    name = 'mt5'
    async def health_check(self):
        return await fake_health_check(self)
    async def get_account_summary(self):
        return await fake_get_account_summary(self)
    async def get_symbol_info(self, symbol):
        return await fake_get_symbol_info(symbol)

import trading_bot.core.application.production_guard_service as mod
mod.BrokerFactory.create = lambda name: FakeBroker()

async def main():
    service = ProductionGuardService()
    result = await service.validate_order_request('mt5', 'XAUUSD', 'BUY', Decimal('0.05'), Decimal('0.1'))
    print(result)

asyncio.run(main())
