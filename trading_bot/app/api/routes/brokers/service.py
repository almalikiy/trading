from __future__ import annotations

import os
import time
import uuid
from typing import Any

from fastapi import HTTPException

from trading_bot.app import db
from trading_bot.app.logic import close_real_trade, open_real_trade
from trading_bot.app.terminal_adapters import get_broker_order_status_snapshot


def get_default_broker() -> dict[str, object] | None:
    return db.get_default_broker()


def resolve_broker(broker_id: int | None) -> dict[str, object]:
    broker = db.get_broker(broker_id) if broker_id else get_default_broker()
    if not broker:
        raise HTTPException(status_code=404, detail="Broker not configured")
    if not bool(broker.get("is_active", True)):
        raise HTTPException(status_code=400, detail="Broker is inactive")
    return broker


def effective_method_for_broker(broker: dict[str, object], requested: str | None = None) -> str:
    method = str(requested or broker.get("execution_mode") or "mouse").lower()
    if str(broker.get("platform") or "").lower() == "mt4" and method == "direct":
        return "mouse"
    return "direct" if method == "direct" else "mouse"


def broker_order_status_snapshot(broker: dict[str, object], symbol: str = "XAUUSD") -> dict[str, object]:
    payload = get_broker_order_status_snapshot(broker, symbol=symbol)
    payload["execution_mode"] = effective_method_for_broker(broker)
    payload["terminal_path_exists"] = bool(broker.get("terminal_path") and os.path.exists(str(broker.get("terminal_path"))))
    return payload


def open_trade_v2(payload: Any) -> dict[str, object]:
    state = db.get_account_state()
    if not bool(state.get("enable_real_trade", False)):
        return {"status": "error", "message": "Real trading not enabled"}

    if payload.signal_time is not None and (time.time() - float(payload.signal_time)) > 60:
        return {"status": "skipped", "message": "Signal expired, trade skipped"}

    broker = resolve_broker(payload.broker_id)
    method = effective_method_for_broker(broker, requested=payload.order_method)

    if method != "direct":
        return {
            "status": "error",
            "message": "open_v2 direct tidak tersedia untuk mode mouse saat ini.",
            "broker": broker,
            "execution_mode": method,
        }

    if str(broker.get("platform") or "").lower() != "mt5":
        return {
            "status": "error",
            "message": "open_v2 direct hanya didukung untuk broker MT5.",
            "broker": broker,
            "execution_mode": method,
        }

    try:
        result = open_real_trade(
            symbol=payload.symbol,
            lot=float(payload.lot),
            trade_type=payload.trade_type,
            terminal_path=broker.get("terminal_path"),
        )
        order = result.get("order", {}) if isinstance(result, dict) else {}
        entry_price = order.get("price")
        ticket = order.get("order") or order.get("ticket")

        now = int(time.time())
        tp_value = state.get("tp_value", 0.5)
        sl_value = state.get("sl_value", None)
        if state.get("auto_analytic_tpsl", False):
            tp_value = round(2 * float(payload.lot), 2)
            sl_value = round(1 * float(payload.lot), 2)
            state["tp_value"] = tp_value
            state["sl_value"] = sl_value
            db.save_account_state(state)

        trade_id = str(uuid.uuid4())
        db.create_trade_open_record(
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
                "account_id": order.get("account_id"),
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
        db.log_mt5_error(str(exc), broker_id=broker.get("id"), broker_name=broker.get("name"))
        return {"status": "error", "message": str(exc), "broker": broker}


def close_trade_v2(payload: Any) -> dict[str, object]:
    state = db.get_account_state()
    if not bool(state.get("enable_real_trade", False)):
        return {"status": "error", "message": "Real trading not enabled"}

    broker = resolve_broker(payload.broker_id)
    method = effective_method_for_broker(broker)

    if method != "direct":
        return {
            "status": "error",
            "message": "close_v2 saat ini hanya untuk mode direct. Gunakan endpoint close_by_index untuk mode mouse.",
            "broker": broker,
        }

    if str(broker.get("platform") or "").lower() != "mt5":
        return {
            "status": "error",
            "message": "close_v2 direct hanya didukung untuk broker MT5.",
            "broker": broker,
        }

    try:
        result = close_real_trade(
            symbol=payload.symbol,
            lot=float(payload.lot),
            ticket=int(payload.ticket),
            terminal_path=broker.get("terminal_path"),
        )
        order = result.get("order", {}) if isinstance(result, dict) else {}
        open_rows = db.list_open_trades(broker_id=broker["id"])
        match = next((t for t in reversed(open_rows) if int(t.get("ticket") or -1) == int(payload.ticket)), None)
        if not match and open_rows:
            match = open_rows[-1]
        if match:
            db.close_trade_record(
                match["trade_id"],
                exit_price=order.get("price"),
                profit=order.get("profit"),
                exit_time=int(time.time()),
                ticket=payload.ticket,
                reason="close_v2",
            )
        return {"status": "ok", "result": result, "broker": broker}
    except Exception as exc:
        db.log_mt5_error(str(exc), broker_id=broker.get("id"), broker_name=broker.get("name"))
        return {"status": "error", "message": str(exc), "broker": broker}


def close_latest_if_single(broker_id: int | None) -> dict[str, object]:
    open_count = db.get_open_trades_count()
    if open_count != 1:
        return {
            "status": "error",
            "message": "Close cepat hanya aktif jika trade aktif tepat satu.",
            "open_count": open_count,
        }

    items = db.list_open_trades(broker_id=broker_id)
    if not items:
        items = db.list_open_trades()
    if not items:
        return {"status": "error", "message": "No open trade found"}

    target = items[-1]
    broker = db.get_broker(target.get("broker_id")) if target.get("broker_id") else get_default_broker()
    if not broker:
        return {"status": "error", "message": "Broker not found"}

    method = effective_method_for_broker(broker, requested=target.get("execution_mode"))
    if method == "mouse":
        return {
            "status": "error",
            "message": "Quick close direct hanya untuk mode direct/API. Gunakan Trade History untuk multi/mouse close.",
        }

    try:
        ticket = int(target.get("ticket") or 0)
        if ticket <= 0:
            return {"status": "error", "message": "Open trade ticket not available"}
        result = close_real_trade(
            symbol=target.get("symbol") or "XAUUSD",
            lot=float(target.get("lot") or 0.01),
            ticket=ticket,
            terminal_path=broker.get("terminal_path"),
        )
        order = result.get("order", {}) if isinstance(result, dict) else {}
        db.close_trade_record(
            target["trade_id"],
            exit_price=order.get("price"),
            profit=order.get("profit"),
            exit_time=int(time.time()),
            ticket=ticket,
            reason="quick_close",
        )
        return {"status": "ok", "result": result, "trade_id": target["trade_id"]}
    except Exception as exc:
        db.log_mt5_error(str(exc), broker_id=broker.get("id"), broker_name=broker.get("name"))
        return {"status": "error", "message": str(exc)}
