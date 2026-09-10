from __future__ import annotations

from fastapi import APIRouter

from trading_bot.app.state_store import list_brokers

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _fallback_brokers() -> list[dict[str, object]]:
    return [
        {
            "id": 1,
            "name": "Default Broker",
            "platform": "mt5",
            "default_symbol": "XAUUSD",
            "is_default": True,
            "is_active": True,
            "available": True,
            "execution_mode": "mouse",
            "terminal_path": None,
        }
    ]


@router.get("/summary")
async def dashboard_summary() -> dict[str, object]:
    brokers = list_brokers(include_inactive=True)
    if not brokers:
        brokers = _fallback_brokers()

    normalized = []
    for broker in brokers:
        normalized.append(
            {
                "id": broker.get("id"),
                "name": broker.get("name"),
                "platform": broker.get("platform"),
                "default_symbol": broker.get("default_symbol"),
                "is_default": bool(broker.get("is_default")),
                "is_active": bool(broker.get("is_active")),
                "available": bool(broker.get("is_active")),
                "execution_mode": broker.get("execution_mode"),
                "terminal_path": broker.get("terminal_path"),
            }
        )
    return {"status": "ready", "brokers": normalized, "accounting": "service_ready"}
