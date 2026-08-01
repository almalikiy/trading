import os
import subprocess
import time
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

from .db import (
    close_trade_record,
    create_broker,
    delete_broker,
    get_account_state,
    get_broker,
    get_default_broker,
    get_open_trades_count,
    list_open_trades,
    list_brokers,
    log_mt5_error,
    save_account_state,
    set_default_broker,
    create_trade_open_record,
    update_broker,
)
from .terminal_adapters import get_broker_adapter, get_broker_order_status_snapshot, probe_broker_order_status

router = APIRouter(tags=["brokers"])


class BrokerCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    platform: Literal["mt4", "mt5"] = "mt5"
    default_symbol: str | None = None 
    terminal_path: Optional[str] = None
    execution_mode: Literal["mouse", "direct"] = "mouse"
    window_hint: Optional[str] = "FinexBisnisSolusi"


class BrokerUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    platform: Optional[Literal["mt4", "mt5"]] = None
    default_symbol: str | None = None 
    terminal_path: Optional[str] = None
    execution_mode: Optional[Literal["mouse", "direct"]] = None
    window_hint: Optional[str] = None
    is_active: Optional[bool] = None


class TradeOpenRequest(BaseModel):
    symbol: str
    lot: float = 0.01
    trade_type: Literal["buy", "sell"]
    signal_time: Optional[float] = None
    broker_id: Optional[int] = None
    order_method: Optional[Literal["mouse", "direct"]] = None


class TradeCloseRequest(BaseModel):
    symbol: str
    lot: float = 0.01
    ticket: int
    broker_id: Optional[int] = None


@router.get("/brokers")
def get_brokers(include_inactive: bool = False):
    return list_brokers(include_inactive=include_inactive)


@router.get("/brokers/default")
def get_broker_default():
    broker = get_default_broker()
    if not broker:
        raise HTTPException(status_code=404, detail="No broker configured")
    return broker


@router.get("/brokers/{broker_id}/order_status")
def get_broker_order_status(broker_id: int, symbol: str = "XAUUSD"):
    broker = get_broker(broker_id)
    if not broker:
        raise HTTPException(status_code=404, detail="Broker not found")
    return get_broker_order_status_snapshot(broker, symbol=symbol)


@router.post("/brokers")
def add_broker(payload: BrokerCreateRequest):
    try:
        data = payload.model_dump()
        if data.get("platform") == "mt4" and data.get("execution_mode") == "direct":
            data["execution_mode"] = "mouse"
        broker = create_broker(data)
        return {"status": "ok", "broker": broker}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/brokers/{broker_id}")
def edit_broker(broker_id: int, payload: BrokerUpdateRequest):
    updates = payload.model_dump(exclude_unset=True)
    current = get_broker(broker_id)
    if not current:
        raise HTTPException(status_code=404, detail="Broker not found")

    target_platform = updates.get("platform", current.get("platform"))
    target_mode = updates.get("execution_mode", current.get("execution_mode"))
    if target_platform == "mt4" and target_mode == "direct":
        updates["execution_mode"] = "mouse"

    # Pastikan default_symbol ikut diproses
    if "default_symbol" in updates:
        updates["default_symbol"] = updates["default_symbol"].strip() or None

    broker = update_broker(broker_id, updates)
    if not broker:
        raise HTTPException(status_code=404, detail="Broker not found")
    return {"status": "ok", "broker": broker}


