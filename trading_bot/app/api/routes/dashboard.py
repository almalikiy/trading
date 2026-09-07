from __future__ import annotations

from fastapi import APIRouter

from trading_bot.adapters.brokers.broker_factory import BrokerFactory

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
async def dashboard_summary() -> dict[str, object]:
    brokers = [
        {"name": broker_name, "available": True}
        for broker_name in BrokerFactory.available()
    ]
    return {"status": "ready", "brokers": brokers, "accounting": "service_ready"}
