from __future__ import annotations

import csv
import json
import os
import time
from typing import Any

from fastapi import APIRouter, Body, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from trading_bot.app.auto_trader import get_auto_trader_runtime_status
from trading_bot.app import db
from trading_bot.app.persistence.account_store import get_account_state, save_account_state
from trading_bot.app.ml_risk import get_close_decision_dataset, get_dataset as get_ml_dataset, train_risk_mode_model

router = APIRouter(tags=["account"])


class AnalyticTPSLRequest(BaseModel):
    tp_value: float
    sl_value: float | None = None


class TradeHistorySyncSettingsRequest(BaseModel):
    sync_all: bool = False
    days: int | None = 90


class AutoTradeConfigRequest(BaseModel):
    symbol: str | None = None
    interval_sec: float | None = None
    auto_analytic_tpsl: bool | None = None
    tp_value: float | None = None
    sl_value: float | None = None
    lot: float | None = None
    max_open_trades: int | None = None
    risk_mode: str | None = None
    risk_percent: float | None = None
    use_account_balance: bool | None = None
    use_available_margin: bool | None = None
    min_free_margin_pct: float | None = None
    max_margin_usage_pct: float | None = None
    max_spread_points: int | None = None
    min_signal_score: float | None = None
    allow_sell: bool | None = None
    cooldown_sec: int | None = None
    session_start_hour: int | None = None
    session_end_hour: int | None = None
    use_atr_tpsl: bool | None = None
    atr_period: int | None = None
    atr_sl_mult: float | None = None
    atr_tp_mult: float | None = None
    trailing_enabled: bool | None = None
    trailing_activation_rr: float | None = None
    trailing_atr_mult: float | None = None
    confidence_model: str | None = None
    confidence_threshold: float | None = None
    timeframes: list[str] | None = None
    tf_weight_m1: float | None = None
    tf_weight_m5: float | None = None
    tf_weight_m15: float | None = None
    tf_weight_m30: float | None = None
    partial_tp_enabled: bool | None = None
    partial_tp_rr1: float | None = None
    partial_tp_close_pct1: float | None = None
    partial_tp_rr2: float | None = None
    partial_tp_close_pct2: float | None = None
    break_even_enabled: bool | None = None
    break_even_rr: float | None = None
    break_even_offset_atr_mult: float | None = None
    trailing_mode: str | None = None
    stateful_trail_buffer_atr_mult: float | None = None
    risk_selector_strategy: str | None = None
    risk_atr_threshold: float | None = None
    risk_balance_fixed_threshold: float | None = None
    risk_confidence_threshold: float | None = None
    risk_spread_fixed_threshold: int | None = None
    risk_spread_low_threshold: int | None = None
    risk_hybrid_addon_rr_threshold: float | None = None
    risk_hybrid_entry_mode: str | None = None
    risk_hybrid_addon_mode: str | None = None
    risk_adaptive_window_days: int | None = None
    risk_adaptive_min_trades: int | None = None
    protective_mode: str | None = None
    min_hold_sec: int | None = None
    reversal_confirm_cycles: int | None = None
    hedge_enabled: bool | None = None
    hedge_threshold: float | None = None
    hedge_slots: int | None = None


def _coerce_enabled(value: Any) -> bool:
    if isinstance(value, dict):
        value = value.get("enabled", False)
    return bool(value)


def _to_int(value: Any, default: int | None = None) -> int | None:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except Exception:
        return default


def _normalize_close_reason(reason: Any) -> str:
    text = str(reason or "").strip().lower()
    if "stop" in text or "sl" in text:
        return "sl"
    if "tp" in text or "take_profit" in text:
        return "tp"
    if "hedge" in text:
        return "hedge"
    if "force_close" in text:
        return "force_close"
    return "other"


