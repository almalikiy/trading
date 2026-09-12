from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from trading_bot.adapters.brokers.broker_factory import BrokerFactory
from trading_bot.app import db
from trading_bot.app.terminal_adapters import get_background_mt5_sync_status

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


@router.get("/background_sync_status")
async def mt5_background_sync_status() -> dict[str, Any]:
    return get_background_mt5_sync_status()


@router.get("/error_log")
async def mt5_error_log(limit: int = 200) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit or 200), 5000))
    rows = db.get_mt5_error_log(limit=safe_limit)
    return {"status": "ok", "count": len(rows), "errors": rows}


@router.get("/error_log_summary")
async def mt5_error_log_summary(limit: int = 500) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit or 500), 10000))
    rows = db.get_mt5_error_log(limit=safe_limit)
    total = len(rows)
    latest = rows[0] if rows else None

    by_broker: dict[str, int] = {}
    for row in rows:
        key = str(row.get("broker_name") or row.get("broker_id") or "unknown")
        by_broker[key] = by_broker.get(key, 0) + 1

    return {
        "status": "ok",
        "total": total,
        "latest": latest,
        "by_broker": by_broker,
        "has_errors": total > 0,
    }


@router.post("/error_log/clear")
async def mt5_error_log_clear() -> dict[str, Any]:
    db.clear_mt5_error_log()
    return {"status": "ok", "message": "MT5 error log cleared"}
