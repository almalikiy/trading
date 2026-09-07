from __future__ import annotations

from fastapi import APIRouter

from trading_bot.adapters.brokers.broker_factory import BrokerFactory

router = APIRouter(prefix="/positions", tags=["positions"])


@router.get("")
async def list_positions() -> list[dict[str, object]]:
    broker = BrokerFactory.create("mt5")
    return [{"broker": broker.name, "positions": await broker.get_positions()}]