def _build_close_decision_dataset(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dataset = []
    for row in rows:
        context = row.get("signal_context") if isinstance(row.get("signal_context"), dict) else {}
        dataset.append(
            {
                "features": {
                    "signal_score": row.get("signal_score"),
                    "spread_points": row.get("spread_points"),
                    "margin_usage_pct": row.get("margin_usage_pct"),
                    "atr_value": row.get("atr_value"),
                    "session_hour": row.get("session_hour"),
                    "risk_mode": row.get("risk_mode"),
                    "trailing_mode": row.get("trailing_mode"),
                    "target_factor": row.get("target_factor"),
                    "tp_sl_mode": row.get("tp_sl_mode"),
                    "context_score": context.get("score") if isinstance(context, dict) else None,
                },
                "result": {
                    "close_reason_family": _normalize_close_reason(row.get("reason")),
                    "profit": row.get("profit"),
                    "target_crossed_before_close": bool(row.get("target_first_crossed_at")),
                    "target_hit": bool(row.get("target_hit")),
                    "time_to_close_sec": row.get("time_to_close_sec"),
                    "time_to_target_cross_sec": row.get("time_to_target_cross_sec"),
                },
                "meta": {
                    "trade_id": row.get("trade_id"),
                    "symbol": row.get("symbol"),
                    "type": row.get("type"),
                    "broker_id": row.get("broker_id"),
                    "account_id": row.get("account_id"),
                    "entryTime": row.get("entryTime"),
                    "exitTime": row.get("exitTime"),
                },
            }
        )
    return dataset


def _active_profile_context(state: dict[str, Any]) -> tuple[dict[str, Any] | None, int | None, dict[str, Any]]:
    broker = db.resolve_feed_broker(state=state, require_terminal_path=False) or db.get_default_broker()
    account_id = None
    metrics = {}
    if broker:
        open_rows = db.list_open_trades(broker_id=broker.get("id"))
        for row in reversed(open_rows):
            candidate = row.get("account_id")
            if candidate is not None:
                try:
                    account_id = int(candidate)
                    break
                except Exception:
                    account_id = None
    return broker, account_id, metrics


def _apply_profile_for_active_account(base_state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None, int | None]:
    broker, account_id, _metrics = _active_profile_context(base_state)
    if broker and account_id is not None:
        scoped = db.apply_auto_trade_profile_to_state(base_state, broker.get("id"), account_id)
    else:
        scoped = dict(base_state)
    return scoped, broker, account_id


def _resolve_symbol_for_state(state: dict[str, Any], broker: dict[str, Any] | None = None) -> str:
    active_broker = broker or db.resolve_feed_broker(state=state, require_terminal_path=False) or db.get_default_broker()
    symbol = (active_broker or {}).get("default_symbol") or state.get("auto_trade_symbol") or "XAUUSD"
    return str(symbol).strip().upper() or "XAUUSD"


@router.get("/account/state")
async def get_account_state_route() -> dict[str, object]:
    base_state = get_account_state()
    state, broker, account_id = _apply_profile_for_active_account(base_state)
    state["auto_trade_symbol"] = _resolve_symbol_for_state(state, broker=broker)
    state["auto_trade_symbol_scope"] = "profile_or_broker_default"
    state["auto_trade_profile_broker_id"] = (broker or {}).get("id")
    state["auto_trade_profile_account_id"] = account_id
    state["auto_trade_profile_scope"] = "account" if (broker and account_id is not None and db.has_auto_trade_profile(broker.get("id"), account_id)) else "global"
    return state


@router.get("/account/auto_trade_health")
async def get_auto_trade_health_route() -> dict[str, object]:
    base_state = get_account_state()
    state, feed_broker, account_id = _apply_profile_for_active_account(base_state)
    enabled = bool(state.get("auto_trade_enabled", False))
    blockers = []
    if not enabled:
        blockers.append("auto_trade_disabled")
    if not bool(state.get("enable_real_trade", False)):
        blockers.append("real_trade_disabled")
    if not feed_broker:
        blockers.append("feed_broker_unavailable")

    hour_now = time.localtime().tm_hour
    start_hour = int(state.get("auto_trade_session_start_hour") or 0)
    end_hour = int(state.get("auto_trade_session_end_hour") or 24)
    if start_hour == end_hour:
        in_session = True
    elif start_hour < end_hour:
        in_session = start_hour <= hour_now < end_hour
    else:
        in_session = hour_now >= start_hour or hour_now < end_hour
    if not in_session:
        blockers.append("out_of_session_window")

    open_rows = db.list_open_trades()
    mouse_open = [r for r in open_rows if str(r.get("execution_mode") or "").lower() == "mouse"]
    if mouse_open:
        blockers.append("open_positions_in_mouse_mode")

    critical_blockers = {"real_trading_disabled", "feed_broker_unavailable"}
    has_critical_blocker = any(item in critical_blockers for item in blockers)

    return {
        "status": "ok",
        "active": bool(enabled and not has_critical_blocker),
        "auto_trade_enabled": enabled,
        "blockers": blockers,
        "checks": [
            {"key": "auto_trade_enabled", "ok": enabled, "value": enabled, "message": "Auto trade enabled"},
            {"key": "real_trade_enabled", "ok": bool(state.get("enable_real_trade", False)), "value": bool(state.get("enable_real_trade", False)), "message": "Real trading enabled"},
            {"key": "symbol", "ok": True, "value": state.get("auto_trade_symbol") or "XAUUSD", "message": "Active symbol"},
            {"key": "feed_broker", "ok": bool(feed_broker), "value": (feed_broker or {}).get("name") if isinstance(feed_broker, dict) else None, "message": "Feed broker resolved"},
            {"key": "session_window", "ok": in_session, "value": f"{start_hour}-{end_hour}", "message": "Configured trading session"},
            {"key": "open_positions_mouse_mode", "ok": len(mouse_open) == 0, "value": len(mouse_open), "message": "Open trades using mouse execution"},
        ],
        "symbol": _resolve_symbol_for_state(state, broker=feed_broker),
        "feed_broker": feed_broker,
        "profile": {
            "broker_id": (feed_broker or {}).get("id"),
            "account_id": account_id,
            "scope": "account" if (feed_broker and account_id is not None and db.has_auto_trade_profile(feed_broker.get("id"), account_id)) else "global",
        },
    }


@router.get("/account/auto_trade_runtime")
async def get_auto_trade_runtime_route() -> dict[str, object]:
    return {
        "status": "ok",
        "runtime": get_auto_trader_runtime_status(),
    }


@router.post("/account/set_analytic_tpsl")
async def set_analytic_tpsl(request: AnalyticTPSLRequest) -> dict[str, object]:
    state = get_account_state()
    state["tp_value"] = float(request.tp_value)
    state["sl_value"] = None if request.sl_value is None else float(request.sl_value)
    save_account_state(state)
    return {"status": "ok", "tp_value": state["tp_value"], "sl_value": state["sl_value"]}


@router.post("/account/set_auto_analytic_tpsl")
async def set_auto_analytic_tpsl(payload: Any = Body(...)) -> dict[str, object]:
    enabled = _coerce_enabled(payload)
    state = get_account_state()
    state["auto_analytic_tpsl"] = enabled
    save_account_state(state)
    return {"status": "ok", "auto_analytic_tpsl": enabled}


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


@router.get("/account/keep_mt5_alive_status")
async def get_keep_mt5_alive_status_route() -> dict[str, object]:
    from trading_bot.app.terminal_adapters import get_keep_mt5_alive_status

    return {"status": "ok", **get_keep_mt5_alive_status()}


@router.post("/account/set_keep_terminal_alive")
async def set_keep_terminal_alive_route(payload: Any = Body(...)) -> dict[str, object]:
    from trading_bot.app.terminal_adapters import set_keep_mt5_alive

    enabled = _coerce_enabled(payload)
    state = get_account_state()
    state["keep_terminal_alive"] = enabled
    save_account_state(state)
    status = set_keep_mt5_alive(enabled)
    return {"status": "ok", "keep_terminal_alive": bool(status.get("enabled", enabled)), "details": status}


@router.post("/account/confirm_mt5_operation")
async def confirm_mt5_operation_route(payload: Any = Body(...)) -> dict[str, object]:
    data = payload if isinstance(payload, dict) else {}
    call_name = str(data.get("call_name") or data.get("name") or "unknown").strip()
    allow = bool(data.get("confirm") or data.get("confirmed") or data.get("approved") or data.get("allow"))
    state = get_account_state()
    state[f"mt5_confirmed_{call_name}"] = allow
    state["mt5_non_strategy_require_confirmation"] = True
    save_account_state(state)
    return {
        "status": "ok",
        "call_name": call_name,
        "confirmed": allow,
        "requires_confirmation": True,
        "message": "User confirmation recorded for this MT5 operational check." if allow else "Confirmation was not granted for this MT5 operational check.",
    }


@router.post("/account/set_data_feed_broker")
async def set_data_feed_broker_route(broker_id: int = Body(...)) -> dict[str, object]:
    broker = db.get_broker(broker_id)
    if not broker:
        return {"status": "error", "message": "Broker not found"}
    state = get_account_state()
    state["data_feed_broker_id"] = int(broker_id)
    state["auto_trade_symbol"] = _resolve_symbol_for_state(state, broker=broker)
    save_account_state(state)
    return {
        "status": "ok",
        "data_feed_broker_id": state["data_feed_broker_id"],
        "auto_trade_symbol": state["auto_trade_symbol"],
        "auto_trade_symbol_scope": "broker_default",
    }


@router.post("/account/set_trade_history_sync")
async def set_trade_history_sync_route(payload: TradeHistorySyncSettingsRequest) -> dict[str, object]:
    state = get_account_state()
    sync_all = bool(payload.sync_all)
    days = None if sync_all else int(payload.days or 90)
    if not sync_all and days <= 0:
        return {"status": "error", "message": "History sync days harus lebih besar dari 0."}
    state["trade_history_sync_all"] = sync_all
    state["trade_history_sync_days"] = 90 if days is None else days
    save_account_state(state)
    return {
        "status": "ok",
        "trade_history_sync_all": bool(state.get("trade_history_sync_all")),
        "trade_history_sync_days": int(state.get("trade_history_sync_days") or 90),
    }


@router.post("/account/set_auto_trade_config")
async def set_auto_trade_config_route(payload: AutoTradeConfigRequest) -> dict[str, object]:
    base_state = get_account_state()
    state, broker_ctx, account_id_ctx = _apply_profile_for_active_account(base_state)

    if payload.interval_sec is not None:
        interval = float(payload.interval_sec)
        if interval < 1 or interval > 60:
            return {"status": "error", "message": "Interval auto-trade harus antara 1 sampai 60 detik."}
        state["auto_trade_interval_sec"] = interval

    mapping = {
        "auto_analytic_tpsl": payload.auto_analytic_tpsl,
        "tp_value": payload.tp_value,
        "sl_value": payload.sl_value,
        "lot": payload.lot,
        "max_open_trades": payload.max_open_trades,
        "auto_trade_risk_mode": payload.risk_mode,
        "auto_trade_risk_percent": payload.risk_percent,
        "auto_trade_use_account_balance": payload.use_account_balance,
        "auto_trade_use_available_margin": payload.use_available_margin,
        "auto_trade_min_free_margin_pct": payload.min_free_margin_pct,
        "auto_trade_max_margin_usage_pct": payload.max_margin_usage_pct,
        "auto_trade_max_spread_points": payload.max_spread_points,
        "auto_trade_min_signal_score": payload.min_signal_score,
        "auto_trade_allow_sell": payload.allow_sell,
        "auto_trade_cooldown_sec": payload.cooldown_sec,
        "auto_trade_session_start_hour": payload.session_start_hour,
        "auto_trade_session_end_hour": payload.session_end_hour,
        "auto_trade_use_atr_tpsl": payload.use_atr_tpsl,
        "auto_trade_atr_period": payload.atr_period,
        "auto_trade_atr_sl_mult": payload.atr_sl_mult,
        "auto_trade_atr_tp_mult": payload.atr_tp_mult,
        "auto_trade_trailing_enabled": payload.trailing_enabled,
        "auto_trade_trailing_activation_rr": payload.trailing_activation_rr,
        "auto_trade_trailing_atr_mult": payload.trailing_atr_mult,
        "auto_trade_confidence_model": payload.confidence_model,
        "auto_trade_confidence_threshold": payload.confidence_threshold,
        "auto_trade_tf_weight_m1": payload.tf_weight_m1,
        "auto_trade_tf_weight_m5": payload.tf_weight_m5,
        "auto_trade_tf_weight_m15": payload.tf_weight_m15,
        "auto_trade_tf_weight_m30": payload.tf_weight_m30,
        "auto_trade_partial_tp_enabled": payload.partial_tp_enabled,
        "auto_trade_partial_tp_rr1": payload.partial_tp_rr1,
        "auto_trade_partial_tp_close_pct1": payload.partial_tp_close_pct1,
        "auto_trade_partial_tp_rr2": payload.partial_tp_rr2,
        "auto_trade_partial_tp_close_pct2": payload.partial_tp_close_pct2,
        "auto_trade_break_even_enabled": payload.break_even_enabled,
        "auto_trade_break_even_rr": payload.break_even_rr,
        "auto_trade_break_even_offset_atr_mult": payload.break_even_offset_atr_mult,
        "auto_trade_trailing_mode": payload.trailing_mode,
        "auto_trade_stateful_trail_buffer_atr_mult": payload.stateful_trail_buffer_atr_mult,
        "auto_trade_risk_selector_strategy": payload.risk_selector_strategy,
        "auto_trade_risk_atr_threshold": payload.risk_atr_threshold,
        "auto_trade_risk_balance_fixed_threshold": payload.risk_balance_fixed_threshold,
        "auto_trade_risk_confidence_threshold": payload.risk_confidence_threshold,
        "auto_trade_risk_spread_fixed_threshold": payload.risk_spread_fixed_threshold,
        "auto_trade_risk_spread_low_threshold": payload.risk_spread_low_threshold,
        "auto_trade_risk_hybrid_addon_rr_threshold": payload.risk_hybrid_addon_rr_threshold,
        "auto_trade_risk_hybrid_entry_mode": payload.risk_hybrid_entry_mode,
        "auto_trade_risk_hybrid_addon_mode": payload.risk_hybrid_addon_mode,
        "auto_trade_risk_adaptive_window_days": payload.risk_adaptive_window_days,
        "auto_trade_risk_adaptive_min_trades": payload.risk_adaptive_min_trades,
        "auto_trade_protective_mode": payload.protective_mode,
        "auto_trade_min_hold_sec": payload.min_hold_sec,
        "auto_trade_reversal_confirm_cycles": payload.reversal_confirm_cycles,
        "hedge_enabled": payload.hedge_enabled,
        "hedge_threshold": payload.hedge_threshold,
        "hedge_slots": payload.hedge_slots,
    }
    for key, value in mapping.items():
        if value is not None:
            state[key] = value

    if payload.timeframes is not None:
        cleaned = [str(v).strip().upper() for v in payload.timeframes if str(v).strip()]
        if cleaned:
            state["auto_trade_timeframes"] = ",".join(cleaned)

    state["auto_trade_symbol"] = _resolve_symbol_for_state(state, broker=broker_ctx)
    save_account_state(state)
    if broker_ctx and account_id_ctx is not None:
        db.save_auto_trade_profile(broker_ctx.get("id"), account_id_ctx, state)

    return {
        "status": "ok",
        "auto_trade_symbol": state.get("auto_trade_symbol"),
        "auto_trade_symbol_scope": "broker_default",
        "risk_mode": state.get("auto_trade_risk_mode", "fixed_lot"),
        "risk_percent": state.get("auto_trade_risk_percent", 1.0),
        "timeframes": str(state.get("auto_trade_timeframes") or "M1,M5,M15,M30").split(","),
        "profile": {
            "broker_id": (broker_ctx or {}).get("id"),
            "account_id": account_id_ctx,
            "scope": "account" if (broker_ctx and account_id_ctx is not None) else "global",
        },
    }


@router.get("/account/auto_trade_constraints")
async def get_auto_trade_constraints_route() -> dict[str, object]:
    state = get_account_state()
    broker = db.resolve_feed_broker(state=state, require_terminal_path=False) or db.get_default_broker()
    symbol = _resolve_symbol_for_state(state, broker=broker)
    return {
        "status": "ok",
        "broker": broker,
        "symbol": symbol,
        "constraints": {
            "max_open_trades": int(state.get("max_open_trades") or 1),
            "lot": float(state.get("lot") or 0.01),
            "symbol": symbol,
            "risk_percent": float(state.get("auto_trade_risk_percent") or 1.0),
        },
    }


@router.get("/account/auto_trade_stats")
async def get_auto_trade_stats_route(window_days: int = 30, broker_id: int | None = None, account_id: int | None = None) -> dict[str, object]:
    stats = db.get_auto_trade_statistics(window_days=window_days, broker_id=broker_id, account_id=account_id)
    return {"status": "ok", "stats": stats}


@router.get("/account/auto_trade_events")
async def get_auto_trade_events_route(
    limit: int = 200,
    broker_id: int | None = None,
    account_id: int | None = None,
    event_type: str | None = None,
    since: int | None = None,
) -> dict[str, object]:
    events = db.get_auto_trade_events(
        limit=max(1, min(int(limit), 2000)),
        broker_id=broker_id,
        account_id=account_id,
        event_type=event_type,
        since=since,
    )
    return {
        "status": "ok",
        "rows": len(events),
        "events": events,
    }


@router.get("/account/auto_trade_close_decision_dataset")
async def get_auto_trade_close_decision_dataset_route(
    limit: int = 500,
    broker_id: int | None = None,
    account_id: int | None = None,
) -> dict[str, object]:
    rows = db.get_recent_closed_trades(
        limit=max(1, min(int(limit), 5000)),
        broker_id=broker_id,
        account_id=account_id,
    )
    dataset = _build_close_decision_dataset(rows)
    return {
        "status": "ok",
        "rows": len(dataset),
        "dataset": dataset,
    }


@router.get("/account/auto_trade_ml_dataset")
async def get_auto_trade_ml_dataset_route(
    limit: int = 500,
    broker_id: int | None = None,
    account_id: int | None = None,
    since_days: int = 90,
) -> dict[str, object]:
    since = int(time.time()) - (max(1, min(int(since_days), 3650)) * 86400)
    trades = db.get_recent_closed_trades(
        limit=max(1, min(int(limit), 5000)),
        broker_id=broker_id,
        account_id=account_id,
    )
    events = db.get_auto_trade_events(
        limit=max(1, min(int(limit), 5000)),
        broker_id=broker_id,
        account_id=account_id,
        since=since,
    )

    event_by_trade: dict[str, dict[str, Any]] = {}
    for event in events:
        trade_id = str(event.get("trade_id") or "").strip()
        if not trade_id:
            continue
        if trade_id not in event_by_trade:
            event_by_trade[trade_id] = event

    dataset = []
    for row in trades:
        trade_id = str(row.get("trade_id") or "").strip()
        ev = event_by_trade.get(trade_id, {})
        dataset.append(
            {
                "trade_id": trade_id,
                "broker_id": row.get("broker_id"),
                "account_id": row.get("account_id"),
                "symbol": row.get("symbol"),
                "features": {
                    "signal_score": row.get("signal_score", ev.get("signal_score")),
                    "spread_points": row.get("spread_points", ev.get("spread_points")),
                    "margin_usage_pct": row.get("margin_usage_pct", ev.get("margin_usage_pct")),
                    "atr_value": row.get("atr_value", ev.get("atr_value")),
                    "session_hour": row.get("session_hour", ev.get("session_hour")),
                },
                "label": {
                    "risk_mode": row.get("risk_mode", ev.get("risk_mode")),
                    "profit": row.get("profit"),
                    "win": float(row.get("profit") or 0.0) > 0.0,
                },
            }
        )

    return {
        "status": "ok",
        "rows": len(dataset),
        "dataset": dataset,
    }


@router.get("/account/auto_trade_profile_history")
async def get_auto_trade_profile_history_route(limit: int = 100, broker_id: int | None = None, account_id: int | None = None) -> dict[str, object]:
    rows = db.get_auto_trade_profile_history(broker_id=broker_id, account_id=account_id, limit=max(1, min(int(limit or 100), 2000)))
    return {"status": "ok", "history": rows}


@router.post("/account/auto_trade_ml_train")
async def train_auto_trade_ml_route(limit: int = 5000) -> dict[str, object]:
    dataset = get_ml_dataset(limit=max(1, min(int(limit or 5000), 100000)))
    result = train_risk_mode_model(dataset)
    return {"status": "ok", "dataset_rows": len(dataset), "result": result}


def _exports_dir() -> str:
    folder = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "exports")
    os.makedirs(folder, exist_ok=True)
    return folder


