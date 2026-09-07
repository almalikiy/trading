"""Bootstrap and startup wiring for the trading system."""

from trading_bot.adapters.brokers.broker_factory import BrokerFactory
from trading_bot.infrastructure.config.settings import get_settings


def bootstrap() -> dict[str, object]:
    settings = get_settings()
    return {
        "app_name": settings.app_name,
        "environment": settings.environment,
        "debug": settings.debug,
        "available_brokers": BrokerFactory.available(),
    }
