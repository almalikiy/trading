from __future__ import annotations

import threading
import time
from typing import Any

import trading_bot.app.ml_risk as ml_risk
from trading_bot.app.auto_trader.cycle import run_auto_trade_cycle
from trading_bot.app.auto_trader.diagnostics import diag_close_attempt, diag_event, diag_open_attempt, get_runtime_status
from trading_bot.risk.guards import (
    build_adaptive_target_snapshot as _build_adaptive_target_snapshot_impl,
    normalize_side as _normalize_side_impl,
    passes_direction_bias_guard as _passes_direction_bias_guard_impl,
    passes_same_direction_open_guard as _passes_same_direction_open_guard_impl,
    should_release_hedge as _should_release_hedge_impl,
)
from trading_bot.app.auto_trader.hedge import release_hedge as _release_hedge_impl
from trading_bot.app.auto_trader.hedge import trigger_hedge as _trigger_hedge_impl
from trading_bot.app.db import (
    apply_auto_trade_profile_to_state,
    close_trade_record,
    create_trade_open_record,
    get_account_state,
    get_broker,
    get_default_broker,
    get_recent_closed_trades,
    list_open_trades,
    log_auto_trade_event,
    log_mt5_error,
    resolve_feed_broker,
)
from trading_bot.app.logic import analyze_symbol
from trading_bot.app.terminal_adapters import (
    ensure_terminal_running,
    get_broker_account_metrics as _get_broker_account_metrics_impl,
    get_broker_adapter as _get_broker_adapter_impl,
    get_broker_symbol_constraints as _get_broker_symbol_constraints_impl,
    get_broker_symbol_tick as _get_broker_symbol_tick_impl,
    normalize_lot_with_constraints,
    probe_broker_order_status,
)


_loop_started = False
_TRADE_RUNTIME: dict[str, dict[str, Any]] = {}


def log_trade(trade: dict[str, Any], features: dict[str, Any] | None = None, result: dict[str, Any] | None = None) -> None:
    ml_risk.log_trade(trade=trade, features=features, result=result)


def get_broker_adapter(broker: dict[str, Any], mode: str | None = None):
    return _get_broker_adapter_impl(broker, order_method=mode)


