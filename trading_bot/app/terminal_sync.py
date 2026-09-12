from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from typing import Any

from trading_bot.app import db
from trading_bot.app.terminal_lifecycle import ensure_terminal_running
from trading_bot.app.terminal_runtime import (
    _BACKGROUND_SYNC_LOCK,
    _BACKGROUND_SYNC_STATE,
    _MT5_LOCK,
    _check_mt5_non_strategy_confirmation,
    _build_mt5_call_notice,
    _group_deals_by_position,
    _log_mt5_error_throttled,
    _safe_mt5_shutdown,
    _sync_trade_id,
    _trade_type_from_deal,
    _trade_type_from_position,
    _weighted_price,
    mt5,
)


def _derive_tp_sl_values(position: Any):
    entry = float(getattr(position, "price_open", 0) or 0)
    if entry <= 0:
        return None, None
    tp_price = float(getattr(position, "tp", 0) or 0)
    sl_price = float(getattr(position, "sl", 0) or 0)
    tp_value = abs(tp_price - entry) if tp_price > 0 else None
    sl_value = abs(sl_price - entry) if sl_price > 0 else None
    return tp_value, sl_value


def _build_open_trade_from_position(broker: dict[str, Any], account_id: Any, position: Any, deals_for_position: list[Any] | None = None):
    tp_value, sl_value = _derive_tp_sl_values(position)
    ticket = int(getattr(position, "ticket", 0) or 0)
    entry_time = int(getattr(position, "time", 0) or 0) or int(time.time())
    entry_price = float(getattr(position, "price_open", 0) or 0)
    if (not entry_price) and deals_for_position:
        entry_deals = [deal for deal in deals_for_position if getattr(deal, "entry", None) == mt5.DEAL_ENTRY_IN]
        entry_price = _weighted_price(entry_deals) or entry_price
        if not entry_time and entry_deals:
            entry_time = int(getattr(entry_deals[0], "time", 0) or 0)
    return {
        "trade_id": _sync_trade_id(broker.get("id"), account_id, ticket),
        "status": "open",
        "type": _trade_type_from_position(getattr(position, "type", None)),
        "symbol": getattr(position, "symbol", None),
        "lot": float(getattr(position, "volume", 0) or 0),
        "ticket": ticket,
        "entry": entry_price,
        "profit": float(getattr(position, "profit", 0) or 0),
        "entryTime": entry_time,
        "exitTime": None,
        "reason": "terminal_sync_open",
        "tpValue": tp_value,
        "slValue": sl_value,
        "broker_id": broker.get("id"),
        "broker_name": broker.get("name"),
        "account_id": account_id,
        "platform": broker.get("platform"),
        "execution_mode": broker.get("execution_mode"),
        "terminal_path": broker.get("terminal_path"),
    }


def _build_closed_trade_from_deals(broker: dict[str, Any], account_id: Any, ticket: Any, deals_for_position: list[Any]):
    if mt5 is None:
        return None
    entry_deals = [deal for deal in deals_for_position if getattr(deal, "entry", None) == mt5.DEAL_ENTRY_IN]
    exit_values = {mt5.DEAL_ENTRY_OUT}
    deal_entry_out_by = getattr(mt5, "DEAL_ENTRY_OUT_BY", None)
    if deal_entry_out_by is not None:
        exit_values.add(deal_entry_out_by)
    exit_deals = [deal for deal in deals_for_position if getattr(deal, "entry", None) in exit_values]
    if not entry_deals or not exit_deals:
        return None
    first_entry = entry_deals[0]
    last_exit = exit_deals[-1]
    return {
        "trade_id": _sync_trade_id(broker.get("id"), account_id, ticket),
        "status": "closed",
        "type": _trade_type_from_deal(getattr(first_entry, "type", None)),
        "symbol": getattr(first_entry, "symbol", None),
        "lot": sum(float(getattr(deal, "volume", 0) or 0) for deal in entry_deals) or float(getattr(first_entry, "volume", 0) or 0),
        "ticket": int(ticket),
        "entry": _weighted_price(entry_deals),
        "exit": _weighted_price(exit_deals),
        "profit": sum(float(getattr(deal, "profit", 0) or 0) for deal in deals_for_position),
        "entryTime": int(getattr(first_entry, "time", 0) or 0) or None,
        "exitTime": int(getattr(last_exit, "time", 0) or 0) or None,
        "reason": "terminal_sync_closed",
        "tpValue": None,
        "slValue": None,
        "broker_id": broker.get("id"),
        "broker_name": broker.get("name"),
        "account_id": account_id,
        "platform": broker.get("platform"),
        "execution_mode": broker.get("execution_mode"),
        "terminal_path": broker.get("terminal_path"),
    }