@router.delete("/brokers/{broker_id}")
def remove_broker(broker_id: int):
    ok = delete_broker(broker_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Broker not found")
    return {"status": "ok"}


@router.post("/brokers/{broker_id}/set_default")
def set_broker_default(broker_id: int):
    broker = set_default_broker(broker_id)
    if not broker:
        raise HTTPException(status_code=404, detail="Broker not found")
    return {"status": "ok", "broker": broker}


def _resolve_broker(broker_id: Optional[int]):
    broker = get_broker(broker_id) if broker_id else get_default_broker()
    if not broker:
        raise HTTPException(status_code=404, detail="Broker not configured")
    if not broker.get("is_active", True):
        raise HTTPException(status_code=400, detail="Broker is inactive")
    return broker


@router.post("/trade/open_v2")
def open_trade_v2(payload: TradeOpenRequest):
    state = get_account_state()
    if not state.get("enable_real_trade", False):
        return {"status": "error", "message": "Real trading not enabled"}

    if payload.signal_time is not None and (time.time() - payload.signal_time) > 60:
        return {"status": "skipped", "message": "Signal expired, trade skipped"}

    broker = _resolve_broker(payload.broker_id)
    method = payload.order_method or broker.get("execution_mode", "mouse")

    if broker.get("platform") == "mt4" and method == "direct":
        method = "mouse"

    try:
        adapter, method = get_broker_adapter(broker, method)
        result = adapter.open_trade(payload.symbol, payload.lot, payload.trade_type)
        entry_price = result.get("order", {}).get("price")
        ticket = result.get("order", {}).get("ticket")

        now = int(time.time())
        tp_value = state.get("tp_value", 0.5)
        sl_value = state.get("sl_value", None)
        if state.get("auto_analytic_tpsl", False):
            tp_value = round(2 * float(payload.lot), 2)
            sl_value = round(1 * float(payload.lot), 2)
            state["tp_value"] = tp_value
            state["sl_value"] = sl_value
            save_account_state(state)

        trade_id = str(uuid.uuid4())
        create_trade_open_record(
            {
            "trade_id": trade_id,
                "type": payload.trade_type.upper(),
            "symbol": payload.symbol,
            "lot": payload.lot,
            "ticket": ticket,
                "entry": entry_price,
                "entryTime": now,
                "reason": "open_v2",
                "tpValue": tp_value,
                "slValue": sl_value,
                "broker_id": broker["id"],
                "broker_name": broker["name"],
                "platform": broker["platform"],
                "execution_mode": method,
                "terminal_path": broker.get("terminal_path"),
            }
        )

        return {
            "status": "ok",
            "result": result,
            "trade_id": trade_id,
            "broker": broker,
            "execution_mode": method,
        }
    except Exception as exc:
        log_mt5_error(str(exc), broker_id=broker.get("id"), broker_name=broker.get("name"))
        return {"status": "error", "message": str(exc), "broker": broker}


@router.post("/trade/close_v2")
def close_trade_v2(payload: TradeCloseRequest):
    state = get_account_state()
    if not state.get("enable_real_trade", False):
        return {"status": "error", "message": "Real trading not enabled"}

    broker = _resolve_broker(payload.broker_id)
    method = broker.get("execution_mode", "mouse")

    if method != "direct":
        return {
            "status": "error",
            "message": "close_v2 saat ini hanya untuk mode direct. Gunakan endpoint close_by_index untuk mode mouse.",
            "broker": broker,
        }

    if broker.get("platform") != "mt5":
        return {
            "status": "error",
            "message": "close_v2 direct hanya didukung untuk broker MT5.",
            "broker": broker,
        }

    try:
        adapter, _ = get_broker_adapter(broker, method)
        result = adapter.close_trade(
            symbol=payload.symbol,
            lot=payload.lot,
            ticket=payload.ticket,
        )
        order = result.get("order", {})
        open_rows = list_open_trades(broker_id=broker["id"])
        match = next((t for t in reversed(open_rows) if int(t.get("ticket") or -1) == int(payload.ticket)), None)
        if not match and open_rows:
            match = open_rows[-1]
        if match:
            close_trade_record(
                match["trade_id"],
                exit_price=order.get("price"),
                profit=order.get("profit"),
                exit_time=int(time.time()),
                ticket=payload.ticket,
                reason="close_v2",
            )
        return {"status": "ok", "result": result, "broker": broker}
    except Exception as exc:
        log_mt5_error(str(exc), broker_id=broker.get("id"), broker_name=broker.get("name"))
        return {"status": "error", "message": str(exc), "broker": broker}


@router.post("/trade/close_latest_if_single")
def close_latest_if_single(broker_id: Optional[int] = Body(default=None)):
    open_count = get_open_trades_count()
    if open_count != 1:
        return {
            "status": "error",
            "message": "Close cepat hanya aktif jika trade aktif tepat satu.",
            "open_count": open_count,
        }
    items = list_open_trades(broker_id=broker_id)
    if not items:
        items = list_open_trades()
    if not items:
        return {"status": "error", "message": "No open trade found"}
    target = items[-1]
    broker = get_broker(target.get("broker_id")) if target.get("broker_id") else get_default_broker()
    if not broker:
        return {"status": "error", "message": "Broker not found"}
    adapter, method = get_broker_adapter(broker, target.get("execution_mode"))
    if method == "mouse":
        return {
            "status": "error",
            "message": "Quick close direct hanya untuk mode direct/API. Gunakan Trade History untuk multi/mouse close.",
        }
    try:
        ticket = int(target.get("ticket") or 0)
        if ticket <= 0:
            return {"status": "error", "message": "Open trade ticket not available"}
        result = adapter.close_trade(target.get("symbol") or "XAUUSD", float(target.get("lot") or 0.01), ticket)
        order = result.get("order", {})
        close_trade_record(
            target["trade_id"],
            exit_price=order.get("price"),
            profit=order.get("profit"),
            exit_time=int(time.time()),
            ticket=ticket,
            reason="quick_close",
        )
        return {"status": "ok", "result": result, "trade_id": target["trade_id"]}
    except Exception as exc:
        log_mt5_error(str(exc), broker_id=broker.get("id"), broker_name=broker.get("name"))
        return {"status": "error", "message": str(exc)}