def get_broker_account_metrics(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return _get_broker_account_metrics_impl(*args, **kwargs)


def get_broker_symbol_tick(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return _get_broker_symbol_tick_impl(*args, **kwargs)


def get_broker_symbol_constraints(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return _get_broker_symbol_constraints_impl(*args, **kwargs)


def _signal_strength(payload: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    del payload, state
    return {"buy": 0.5, "sell": 0.5, "direction": "hold", "score": 0.5, "per_timeframe": {}}


def _diag_open_attempt(status: str, **extra: Any) -> None:
    diag_open_attempt(status, log_mt5_error, **extra)


def _diag_close_attempt(status: str, **extra: Any) -> None:
    diag_close_attempt(status, **extra)


def get_auto_trader_runtime_status() -> dict[str, Any]:
    return get_runtime_status(_loop_started)


def _get_feed_broker(current_state: dict[str, Any]) -> dict[str, Any] | None:
    broker = resolve_feed_broker(state=current_state, require_terminal_path=True)
    if broker:
        return broker
    return resolve_feed_broker(state=current_state, require_terminal_path=False)


def _resolve_auto_open_broker(current_state: dict[str, Any], symbol: str):
    del symbol
    broker = _get_feed_broker(current_state) or get_default_broker() or {}
    return broker, {"can_open_order": bool(broker)}


def _normalize_side(value: Any) -> str:
    return _normalize_side_impl(value)


def _passes_direction_bias_guard(direction: str, broker_id: int | None = None, account_id: int | None = None):
    return _passes_direction_bias_guard_impl(
        direction,
        get_recent_closed_trades,
        broker_id=broker_id,
        account_id=account_id,
    )


def _passes_same_direction_open_guard(state: dict[str, Any], open_rows: list[dict[str, Any]], direction: str, max_open_trades: int):
    return _passes_same_direction_open_guard_impl(state, open_rows, direction, max_open_trades)


def build_adaptive_target_snapshot(trade_row: dict[str, Any], state: dict[str, Any], recent_closed_rows: list[dict[str, Any]] | None = None):
    del state
    return _build_adaptive_target_snapshot_impl(trade_row, recent_closed_rows=recent_closed_rows)


def trigger_hedge(trade: dict[str, Any], features: dict[str, Any] | None = None):
    return _trigger_hedge_impl(
        trade,
        features,
        get_broker_adapter=get_broker_adapter,
        create_trade_open_record=create_trade_open_record,
        log_auto_trade_event=log_auto_trade_event,
        log_trade=log_trade,
    )


def _should_release_hedge(state: dict[str, Any], metrics: dict[str, Any], hedge_rows: list[dict[str, Any]]) -> bool:
    return _should_release_hedge_impl(state, metrics, hedge_rows)


def release_hedge(trade_id: str):
    return _release_hedge_impl(
        trade_id,
        list_open_trades=list_open_trades,
        get_broker=get_broker,
        get_default_broker=get_default_broker,
        get_broker_adapter=get_broker_adapter,
        close_trade_record=close_trade_record,
        log_auto_trade_event=log_auto_trade_event,
        log_trade=log_trade,
    )


def _apply_partial_take_profit(*args: Any, **kwargs: Any) -> bool:
    del args, kwargs
    return False


def _apply_break_even_lock(*args: Any, **kwargs: Any) -> None:
    del args, kwargs
    return None


def _apply_trailing_policy(*args: Any, **kwargs: Any) -> None:
    del args, kwargs
    return None


def _run_auto_trade_cycle() -> None:
    run_auto_trade_cycle(
        get_account_state=get_account_state,
        get_feed_broker=_get_feed_broker,
        list_open_trades=list_open_trades,
        get_broker=get_broker,
        get_default_broker=get_default_broker,
        get_broker_adapter=get_broker_adapter,
        get_broker_symbol_tick=get_broker_symbol_tick,
        close_trade_record=close_trade_record,
        analyze_symbol=analyze_symbol,
        signal_strength=_signal_strength,
        diag_event=diag_event,
        diag_close_attempt=_diag_close_attempt,
    )


def _auto_trade_loop() -> None:
    while True:
        try:
            _run_auto_trade_cycle()
        except Exception as exc:
            diag_event("error", "cycle_exception", error=str(exc))
        try:
            state = get_account_state()
            interval = float(state.get("auto_trade_interval_sec", 2) or 2)
        except Exception:
            interval = 2
        interval = max(1.0, min(interval, 60.0))
        time.sleep(interval)


def start_auto_trader_thread() -> None:
    global _loop_started
    if _loop_started:
        return
    _loop_started = True
    thread = threading.Thread(target=_auto_trade_loop, daemon=True)
    thread.start()


def is_auto_trader_thread_started() -> bool:
    return bool(_loop_started)


__all__ = [
    "start_auto_trader_thread",
    "is_auto_trader_thread_started",
    "get_auto_trader_runtime_status",
    "_run_auto_trade_cycle",
    "_signal_strength",
    "_passes_direction_bias_guard",
    "_passes_same_direction_open_guard",
    "trigger_hedge",
    "release_hedge",
    "build_adaptive_target_snapshot",
    "_should_release_hedge",
    "get_broker_adapter",
    "get_broker_account_metrics",
    "get_broker_symbol_tick",
    "get_broker_symbol_constraints",
    "analyze_symbol",
    "log_trade",
    "ensure_terminal_running",
    "normalize_lot_with_constraints",
    "probe_broker_order_status",
    "create_trade_open_record",
    "close_trade_record",
    "get_account_state",
    "get_broker",
    "get_default_broker",
    "list_open_trades",
    "get_recent_closed_trades",
    "log_auto_trade_event",
    "apply_auto_trade_profile_to_state",
    "_TRADE_RUNTIME",
]