def _fetch_history_deals_resilient(broker: dict[str, Any], from_date: datetime, to_date: datetime):
    broker_id = broker.get("id")
    broker_name = broker.get("name")
    primary_error = "history_deals_get_failed"
    try:
        deals_raw = mt5.history_deals_get(from_date, to_date) if mt5 is not None else []
        if deals_raw is not None:
            return list(deals_raw), True, "ok"
        err = mt5.last_error() if mt5 is not None else "mt5_unavailable"
        primary_error = f"history_deals_get failed [phase=primary, from={from_date.isoformat()}, to={to_date.isoformat()}, last_error={err}]"
        _log_mt5_error_throttled(primary_error, broker_id=broker_id, broker_name=broker_name, key=f"deals_primary_failed:{broker_id}:{err}", cooldown_sec=45)
    except Exception as exc:
        err = mt5.last_error() if mt5 is not None else "mt5_unavailable"
        primary_error = f"history_deals_get exception [phase=primary, from={from_date.isoformat()}, to={to_date.isoformat()}, exc={exc}, last_error={err}]"
        _log_mt5_error_throttled(primary_error, broker_id=broker_id, broker_name=broker_name, key=f"deals_primary_exception:{broker_id}:{err}", cooldown_sec=45)
    cursor = from_date
    merged: list[Any] = []
    fallback_errors: list[str] = []
    while cursor < to_date:
        chunk_end = min(cursor + timedelta(days=7), to_date)
        try:
            chunk_raw = mt5.history_deals_get(cursor, chunk_end) if mt5 is not None else []
            if chunk_raw is None:
                err = mt5.last_error() if mt5 is not None else "mt5_unavailable"
                fallback_errors.append(f"{cursor.isoformat()}..{chunk_end.isoformat()}: {err}")
            else:
                merged.extend(list(chunk_raw))
        except Exception as exc:
            fallback_errors.append(f"{cursor.isoformat()}..{chunk_end.isoformat()}: {exc}")
        cursor = chunk_end + timedelta(seconds=1)
    if merged:
        return merged, True, "chunked"
    if fallback_errors:
        _log_mt5_error_throttled(
            "history_deals_get fallback failed [phase=chunked, from=" + f"{from_date.isoformat()}, to={to_date.isoformat()}]: " + " | ".join(fallback_errors[:4]),
            broker_id=broker_id,
            broker_name=broker_name,
            key=f"deals_fallback_failed:{broker_id}:{fallback_errors[0]}",
            cooldown_sec=45,
        )
    return [], False, primary_error


