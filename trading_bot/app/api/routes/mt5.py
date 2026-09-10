from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from trading_bot.adapters.brokers.broker_factory import BrokerFactory

router = APIRouter(prefix="/mt5", tags=["mt5"])


@router.get("/status")
async def mt5_status() -> dict[str, Any]:
    try:
        broker = BrokerFactory.create("mt5")
    except Exception as exc:
        return {
            "status": "error",
            "connected": False,
            "ready": False,
            "message": f"MT5 adapter unavailable: {exc}",
        }

    try:
        if hasattr(broker, "connected") and not bool(getattr(broker, "connected", False)):
            await broker.connect()
        connected = bool(getattr(broker, "connected", False))
        healthy = bool(await broker.health_check()) if connected else False
        return {
            "status": "ok" if healthy else "degraded",
            "connected": connected,
            "ready": healthy,
            "broker": getattr(broker, "name", "mt5"),
        }
    except Exception as exc:
        return {
            "status": "error",
            "connected": False,
            "ready": False,
            "broker": getattr(broker, "name", "mt5"),
            "message": str(exc),
        }
