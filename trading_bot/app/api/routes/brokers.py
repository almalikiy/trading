from __future__ import annotations

from fastapi import APIRouter, HTTPException

from trading_bot.app.state_store import get_default_broker, list_brokers

router = APIRouter(tags=["brokers"])


def _fallback_brokers() -> list[dict[str, object]]:
    return [
        {
            "id": 1,
            "name": "Default Broker",
            "platform": "mt5",
            "terminal_path": None,
            "execution_mode": "mouse",
            "default_symbol": "XAUUSD",
            "is_default": True,
            "is_active": True,
            "available": True,
        }
    ]


@router.get("/brokers")
async def get_brokers(include_inactive: bool = False) -> list[dict[str, object]]:
    brokers = list_brokers(include_inactive=include_inactive)
    if brokers:
        return brokers
    return _fallback_brokers()


@router.get("/brokers/default")
async def get_default_broker_route() -> dict[str, object]:
    broker = get_default_broker()
    if broker:
        return broker
    return _fallback_brokers()[0]