def sync_broker_trade_state(broker: dict[str, Any] | None, history_days: int | None = 90):
    broker = broker or {}
    payload = {
        "broker_id": broker.get("id"),
        "broker_name": broker.get("name"),
        "synced": False,
        "reason": "unknown",
    }
    payload.update(_build_mt5_call_notice(call_name="sync_broker_trade_state", strategy_related=False))
    if _check_mt5_non_strategy_confirmation(call_name="sync_broker_trade_state", payload=payload, strategy_related=False):
        return payload
    if str(broker.get("platform", "mt5")).lower() != "mt5" or mt5 is None:
        return {"broker_id": broker.get("id"), "synced": False, "reason": "non_mt5_platform"}
    terminal_path = broker.get("terminal_path")
    if not terminal_path:
        return {"broker_id": broker.get("id"), "synced": False, "reason": "terminal_path_missing"}
    if _is_keep_terminal_alive_enabled():
        ensure_terminal_running(terminal_path, broker=broker)
    initialized = False
    saved_count = 0
    errors: list[dict[str, Any]] = []
    try:
        with _MT5_LOCK:
            initialized = bool(mt5.initialize(path=terminal_path))
            if not initialized:
                db.log_mt5_error(f"Failed to initialize MT5 for trade sync: {broker.get('name')}", broker_id=broker.get("id"), broker_name=broker.get("name"))
                return {"broker_id": broker.get("id"), "synced": False, "reason": "mt5_initialize_failed"}
            account = mt5.account_info()
            if account is None:
                return {"broker_id": broker.get("id"), "synced": False, "reason": "account_info_failed"}
            account_id = int(getattr(account, "login", 0) or 0) or None
            positions = list(mt5.positions_get() or [])
            from_date = datetime(1970, 1, 1) if history_days is None else datetime.now() - timedelta(days=max(1, int(history_days)))
            to_date = datetime.now() - timedelta(seconds=1)
            deals, deals_ok, deals_fetch_mode = _fetch_history_deals_resilient(broker, from_date, to_date)
            deals_by_position = _group_deals_by_position(deals)
            live_tickets: set[int] = set()
            for position in positions:
                ticket = int(getattr(position, "ticket", 0) or 0)
                if ticket <= 0:
                    continue
                live_tickets.add(ticket)
                trade = _build_open_trade_from_position(broker, account_id, position, deals_by_position.get(ticket, []))
                try:
                    db.upsert_trade_history_record(trade)
                    saved_count += 1
                except Exception as exc:
                    errors.append({"trade_id": trade.get("trade_id"), "error": str(exc)})
            for ticket, deals_for_position in deals_by_position.items():
                if ticket in live_tickets:
                    continue
                summary = _build_closed_trade_from_deals(broker, account_id, ticket, deals_for_position)
                if summary:
                    try:
                        db.upsert_trade_history_record(summary)
                        saved_count += 1
                    except Exception as exc:
                        errors.append({"trade_id": summary.get("trade_id"), "error": str(exc)})
            return {
                "broker_id": broker.get("id"),
                "broker_name": broker.get("name"),
                "account_id": account_id,
                "synced": deals_ok and not errors,
                "partial": (not deals_ok) or bool(errors),
                "reason": "ok" if deals_ok and not errors else ("history_deals_fetch_failed" if not deals_ok else "upsert_failed"),
                "open_positions": len(live_tickets),
                "history_deals": len(deals),
                "history_fetch_mode": deals_fetch_mode,
                "saved_count": saved_count,
                "errors": errors,
            }
    except Exception as exc:
        _log_mt5_error_throttled(f"Terminal sync failed for broker {broker.get('name')}: {exc}", broker_id=broker.get("id"), broker_name=broker.get("name"), key=f"terminal_sync_failed:{broker.get('id')}:{exc}", cooldown_sec=45)
        return {"broker_id": broker.get("id"), "synced": False, "reason": str(exc)}
    finally:
        if initialized:
            _safe_mt5_shutdown()


def sync_all_terminal_trade_state(history_days: int | None = 90):
    results = []
    for broker in db.list_brokers(include_inactive=False):
        if str(broker.get("platform", "mt5")).lower() != "mt5":
            continue
        results.append(sync_broker_trade_state(broker, history_days=history_days))
    return results


