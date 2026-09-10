from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body

from trading_bot.app.state_store import get_account_state, save_account_state

router = APIRouter(tags=["account"])


def _coerce_enabled(value: Any) -> bool:
    if isinstance(value, dict):
        value = value.get("enabled", False)
    return bool(value)


@router.get("/account/state")
async def get_account_state_route() -> dict[str, object]:
    return get_account_state()


@router.get("/account/auto_trade_health")
async def get_auto_trade_health_route() -> dict[str, object]:
    state = get_account_state()
    enabled = bool(state.get("auto_trade_enabled", False))
    return {
        "status": "ok",
        "active": enabled,
        "auto_trade_enabled": enabled,
        "blockers": [],
        "checks": [
            {"key": "auto_trade_enabled", "ok": enabled, "value": enabled, "message": "Auto trade enabled"},
            {"key": "real_trade_enabled", "ok": bool(state.get("enable_real_trade", False)), "value": bool(state.get("enable_real_trade", False)), "message": "Real trading enabled"},
            {"key": "symbol", "ok": True, "value": state.get("auto_trade_symbol") or "XAUUSD", "message": "Active symbol"},
        ],
        "symbol": state.get("auto_trade_symbol") or "XAUUSD",
        "feed_broker": None,
    }


@router.post("/account/set_auto_trade_enabled")
async def set_auto_trade_enabled_route(payload: Any = Body(...)) -> dict[str, object]:
    enabled = _coerce_enabled(payload)
    state = get_account_state()
    state["auto_trade_enabled"] = enabled
    save_account_state(state)
    return {"status": "ok", "auto_trade_enabled": state["auto_trade_enabled"]}


@router.post("/account/set_enable_real_trade")
async def set_enable_real_trade_route(payload: Any = Body(...)) -> dict[str, object]:
    enabled = _coerce_enabled(payload)
    state = get_account_state()
    state["enable_real_trade"] = enabled
    save_account_state(state)
    return {"status": "ok", "enable_real_trade": state["enable_real_trade"]}


@router.get("/account/auto_trade_constraints")
async def get_auto_trade_constraints_route() -> dict[str, object]:
    state = get_account_state()
    return {
        "status": "ok",
        "constraints": {
            "max_open_trades": int(state.get("max_open_trades") or 1),
            "lot": float(state.get("lot") or 0.01),
            "symbol": state.get("auto_trade_symbol") or "XAUUSD",
            "risk_percent": float(state.get("auto_trade_risk_percent") or 1.0),
        },
    }


@router.get("/account/auto_trade_stats")
async def get_auto_trade_stats_route() -> dict[str, object]:
    return {"status": "ok", "stats": {}}


@router.get("/account/auto_trade_events")
async def get_auto_trade_events_route() -> dict[str, object]:
    return {"status": "ok", "rows": 0, "events": []}


@router.get("/account/auto_trade_close_decision_dataset")
async def get_auto_trade_close_decision_dataset_route() -> dict[str, object]:
    return {"status": "ok", "rows": 0, "dataset": []}


@router.get("/account/auto_trade_ml_dataset")
async def get_auto_trade_ml_dataset_route() -> dict[str, object]:
    return {"status": "ok", "rows": 0, "dataset": []}
