from __future__ import annotations

import importlib

from fastapi import APIRouter, Body, HTTPException

from trading_bot.app import db
from trading_bot.app.api.routes.brokers.models import BrokerCreateRequest, BrokerUpdateRequest, TradeCloseRequest, TradeOpenRequest
from trading_bot.app.api.routes.brokers import service

router = APIRouter(tags=["brokers"])


def _resolve_default_broker_callable():
    pkg = importlib.import_module("trading_bot.app.api.routes.brokers")
    return getattr(pkg, "get_default_broker", service.get_default_broker)


@router.get("/brokers")
async def get_brokers(include_inactive: bool = False) -> list[dict[str, object]]:
    return db.list_brokers(include_inactive=include_inactive)


@router.get("/brokers/default")
async def get_default_broker_route() -> dict[str, object]:
    broker = _resolve_default_broker_callable()()
    if not broker:
        raise HTTPException(status_code=404, detail="No broker configured")
    return broker


@router.get("/brokers/{broker_id}/order_status")
async def get_broker_order_status(broker_id: int, symbol: str = "XAUUSD") -> dict[str, object]:
    broker = db.get_broker(broker_id)
    if not broker:
        raise HTTPException(status_code=404, detail="Broker not found")
    return service.broker_order_status_snapshot(broker, symbol=symbol)


@router.post("/brokers")
async def add_broker(payload: BrokerCreateRequest) -> dict[str, object]:
    try:
        data = payload.model_dump()
        if data.get("platform") == "mt4" and data.get("execution_mode") == "direct":
            data["execution_mode"] = "mouse"
        if data.get("default_symbol") is not None:
            data["default_symbol"] = str(data.get("default_symbol") or "").strip() or None
        broker = db.create_broker(data)
        return {"status": "ok", "broker": broker}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/brokers/{broker_id}")
async def edit_broker(broker_id: int, payload: BrokerUpdateRequest) -> dict[str, object]:
    updates = payload.model_dump(exclude_unset=True)
    current = db.get_broker(broker_id)
    if not current:
        raise HTTPException(status_code=404, detail="Broker not found")

    target_platform = updates.get("platform", current.get("platform"))
    target_mode = updates.get("execution_mode", current.get("execution_mode"))
    if target_platform == "mt4" and target_mode == "direct":
        updates["execution_mode"] = "mouse"

    if "default_symbol" in updates:
        updates["default_symbol"] = str(updates.get("default_symbol") or "").strip() or None

    broker = db.update_broker(broker_id, updates)
    if not broker:
        raise HTTPException(status_code=404, detail="Broker not found")
    return {"status": "ok", "broker": broker}


@router.delete("/brokers/{broker_id}")
async def remove_broker(broker_id: int) -> dict[str, str]:
    ok = db.delete_broker(broker_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Broker not found")
    return {"status": "ok"}


@router.post("/brokers/{broker_id}/set_default")
async def set_broker_default(broker_id: int) -> dict[str, object]:
    broker = db.set_default_broker(broker_id)
    if not broker:
        raise HTTPException(status_code=404, detail="Broker not found")
    return {"status": "ok", "broker": broker}


@router.post("/trade/open_v2")
async def open_trade_v2(payload: TradeOpenRequest) -> dict[str, object]:
    return service.open_trade_v2(payload)


@router.post("/trade/close_v2")
async def close_trade_v2(payload: TradeCloseRequest) -> dict[str, object]:
    return service.close_trade_v2(payload)


@router.post("/trade/close_latest_if_single")
async def close_latest_if_single(broker_id: int | None = Body(default=None)) -> dict[str, object]:
    return service.close_latest_if_single(broker_id)