def sync_trade_state_for_history_flow(*, broker_id: int | None = None, state: dict[str, Any] | None = None) -> dict[str, Any]:
    current_state = state if isinstance(state, dict) else db.get_account_state()
    sync_all = bool(current_state.get("trade_history_sync_all", False))
    days_value = current_state.get("trade_history_sync_days", 90)
    try:
        history_days = None if sync_all else max(1, int(days_value or 90))
    except Exception:
        history_days = None if sync_all else 90

    if broker_id is not None:
        broker = db.get_broker(broker_id)
        if not broker or str(broker.get("platform", "mt5")).lower() != "mt5":
            results: list[dict[str, Any]] = []
        else:
            results = [sync_broker_trade_state(broker, history_days=history_days)]
    else:
        results = sync_all_terminal_trade_state(history_days=history_days)

    synced = sum(1 for item in results if item.get("synced"))
    partial = sum(1 for item in results if item.get("partial"))
    failed = sum(1 for item in results if not item.get("synced") and not item.get("partial"))
    if failed and not synced and not partial:
        status = "error"
    elif partial or failed:
        status = "partial"
    else:
        status = "ok"

    return {
        "status": status,
        "summary": {
            "brokers_total": len(results),
            "brokers_synced": synced,
            "brokers_partial": partial,
            "brokers_failed": failed,
            "history_days": history_days,
            "sync_all": sync_all,
        },
        "results": results,
    }


def get_background_mt5_sync_status() -> dict[str, Any]:
    with _BACKGROUND_SYNC_LOCK:
        payload = {
            "status": "ok",
            "sync_status": str(_BACKGROUND_SYNC_STATE.get("status", "idle")),
            "queued_at": _BACKGROUND_SYNC_STATE.get("queued_at"),
            "started_at": _BACKGROUND_SYNC_STATE.get("started_at"),
            "finished_at": _BACKGROUND_SYNC_STATE.get("finished_at"),
            "error": _BACKGROUND_SYNC_STATE.get("error"),
            "last_result": _BACKGROUND_SYNC_STATE.get("last_result"),
        }
        return payload


def sync_trade_state_for_history_flow_in_background(*, broker_id: int | None = None, state: dict[str, Any] | None = None, timeout_sec: float = 1.0) -> dict[str, Any]:
    now = time.time()
    with _BACKGROUND_SYNC_LOCK:
        _BACKGROUND_SYNC_STATE.update(
            {
                "status": "queued",
                "queued_at": now,
                "started_at": None,
                "finished_at": None,
                "error": None,
                "last_result": None,
            }
        )

    def _runner() -> None:
        try:
            with _BACKGROUND_SYNC_LOCK:
                _BACKGROUND_SYNC_STATE["status"] = "running"
                _BACKGROUND_SYNC_STATE["started_at"] = time.time()
                _BACKGROUND_SYNC_STATE["finished_at"] = None
                _BACKGROUND_SYNC_STATE["error"] = None
            payload = sync_trade_state_for_history_flow(broker_id=broker_id, state=state)
            with _BACKGROUND_SYNC_LOCK:
                _BACKGROUND_SYNC_STATE["status"] = "completed"
                _BACKGROUND_SYNC_STATE["finished_at"] = time.time()
                _BACKGROUND_SYNC_STATE["last_result"] = payload
        except Exception as exc:
            with _BACKGROUND_SYNC_LOCK:
                _BACKGROUND_SYNC_STATE["status"] = "failed"
                _BACKGROUND_SYNC_STATE["finished_at"] = time.time()
                _BACKGROUND_SYNC_STATE["error"] = str(exc)

    worker = threading.Thread(target=_runner, name=f"trade-sync-bg-{broker_id or 'all'}", daemon=True)
    worker.start()
    return {"status": "queued", "sync_status": "queued", "message": "MT5 trade sync started in background"}


__all__ = [
    "sync_broker_trade_state",
    "sync_all_terminal_trade_state",
    "sync_trade_state_for_history_flow",
    "get_background_mt5_sync_status",
    "sync_trade_state_for_history_flow_in_background",
]
