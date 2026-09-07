from __future__ import annotations

from trading_bot.adapters.brokers.binance_broker import BinanceBrokerAdapter
from trading_bot.adapters.brokers.mt5_broker import MT5BrokerAdapter
from trading_bot.adapters.brokers.stockbit_broker import StockbitBrokerAdapter


class BrokerFactory:
    registry = {
        "mt5": MT5BrokerAdapter,
        "binance": BinanceBrokerAdapter,
        "stockbit": StockbitBrokerAdapter,
    }

    @classmethod
    def create(cls, name: str):
        key = str(name).strip().lower()
        factory = cls.registry.get(key)
        if factory is None:
            raise ValueError(f"Unsupported broker: {name}")
        return factory()

    @classmethod
    def available(cls) -> list[str]:
        return sorted(cls.registry.keys())