@router.post("/account/auto_trade_ml_export")
async def export_auto_trade_ml_dataset_route(format: str = Body("json"), limit: int = Body(10000)) -> dict[str, object]:
    safe_format = str(format or "json").strip().lower()
    rows = get_ml_dataset(limit=max(1, min(int(limit or 10000), 200000)))
    ts = int(time.time())
    export_dir = _exports_dir()

    if safe_format == "csv":
        path = os.path.join(export_dir, f"auto_trade_dataset_{ts}.csv")
        with open(path, "w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["timestamp", "risk_mode", "profit", "features_json"])
            for row in rows:
                writer.writerow([
                    row.get("timestamp"),
                    row.get("risk_mode"),
                    (row.get("result") or {}).get("profit"),
                    json.dumps(row.get("features") or {}, ensure_ascii=True),
                ])
    elif safe_format == "json":
        path = os.path.join(export_dir, f"auto_trade_dataset_{ts}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, ensure_ascii=True, indent=2)
    else:
        return {"status": "error", "message": "Format export harus csv atau json."}

    filename = os.path.basename(path)
    return {
        "status": "ok",
        "export": {
            "path": path,
            "filename": filename,
            "rows": len(rows),
            "download_url": f"/account/auto_trade_ml_export_download?file={filename}",
        },
    }


@router.get("/account/auto_trade_ml_export_download")
async def download_auto_trade_ml_export_route(file: str = Query(..., min_length=1)):
    exports_dir = os.path.abspath(_exports_dir())
    safe_name = os.path.basename(str(file or "").strip())
    if not safe_name:
        return {"status": "error", "message": "Nama file export tidak valid."}
    full_path = os.path.abspath(os.path.join(exports_dir, safe_name))
    if not full_path.startswith(exports_dir + os.sep):
        return {"status": "error", "message": "Path file tidak valid."}
    if not os.path.exists(full_path):
        return {"status": "error", "message": "File export tidak ditemukan."}
    media_type = "text/csv" if safe_name.lower().endswith(".csv") else "application/json"
    return FileResponse(path=full_path, media_type=media_type, filename=safe_name)


@router.post("/account/set_initial_balance")
async def set_initial_balance_route(amount: float = Body(...)) -> dict[str, object]:
    state = get_account_state()
    state["initial_balance"] = float(amount)
    state["balance"] = float(amount)
    save_account_state(state)
    return {"status": "ok", "balance": state["balance"]}


@router.post("/account/deposit")
async def deposit_route(amount: float = Body(...)) -> dict[str, object]:
    state = get_account_state()
    state["balance"] = float(state.get("balance") or 0.0) + float(amount)
    db.add_account_transaction("deposit", float(amount), "api:deposit")
    save_account_state(state)
    return {"status": "ok", "balance": state["balance"]}


@router.post("/account/withdraw")
async def withdraw_route(amount: float = Body(...)) -> dict[str, object]:
    state = get_account_state()
    balance = float(state.get("balance") or 0.0)
    if float(amount) > balance:
        return {"status": "error", "message": "Insufficient balance"}
    state["balance"] = balance - float(amount)
    db.add_account_transaction("withdraw", float(amount), "api:withdraw")
    save_account_state(state)
    return {"status": "ok", "balance": state["balance"]}


@router.post("/account/adjustment")
async def adjustment_route(amount: float = Body(...), note: str = Body("")) -> dict[str, object]:
    state = get_account_state()
    state["balance"] = float(state.get("balance") or 0.0) + float(amount)
    db.add_account_transaction("adjustment", float(amount), str(note or ""))
    save_account_state(state)
    return {"status": "ok", "balance": state["balance"]}


@router.post("/account/set_lot")
async def set_lot_route(lot: float = Body(...)) -> dict[str, object]:
    state = get_account_state()
    state["lot"] = float(lot)
    save_account_state(state)
    return {"status": "ok", "lot": state["lot"]}


@router.post("/account/set_max_open_trades")
async def set_max_open_trades_route(count: int = Body(...)) -> dict[str, object]:
    state = get_account_state()
    state["max_open_trades"] = int(count)
    save_account_state(state)
    return {"status": "ok", "max_open_trades": state["max_open_trades"]}
