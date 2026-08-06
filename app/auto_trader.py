import threading
import time
import uuid
from collections import deque
from datetime import datetime

from .db import (
    apply_auto_trade_profile_to_state,
    apply_partial_close_record,
    close_trade_record,
    create_trade_open_record,
    get_account_state,
    get_broker,
    get_default_broker,
    get_trade_history,
    get_recent_closed_trades,
    list_brokers,
    list_open_trades,
    log_mt5_error,
    log_auto_trade_event,
    resolve_feed_broker,
    save_account_state,
    update_open_trade_tpsl,
    get_risk_mode_performance,
)
from .logic import analyze_symbol, fetch_ohlcv, normalize_timeframes
from .ml_risk import log_trade, predict_risk_mode
from .terminal_adapters import (
    ensure_terminal_running,
    get_broker_adapter,
    get_broker_account_metrics,
    get_broker_symbol_tick,
    get_broker_symbol_constraints,
    normalize_lot_with_constraints,
    probe_broker_order_status,
)


_loop_started = False
_TRADE_RUNTIME = {}
_DIAG_LOCK = threading.Lock()
_OPEN_FAIL_LOG_LOCK = threading.Lock()
_OPEN_FAIL_LOG_TS = {}
_AUTO_TRADE_DIAG = {
    "started_at": int(time.time()),
    "last_cycle_at": None,
    "last_decision": "init",
    "last_reason": "not_started",
    "last_signal": "wait",
    "last_signal_score": 0.0,
    "last_symbol": None,
    "last_open_attempt_at": None,
    "last_open_attempt": None,
    "last_open_success_at": None,
    "last_open_error": None,
    "last_close_attempt_at": None,
    "last_close_attempt": None,
    "skip_counts": {},
    "recent_events": deque(maxlen=40),
}


def _log_open_failure_throttled(reason, **extra):
    symbol = str(extra.get("symbol") or "-")
    broker = str(extra.get("broker_name") or "-")
    key = f"{reason}:{symbol}:{broker}"
    now = time.time()
    with _OPEN_FAIL_LOG_LOCK:
        last_ts = _OPEN_FAIL_LOG_TS.get(key, 0.0)
        if now - last_ts < 30.0:
            return
        _OPEN_FAIL_LOG_TS[key] = now

    details = []
    for field in ("signal", "spread_points", "max_spread_points", "lot", "method", "broker_reason", "error"):
        if extra.get(field) is not None:
            details.append(f"{field}={extra.get(field)}")
    msg = f"auto_open blocked [{reason}] symbol={symbol} broker={broker}"
    if details:
        msg += " " + " ".join(details)
    log_mt5_error(msg, broker_name=(None if broker == "-" else broker))


def _diag_event(decision, reason, **extra):
    now = int(time.time())
    with _DIAG_LOCK:
        _AUTO_TRADE_DIAG["last_cycle_at"] = now
        _AUTO_TRADE_DIAG["last_decision"] = decision
        _AUTO_TRADE_DIAG["last_reason"] = reason
        if "symbol" in extra and extra.get("symbol"):
            _AUTO_TRADE_DIAG["last_symbol"] = str(extra.get("symbol"))
        if "signal" in extra and extra.get("signal") is not None:
            _AUTO_TRADE_DIAG["last_signal"] = str(extra.get("signal"))
        if "signal_score" in extra and extra.get("signal_score") is not None:
            _AUTO_TRADE_DIAG["last_signal_score"] = float(extra.get("signal_score"))
        if decision == "skip":
            counts = _AUTO_TRADE_DIAG["skip_counts"]
            counts[reason] = int(counts.get(reason, 0)) + 1
        _AUTO_TRADE_DIAG["recent_events"].append(
            {
                "ts": now,
                "decision": decision,
                "reason": reason,
                "extra": extra,
            }
        )


def _diag_open_attempt(status, **extra):
    now = int(time.time())
    with _DIAG_LOCK:
        _AUTO_TRADE_DIAG["last_open_attempt_at"] = now
        _AUTO_TRADE_DIAG["last_open_attempt"] = {
            "status": status,
            **extra,
        }
        if status == "ok":
            _AUTO_TRADE_DIAG["last_open_success_at"] = now
            _AUTO_TRADE_DIAG["last_open_error"] = None
        elif status == "error":
            _AUTO_TRADE_DIAG["last_open_error"] = str(extra.get("error") or "unknown")
            details = dict(extra)
            reason = str(details.pop("reason", "unknown"))
            _log_open_failure_throttled(reason, **details)


def _diag_close_attempt(status, **extra):
    now = int(time.time())
    with _DIAG_LOCK:
        _AUTO_TRADE_DIAG["last_close_attempt_at"] = now
        _AUTO_TRADE_DIAG["last_close_attempt"] = {
            "status": status,
            **extra,
        }


def get_auto_trader_runtime_status():
    with _DIAG_LOCK:
        return {
            "loop_started": bool(_loop_started),
            "started_at": _AUTO_TRADE_DIAG.get("started_at"),
            "last_cycle_at": _AUTO_TRADE_DIAG.get("last_cycle_at"),
            "last_decision": _AUTO_TRADE_DIAG.get("last_decision"),
            "last_reason": _AUTO_TRADE_DIAG.get("last_reason"),
            "last_signal": _AUTO_TRADE_DIAG.get("last_signal"),
            "last_signal_score": _AUTO_TRADE_DIAG.get("last_signal_score"),
            "last_symbol": _AUTO_TRADE_DIAG.get("last_symbol"),
            "last_open_attempt_at": _AUTO_TRADE_DIAG.get("last_open_attempt_at"),
            "last_open_attempt": _AUTO_TRADE_DIAG.get("last_open_attempt"),
            "last_open_success_at": _AUTO_TRADE_DIAG.get("last_open_success_at"),
            "last_open_error": _AUTO_TRADE_DIAG.get("last_open_error"),
            "last_close_attempt_at": _AUTO_TRADE_DIAG.get("last_close_attempt_at"),
            "last_close_attempt": _AUTO_TRADE_DIAG.get("last_close_attempt"),
            "skip_counts": dict(_AUTO_TRADE_DIAG.get("skip_counts") or {}),
            "recent_events": list(_AUTO_TRADE_DIAG.get("recent_events") or []),
        }


def _get_feed_broker(state):
    broker = resolve_feed_broker(state=state, require_terminal_path=True)
    if broker:
        return broker
    return resolve_feed_broker(state=state, require_terminal_path=False)


def _latest_bar(symbol, terminal_path):
    try:
        df = fetch_ohlcv(symbol, "M1", bars=2, terminal_path=terminal_path)
        last = df.iloc[-1]
        return {
            "close": float(last["close"]),
            "high": float(last["high"]),
            "low": float(last["low"]),
        }
    except Exception:
        return None


def _resolve_auto_open_broker(state, symbol):
    """
    Prefer default broker if order-ready; otherwise fallback to first active broker that is ready.
    """
    default_broker = get_default_broker()
    candidates = []
    if default_broker and default_broker.get("is_active", True):
        candidates.append(default_broker)

    seen_ids = {b.get("id") for b in candidates if b}
    for row in list_open_trades():
        broker_id = row.get("broker_id")
        if broker_id and broker_id not in seen_ids:
            broker = get_broker(broker_id)
            if broker and broker.get("is_active", True):
                candidates.append(broker)
                seen_ids.add(broker_id)

    for broker in list_brokers(include_inactive=False):
        if broker.get("id") not in seen_ids:
            candidates.append(broker)
            seen_ids.add(broker.get("id"))

    for broker in candidates:
        status = probe_broker_order_status(broker, symbol=symbol, auto_start=False)
        if status.get("can_open_order"):
            return broker, status

    if default_broker:
        return default_broker, probe_broker_order_status(default_broker, symbol=symbol, auto_start=False)
    return None, {"can_open_order": False, "reason": "no_broker_available"}


def _coerce_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return float(default)


def _coerce_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return int(default)


def _cleanup_runtime_for_open_trades(open_rows):
    active_trade_ids = {row.get("trade_id") for row in open_rows if row.get("trade_id")}
    for trade_id in list(_TRADE_RUNTIME.keys()):
        if trade_id not in active_trade_ids:
            _TRADE_RUNTIME.pop(trade_id, None)


def _get_trade_runtime(trade_row, direction, atr_value):
    trade_id = trade_row.get("trade_id")
    if not trade_id:
        return {}

    runtime = _TRADE_RUNTIME.get(trade_id)
    if runtime is None:
        entry = _coerce_float(trade_row.get("entry"), 0.0)
        sl = trade_row.get("slValue")
        base_risk = abs(_coerce_float(sl, 0.0))
        if base_risk <= 0 and atr_value and atr_value > 0:
            base_risk = abs(_coerce_float(atr_value, 0.0))

        runtime = {
            "initial_lot": _coerce_float(trade_row.get("lot"), 0.0),
            "base_risk": max(base_risk, 1e-6),
            "stage1_done": False,
            "stage2_done": False,
            "break_even_done": False,
            "highest": entry,
            "lowest": entry,
            "mfe_price_distance": 0.0,
            "mae_price_distance": 0.0,
            "target_first_crossed_at": None,
            "updated_at": int(time.time()),
            "direction": direction,
        }
        _TRADE_RUNTIME[trade_id] = runtime

    runtime["updated_at"] = int(time.time())
    return runtime


def _normalize_close_lot(lot_value, constraints):
    lot = max(0.0, _coerce_float(lot_value, 0.0))
    if lot <= 0:
        return 0.0
    if constraints and constraints.get("volume_step"):
        lot = normalize_lot_with_constraints(lot, constraints)
    return max(0.0, lot)


def _profit_distance(direction, entry, price):
    if direction == "buy":
        return price - entry
    if direction == "sell":
        return entry - price
    return 0.0


def _normalize_trade_direction(trade_type):
    value = str(trade_type or "").strip().lower()
    if value in ("buy", "hedge_buy"):
        return "buy"
    if value in ("sell", "hedge_sell"):
        return "sell"
    return None


def _resolve_trade_atr_value(trade_row, fallback_atr=None):
    atr_value = _coerce_float((trade_row or {}).get("atr_value"), 0.0)
    if atr_value > 0:
        return atr_value

    signal_context = (trade_row or {}).get("signal_context") or {}
    if isinstance(signal_context, dict):
        context_atr = _coerce_float(signal_context.get("atr_value"), 0.0)
        if context_atr > 0:
            return context_atr
        timeframes = signal_context.get("timeframes") or {}
        values = []
        if isinstance(timeframes, dict):
            for payload in timeframes.values():
                if not isinstance(payload, dict):
                    continue
                value = _coerce_float(payload.get("atr"), 0.0)
                if value > 0:
                    values.append(value)
        if values:
            return sum(values) / len(values)

    fallback = _coerce_float(fallback_atr, 0.0)
    return fallback if fallback > 0 else 0.0


def _recent_direction_performance(trade_row, recent_closed_rows=None):
    recent_rows = recent_closed_rows
    if recent_rows is None:
        recent_rows = get_recent_closed_trades(
            limit=40,
            broker_id=(trade_row or {}).get("broker_id"),
            account_id=(trade_row or {}).get("account_id"),
        )

    direction = _normalize_trade_direction((trade_row or {}).get("type"))
    symbol = str((trade_row or {}).get("symbol") or "").strip().upper()
    if direction not in ("buy", "sell"):
        return {"samples": 0, "winrate": None, "avg_profit": None}

    matches = []
    for row in recent_rows or []:
        if _normalize_trade_direction((row or {}).get("type")) != direction:
            continue
        row_symbol = str((row or {}).get("symbol") or "").strip().upper()
        if symbol and row_symbol and row_symbol != symbol:
            continue
        matches.append(row)
        if len(matches) >= 12:
            break

    if not matches:
        return {"samples": 0, "winrate": None, "avg_profit": None}

    profits = [_coerce_float(row.get("profit"), 0.0) for row in matches]
    wins = len([profit for profit in profits if profit > 0])
    return {
        "samples": len(matches),
        "winrate": wins / len(matches),
        "avg_profit": sum(profits) / len(profits),
    }


def build_adaptive_target_snapshot(trade_row, account_state, recent_closed_rows=None, fallback_atr=None):
    row = dict(trade_row or {})
    direction = _normalize_trade_direction(row.get("type"))
    entry = _coerce_float(row.get("entry"), 0.0)
    base_tp_value = _coerce_float(row.get("tpValue"), 0.0)
    stop_distance = _coerce_float(row.get("slValue"), 0.0)
    atr_value = _resolve_trade_atr_value(row, fallback_atr=fallback_atr)
    signal_context = row.get("signal_context") if isinstance(row.get("signal_context"), dict) else {}

    if base_tp_value <= 0 and atr_value > 0:
        tp_mult = max(0.2, min(20.0, _coerce_float((account_state or {}).get("auto_trade_atr_tp_mult"), 2.5)))
        base_tp_value = atr_value * tp_mult

    target_price = None
    stop_price = None
    adaptive_factor = 1.0
    signal_score = _coerce_float(row.get("signal_score"), _coerce_float(signal_context.get("score"), 0.0))

    alignment_ratio = None
    tf_payload = signal_context.get("timeframes") or {}
    if direction in ("buy", "sell") and isinstance(tf_payload, dict) and tf_payload:
        aligned = 0
        total = 0
        for values in tf_payload.values():
            if not isinstance(values, dict):
                continue
            tf_direction = _normalize_trade_direction(values.get("direction"))
            if tf_direction not in ("buy", "sell"):
                continue
            total += 1
            if tf_direction == direction:
                aligned += 1
        if total > 0:
            alignment_ratio = aligned / total

    recent_perf = _recent_direction_performance(row, recent_closed_rows=recent_closed_rows)

    if signal_score > 0:
        adaptive_factor += max(-0.12, min(0.18, (signal_score - 0.55) * 0.8))
    if alignment_ratio is not None:
        adaptive_factor += max(-0.18, min(0.18, (alignment_ratio - 0.5) * 0.5))
    if recent_perf["samples"] >= 3 and recent_perf["winrate"] is not None:
        adaptive_factor += max(-0.15, min(0.15, (recent_perf["winrate"] - 0.5) * 0.5))

    adaptive_factor = max(0.65, min(1.75, adaptive_factor))
    effective_tp_value = base_tp_value * adaptive_factor if base_tp_value > 0 else 0.0

    if direction == "buy" and entry > 0 and effective_tp_value > 0:
        target_price = entry + effective_tp_value
    elif direction == "sell" and entry > 0 and effective_tp_value > 0:
        target_price = entry - effective_tp_value

    if direction == "buy" and entry > 0 and stop_distance > 0:
        stop_price = entry - stop_distance
    elif direction == "sell" and entry > 0 and stop_distance != 0:
        stop_price = entry + stop_distance

    return {
        "mode": "adaptive" if base_tp_value > 0 else "unavailable",
        "base_tp_value": _rounded(base_tp_value, 6),
        "effective_tp_value": _rounded(effective_tp_value, 6),
        "target_price": _rounded(target_price, 6),
        "stop_price": _rounded(stop_price, 6),
        "adaptive_factor": _rounded(adaptive_factor, 6),
        "signal_score": _rounded(signal_score, 6),
        "signal_alignment_ratio": _rounded(alignment_ratio, 6),
        "recent_winrate": _rounded(recent_perf.get("winrate"), 6),
        "recent_samples": int(recent_perf.get("samples") or 0),
        "recent_avg_profit": _rounded(recent_perf.get("avg_profit"), 6),
        "atr_value": _rounded(atr_value, 6),
    }


def _apply_partial_take_profit(state, trade_row, runtime, adapter, symbol, ticket, direction, entry, last_price, constraints):
    if not bool(state.get("auto_trade_partial_tp_enabled", True)):
        return False

    base_risk = max(1e-6, _coerce_float(runtime.get("base_risk"), 1e-6))
    rr_now = _profit_distance(direction, entry, last_price) / base_risk
    runtime["rr_now"] = rr_now
    if rr_now <= 0:
        return False

    initial_lot = max(0.0, _coerce_float(runtime.get("initial_lot"), _coerce_float(trade_row.get("lot"), 0.0)))
    remaining_lot = max(0.0, _coerce_float(trade_row.get("lot"), 0.0))

    stages = [
        {
            "name": "stage1",
            "rr": max(0.2, _coerce_float(state.get("auto_trade_partial_tp_rr1"), 1.0)),
            "pct": max(1.0, min(95.0, _coerce_float(state.get("auto_trade_partial_tp_close_pct1"), 40.0))),
            "flag": "stage1_done",
        },
        {
            "name": "stage2",
            "rr": max(0.2, _coerce_float(state.get("auto_trade_partial_tp_rr2"), 2.0)),
            "pct": max(1.0, min(95.0, _coerce_float(state.get("auto_trade_partial_tp_close_pct2"), 35.0))),
            "flag": "stage2_done",
        },
    ]

    for stage in stages:
        if runtime.get(stage["flag"]):
            continue
        if rr_now < stage["rr"]:
            continue

        lot_to_close = initial_lot * (stage["pct"] / 100.0)
        lot_to_close = min(lot_to_close, remaining_lot)
        lot_to_close = _normalize_close_lot(lot_to_close, constraints)
        if lot_to_close <= 0:
            runtime[stage["flag"]] = True
            continue

        try:
            result = adapter.close_trade(symbol, lot_to_close, ticket)
            order = result.get("order", {})
            apply_partial_close_record(
                trade_row.get("trade_id"),
                closed_lot=lot_to_close,
                exit_price=order.get("price", last_price),
                profit=order.get("profit"),
                exit_time=int(time.time()),
                reason=f"partial_take_profit_{stage['name']}",
            )
            runtime[stage["flag"]] = True
            return True
        except Exception as exc:
            log_mt5_error(
                f"Partial TP failed for trade {trade_row.get('trade_id')} ({stage['name']}): {exc}",
                broker_id=trade_row.get("broker_id"),
                broker_name=trade_row.get("broker_name"),
                account_id=trade_row.get("account_id"),
            )
            return False

    return False


def _apply_break_even_lock(state, trade_row, runtime, direction, entry, last_price, atr_value):
    if runtime.get("break_even_done"):
        return None
    if not bool(state.get("auto_trade_break_even_enabled", True)):
        return None

    base_risk = max(1e-6, _coerce_float(runtime.get("base_risk"), 1e-6))
    rr_now = _profit_distance(direction, entry, last_price) / base_risk
    runtime["rr_now"] = rr_now
    trigger_rr = max(0.2, min(5.0, _coerce_float(state.get("auto_trade_break_even_rr"), 1.0)))
    if rr_now < trigger_rr:
        return None

    offset_mult = max(0.0, min(2.0, _coerce_float(state.get("auto_trade_break_even_offset_atr_mult"), 0.1)))
    offset = (_coerce_float(atr_value, 0.0) * offset_mult) if atr_value and atr_value > 0 else 0.0

    new_sl = -offset
    current_sl = _coerce_float(trade_row.get("slValue"), 0.0)
    if new_sl < current_sl - 1e-9:
        update_open_trade_tpsl(trade_row.get("trade_id"), tp_value=trade_row.get("tpValue"), sl_value=new_sl)
        runtime["break_even_done"] = True
        return new_sl

    runtime["break_even_done"] = True
    return None


def _within_trade_session(start_hour: int, end_hour: int):
    hour_now = datetime.now().hour
    start = max(0, min(23, _coerce_int(start_hour, 0)))
    end = max(0, min(24, _coerce_int(end_hour, 24)))
    if start == end:
        return True
    if start < end:
        return start <= hour_now < end
    return hour_now >= start or hour_now < end


def _timeframe_weights(state):
    return {
        "M1": max(0.0, _coerce_float(state.get("auto_trade_tf_weight_m1"), 0.35)),
        "M5": max(0.0, _coerce_float(state.get("auto_trade_tf_weight_m5"), 0.30)),
        "M15": max(0.0, _coerce_float(state.get("auto_trade_tf_weight_m15"), 0.20)),
        "M30": max(0.0, _coerce_float(state.get("auto_trade_tf_weight_m30"), 0.15)),
        "H1": max(0.0, _coerce_float(state.get("auto_trade_tf_weight_h1"), 0.10)),
        "H4": max(0.0, _coerce_float(state.get("auto_trade_tf_weight_h4"), 0.05)),
        "D1": max(0.0, _coerce_float(state.get("auto_trade_tf_weight_d1"), 0.05)),
    }


def _resolve_analysis_timeframes(state):
    raw = state.get("auto_trade_timeframes")
    if isinstance(raw, (list, tuple)):
        return normalize_timeframes(raw)
    if isinstance(raw, str):
        return normalize_timeframes([part.strip() for part in raw.split(",")])
    return normalize_timeframes(None)


def _score_timeframe(values):
    rsi = values.get("rsi")
    macd = values.get("macd")
    macd_signal = values.get("macd_signal")
    bb_mid = values.get("bb_mid")
    sma = values.get("sma")

    buy = 0.0
    sell = 0.0
    total = 0.0

    if rsi is not None:
        rsi_value = _coerce_float(rsi, 50.0)
        buy += max(0.0, min(1.0, (70.0 - rsi_value) / 40.0))
        sell += max(0.0, min(1.0, (rsi_value - 30.0) / 40.0))
        total += 1.0

    if macd is not None and macd_signal is not None:
        diff = _coerce_float(macd) - _coerce_float(macd_signal)
        if diff > 0:
            buy += 1.0
        elif diff < 0:
            sell += 1.0
        else:
            buy += 0.5
            sell += 0.5
        total += 1.0

    if bb_mid is not None and sma is not None:
        if _coerce_float(sma) < _coerce_float(bb_mid):
            buy += 1.0
        else:
            sell += 1.0
        total += 1.0

    if total <= 0:
        return {"buy": 0.0, "sell": 0.0, "score": 0.0, "direction": "wait"}

    buy_score = buy / total
    sell_score = sell / total
    direction = "buy" if buy_score > sell_score else "sell" if sell_score > buy_score else "wait"
    return {
        "buy": buy_score,
        "sell": sell_score,
        "score": max(buy_score, sell_score),
        "direction": direction,
    }


def _signal_strength(signal_payload, state):
    indicators = (signal_payload or {}).get("indicators") or {}
    if not isinstance(indicators, dict) or not indicators:
        return {"buy": 0.0, "sell": 0.0, "direction": "wait", "score": 0.0, "per_timeframe": {}}

    weights = _timeframe_weights(state)
    model = str(state.get("auto_trade_confidence_model") or "weighted").strip().lower()

    buy_total = 0.0
    sell_total = 0.0
    weight_total = 0.0
    tf_scores = {}

    for timeframe, values in indicators.items():
        if not isinstance(values, dict):
            continue
        tf_score = _score_timeframe(values)
        tf_scores[timeframe] = tf_score
        weight = weights.get(str(timeframe).upper(), 0.0)
        if model != "weighted":
            weight = 1.0
        if weight <= 0:
            continue
        buy_total += tf_score["buy"] * weight
        sell_total += tf_score["sell"] * weight
        weight_total += weight

    if weight_total <= 0:
        return {"buy": 0.0, "sell": 0.0, "direction": "wait", "score": 0.0, "per_timeframe": tf_scores}

    buy_score = max(0.0, min(1.0, buy_total / weight_total))
    sell_score = max(0.0, min(1.0, sell_total / weight_total))

    direction = "wait"
    score = max(buy_score, sell_score)
    if buy_score > sell_score:
        direction = "buy"
    elif sell_score > buy_score:
        direction = "sell"

    return {
        "buy": buy_score,
        "sell": sell_score,
        "direction": direction,
        "score": score,
        "per_timeframe": tf_scores,
    }


def _resolve_atr_value(signal_payload):
    indicators = (signal_payload or {}).get("indicators") or {}
    if not isinstance(indicators, dict):
        return None

    m1 = indicators.get("M1") if isinstance(indicators.get("M1"), dict) else None
    atr_m1 = _coerce_float((m1 or {}).get("atr"), 0.0)
    if atr_m1 > 0:
        return atr_m1

    values = []
    for tf in ("M1", "M5", "M15", "M30"):
        atr = _coerce_float((indicators.get(tf) or {}).get("atr"), 0.0)
        if atr > 0:
            values.append(atr)
    if values:
        return sum(values) / len(values)
    return None


def _rounded(value, digits=6):
    if value is None:
        return None
    try:
        return round(float(value), int(digits))
    except Exception:
        return None


def _build_signal_context(signal_payload, signal_scoring, raw_signal, resolved_signal, atr_value):
    indicators = (signal_payload or {}).get("indicators") or {}
    per_tf = {}
    score_map = (signal_scoring or {}).get("per_timeframe") or {}
    for tf in sorted(indicators.keys()):
        values = indicators.get(tf)
        if not isinstance(values, dict):
            continue
        tf_score = score_map.get(tf) if isinstance(score_map.get(tf), dict) else {}
        per_tf[tf] = {
            "rsi": _rounded(values.get("rsi"), 3),
            "macd": _rounded(values.get("macd"), 6),
            "macd_signal": _rounded(values.get("macd_signal"), 6),
            "sma": _rounded(values.get("sma"), 6),
            "bb_mid": _rounded(values.get("bb_mid"), 6),
            "stoch_k": _rounded(values.get("stoch_k"), 3),
            "stoch_d": _rounded(values.get("stoch_d"), 3),
            "atr": _rounded(values.get("atr"), 6),
            "direction": tf_score.get("direction"),
            "score": _rounded(tf_score.get("score"), 6),
            "buy": _rounded(tf_score.get("buy"), 6),
            "sell": _rounded(tf_score.get("sell"), 6),
        }

    return {
        "captured_at": int(time.time()),
        "raw_signal": str(raw_signal or "wait"),
        "resolved_signal": str(resolved_signal or "wait"),
        "score": _rounded((signal_scoring or {}).get("score"), 6),
        "buy": _rounded((signal_scoring or {}).get("buy"), 6),
        "sell": _rounded((signal_scoring or {}).get("sell"), 6),
        "atr_value": _rounded(atr_value, 6),
        "timeframes": per_tf,
    }


def _passes_direction_bias_guard(signal, broker_id=None, account_id=None):
    direction = str(signal or "").strip().upper()
    if direction not in ("BUY", "SELL"):
        return True, None

    recent = get_recent_closed_trades(limit=18, broker_id=broker_id, account_id=account_id)
    if not recent:
        return True, None

    valid_rows = []
    for row in recent:
        trade_type = str(row.get("type") or "").strip().upper()
        if trade_type not in ("BUY", "SELL"):
            continue
        try:
            profit = float(row.get("profit") or 0.0)
        except Exception:
            profit = 0.0
        valid_rows.append({"type": trade_type, "profit": profit, "trade_id": row.get("trade_id")})

    if not valid_rows:
        return True, None

    consecutive_losses_same_side = 0
    for row in valid_rows:
        if row["type"] != direction:
            break
        if row["profit"] >= 0:
            break
        consecutive_losses_same_side += 1

    same_side_rows = [row for row in valid_rows if row["type"] == direction]
    same_side_count = len(same_side_rows)
    same_side_losses = len([row for row in same_side_rows if row["profit"] < 0])
    same_side_net = sum(row["profit"] for row in same_side_rows)
    ratio = (same_side_count / len(valid_rows)) if valid_rows else 0.0

    blocked = False
    reason = None
    if consecutive_losses_same_side >= 3:
        blocked = True
        reason = "direction_loss_streak_guard"
    elif same_side_count >= 8 and ratio >= 0.80 and same_side_net < 0:
        blocked = True
        reason = "direction_one_side_bias_guard"

    payload = {
        "direction": direction,
        "recent_rows": len(valid_rows),
        "same_side_count": same_side_count,
        "same_side_losses": same_side_losses,
        "same_side_net": round(same_side_net, 4),
        "same_side_ratio": round(ratio, 4),
        "consecutive_losses_same_side": consecutive_losses_same_side,
        "reason": reason,
    }
    return (not blocked), payload


def _passes_same_direction_open_guard(state, normal_open_rows, signal, max_open_trades):
    direction = str(signal or "").strip().upper()
    if direction not in ("BUY", "SELL"):
        return True, None

    default_cap = max(1, min(max_open_trades, 3))
    cap = max(1, min(max_open_trades, _coerce_int((state or {}).get("auto_trade_max_same_direction_trades"), default_cap)))

    same_side_open = len(
        [
            row
            for row in (normal_open_rows or [])
            if str(row.get("type") or "").strip().upper() == direction
        ]
    )
    if same_side_open >= cap:
        return False, {
            "direction": direction,
            "same_side_open": same_side_open,
            "cap": cap,
            "reason": "same_direction_open_limit",
        }
    return True, {
        "direction": direction,
        "same_side_open": same_side_open,
        "cap": cap,
        "reason": None,
    }


def _resolve_initial_tpsl(state, lot_to_open, atr_value):
    tp_value = state.get("tp_value", 0.5)
    sl_value = state.get("sl_value", None)

    if state.get("auto_analytic_tpsl", False):
        tp_value = round(2 * _coerce_float(lot_to_open, 0.01), 2)
        sl_value = round(1 * _coerce_float(lot_to_open, 0.01), 2)

    use_atr_tpsl = bool(state.get("auto_trade_use_atr_tpsl", True))
    if use_atr_tpsl and atr_value and atr_value > 0:
        sl_mult = max(0.2, min(10.0, _coerce_float(state.get("auto_trade_atr_sl_mult"), 1.5)))
        tp_mult = max(0.2, min(20.0, _coerce_float(state.get("auto_trade_atr_tp_mult"), 2.5)))
        sl_value = atr_value * sl_mult
        tp_value = atr_value * tp_mult

    return _coerce_float(tp_value, 0.0), _coerce_float(sl_value, 0.0)


def _resolve_protective_order_prices(state, broker, symbol, direction, tp_value, sl_value):
    mode = str((state or {}).get("auto_trade_protective_mode") or "broker_sl").strip().lower()
    if mode == "engine_only":
        return None, None

    tick_snapshot = get_broker_symbol_tick(broker, symbol=symbol, auto_start=False)
    if not tick_snapshot.get("ready"):
        return None, None

    bid = _coerce_float(tick_snapshot.get("bid"), 0.0)
    ask = _coerce_float(tick_snapshot.get("ask"), 0.0)
    if direction == "buy":
        entry_hint = ask if ask > 0 else _coerce_float(tick_snapshot.get("mid"), 0.0)
        sl_price = (entry_hint - _coerce_float(sl_value, 0.0)) if entry_hint > 0 and _coerce_float(sl_value, 0.0) > 0 else None
        tp_price = (entry_hint + _coerce_float(tp_value, 0.0)) if entry_hint > 0 and _coerce_float(tp_value, 0.0) > 0 else None
    elif direction == "sell":
        entry_hint = bid if bid > 0 else _coerce_float(tick_snapshot.get("mid"), 0.0)
        sl_price = (entry_hint + _coerce_float(sl_value, 0.0)) if entry_hint > 0 and _coerce_float(sl_value, 0.0) > 0 else None
        tp_price = (entry_hint - _coerce_float(tp_value, 0.0)) if entry_hint > 0 and _coerce_float(tp_value, 0.0) > 0 else None
    else:
        return None, None

    if mode == "broker_sl":
        return None, sl_price
    if mode == "broker_tpsl":
        return tp_price, sl_price
    return None, None


def _update_trade_runtime_path_metrics(trade_row, runtime, direction, entry, last_price, target_snapshot):
    if not runtime or direction not in ("buy", "sell") or entry <= 0 or last_price <= 0:
        return runtime

    highest = max(_coerce_float(runtime.get("highest"), entry), last_price)
    lowest = min(_coerce_float(runtime.get("lowest"), entry), last_price)
    runtime["highest"] = highest
    runtime["lowest"] = lowest

    if direction == "buy":
        runtime["mfe_price_distance"] = max(_coerce_float(runtime.get("mfe_price_distance"), 0.0), highest - entry)
        runtime["mae_price_distance"] = max(_coerce_float(runtime.get("mae_price_distance"), 0.0), entry - lowest)
    else:
        runtime["mfe_price_distance"] = max(_coerce_float(runtime.get("mfe_price_distance"), 0.0), entry - lowest)
        runtime["mae_price_distance"] = max(_coerce_float(runtime.get("mae_price_distance"), 0.0), highest - entry)

    target_price = _coerce_float((target_snapshot or {}).get("target_price"), 0.0)
    crossed = False
    if target_price > 0:
        if direction == "buy" and highest >= target_price:
            crossed = True
        elif direction == "sell" and lowest <= target_price:
            crossed = True
    if crossed and not runtime.get("target_first_crossed_at"):
        runtime["target_first_crossed_at"] = int(time.time())
    return runtime


def _apply_trailing_policy(state, trade_row, direction, entry, last_price, atr_value):
    if not bool(state.get("auto_trade_trailing_enabled", True)):
        return None

    trailing_mode = str(state.get("auto_trade_trailing_mode") or "stateful_hl").strip().lower()
    runtime = _get_trade_runtime(trade_row, direction, atr_value)
    if trailing_mode == "stateful_hl":
        bar = _latest_bar(trade_row.get("symbol") or "XAUUSD", trade_row.get("terminal_path"))
        if bar:
            runtime["highest"] = max(_coerce_float(runtime.get("highest"), entry), _coerce_float(bar.get("high"), last_price), last_price)
            runtime["lowest"] = min(_coerce_float(runtime.get("lowest"), entry), _coerce_float(bar.get("low"), last_price), last_price)

    if atr_value is None or atr_value <= 0:
        atr_value = 0.0

    current_sl = trade_row.get("slValue")
    if current_sl is None:
        return None
    current_sl = _coerce_float(current_sl, 0.0)

    activation_rr = max(0.2, min(5.0, _coerce_float(state.get("auto_trade_trailing_activation_rr"), 1.0)))
    trail_mult = max(0.2, min(10.0, _coerce_float(state.get("auto_trade_trailing_atr_mult"), 1.0)))
    trail_gap = atr_value * trail_mult
    if trailing_mode == "stateful_hl":
        buffer_mult = max(0.0, min(5.0, _coerce_float(state.get("auto_trade_stateful_trail_buffer_atr_mult"), 0.5)))
        trail_gap = atr_value * buffer_mult if atr_value > 0 else max(0.0, abs(current_sl) * 0.25)
    if trail_gap <= 0:
        return None

    if direction == "buy":
        profit_dist = last_price - entry
        activation_dist = max(0.0000001, abs(current_sl) * activation_rr)
        if profit_dist < activation_dist:
            return None
        if trailing_mode == "stateful_hl":
            highest = _coerce_float(runtime.get("highest"), last_price)
            new_stop_price = highest - trail_gap
        else:
            new_stop_price = last_price - trail_gap
        new_sl = entry - new_stop_price
    else:
        profit_dist = entry - last_price
        activation_dist = max(0.0000001, abs(current_sl) * activation_rr)
        if profit_dist < activation_dist:
            return None
        if trailing_mode == "stateful_hl":
            lowest = _coerce_float(runtime.get("lowest"), last_price)
            new_stop_price = lowest + trail_gap
        else:
            new_stop_price = last_price + trail_gap
        new_sl = new_stop_price - entry

    if new_sl < current_sl - 1e-9:
        update_open_trade_tpsl(trade_row.get("trade_id"), tp_value=trade_row.get("tpValue"), sl_value=new_sl)
        return new_sl
    return None


def _last_auto_action_at():
    history = get_trade_history()
    for row in reversed(history):
        reason = str(row.get("reason") or "")
        if not (reason.startswith("auto_open") or reason.startswith("auto_close")):
            continue
        return _coerce_int(row.get("exitTime") or row.get("entryTime") or 0, 0)
    return 0


def _risk_based_lot(state, constraints, metrics, manual_lot, sl_value, atr_value=None, risk_mode_override=None):
    risk_mode = str(risk_mode_override or state.get("auto_trade_risk_mode") or "fixed_lot").strip().lower()
    if risk_mode == "fixed_lot":
        return float(manual_lot)

    balance = _coerce_float((metrics or {}).get("balance"), _coerce_float(state.get("balance"), 0.0))
    equity = _coerce_float((metrics or {}).get("equity"), balance)
    reference_balance = _coerce_float(state.get("initial_balance"), balance)

    if risk_mode == "balance_scaled":
        if reference_balance <= 0:
            return float(manual_lot)
        scale_base = equity if bool(state.get("auto_trade_use_available_margin", True)) else balance
        if scale_base <= 0:
            return float(manual_lot)
        return max(0.0, float(manual_lot) * (scale_base / reference_balance))

    if risk_mode not in ("risk_percent", "atr_dynamic"):
        return float(manual_lot)

    sl = _coerce_float(sl_value, 0.0)
    if risk_mode == "atr_dynamic" and sl <= 0:
        atr_mult = max(0.2, min(10.0, _coerce_float(state.get("auto_trade_atr_sl_mult"), 1.5)))
        atr_source = _coerce_float(atr_value, 0.0)
        if atr_source <= 0:
            atr_source = _coerce_float((metrics or {}).get("atr_value"), 0.0)
        if atr_source > 0:
            sl = atr_source * atr_mult

    if sl <= 0:
        return float(manual_lot)

    use_available_margin = bool(state.get("auto_trade_use_available_margin", True))
    use_account_balance = bool(state.get("auto_trade_use_account_balance", True))

    if use_available_margin:
        risk_base = _coerce_float((metrics or {}).get("margin_free"), 0.0)
    elif use_account_balance:
        risk_base = _coerce_float((metrics or {}).get("balance"), 0.0)
    else:
        risk_base = _coerce_float(state.get("balance"), 0.0)

    if risk_base <= 0:
        return float(manual_lot)

    risk_percent = max(0.1, min(10.0, _coerce_float(state.get("auto_trade_risk_percent"), 1.0)))
    risk_amount = risk_base * (risk_percent / 100.0)

    tick_size = _coerce_float((constraints or {}).get("tick_size") or (metrics or {}).get("tick_size"), 0.0)
    tick_value = _coerce_float((constraints or {}).get("tick_value") or (metrics or {}).get("tick_value"), 0.0)
    contract_size = _coerce_float((metrics or {}).get("contract_size"), 0.0)

    loss_per_lot = 0.0
    if tick_size > 0 and tick_value > 0:
        loss_per_lot = (sl / tick_size) * tick_value
    elif contract_size > 0:
        loss_per_lot = sl * contract_size

    if loss_per_lot <= 0:
        return float(manual_lot)

    return max(0.0, risk_amount / loss_per_lot)


def _normalize_risk_mode(mode):
    value = str(mode or "fixed_lot").strip().lower()
    if value in ("fixed_lot", "risk_percent", "balance_scaled", "atr_dynamic", "hedge"):
        return value
    return "fixed_lot"


def _is_hedge_trade(row):
    trade_type = str((row or {}).get("type") or "").strip().lower()
    risk_mode = str((row or {}).get("risk_mode") or "").strip().lower()
    return trade_type in ("hedge_buy", "hedge_sell") or risk_mode == "hedge"


def _floating_loss_ratio_from_metrics(metrics):
    balance = _coerce_float((metrics or {}).get("balance"), 0.0)
    equity = _coerce_float((metrics or {}).get("equity"), 0.0)
    if equity <= 0:
        return 0.0
    return (equity - balance) / equity


def log_hedge_event(event):
    payload = dict(event or {})
    payload["timestamp"] = int(payload.get("timestamp") or time.time())
    payload["decision"] = payload.get("decision") or "hedge_triggered"
    payload["risk_mode"] = "hedge"
    return log_auto_trade_event(payload)


def trigger_hedge(trade, features):
    ctx = dict(trade or {})
    feat = dict(features or {})

    state = ctx.get("state") or {}
    broker = ctx.get("broker")
    symbol = str(ctx.get("symbol") or state.get("auto_trade_symbol") or "XAUUSD").strip() or "XAUUSD"
    metrics = ctx.get("metrics") or {}
    open_rows = list(ctx.get("open_rows") or [])
    if not broker:
        return {"status": "skip", "reason": "no_broker"}

    if not bool(state.get("hedge_enabled", True)):
        return {"status": "skip", "reason": "hedge_disabled"}

    hedge_threshold = _coerce_float(state.get("hedge_threshold"), -0.05)
    hedge_slots = max(0, _coerce_int(state.get("hedge_slots"), 2))
    floating_loss_ratio = _coerce_float(feat.get("floating_loss_ratio"), _floating_loss_ratio_from_metrics(metrics))

    hedge_open_rows = [row for row in open_rows if _is_hedge_trade(row)]
    if hedge_slots <= 0 or len(hedge_open_rows) >= hedge_slots:
        return {"status": "skip", "reason": "hedge_slots_full"}
    if floating_loss_ratio > hedge_threshold:
        return {"status": "skip", "reason": "hedge_not_required"}

    normal_rows = [row for row in open_rows if not _is_hedge_trade(row)]
    buy_lots = sum(_coerce_float(row.get("lot"), 0.0) for row in normal_rows if str(row.get("type") or "").upper() == "BUY")
    sell_lots = sum(_coerce_float(row.get("lot"), 0.0) for row in normal_rows if str(row.get("type") or "").upper() == "SELL")
    if buy_lots <= 0 and sell_lots <= 0:
        return {"status": "skip", "reason": "no_exposure_to_hedge"}

    hedge_direction = "sell" if buy_lots >= sell_lots else "buy"
    hedge_type = "hedge_sell" if hedge_direction == "sell" else "hedge_buy"
    dominant_exposure = max(buy_lots, sell_lots)

    constraints = ctx.get("constraints") or get_broker_symbol_constraints(broker, symbol=symbol, auto_start=False)
    base_lot = max(0.01, _coerce_float(state.get("lot"), 0.01))
    hedge_lot = min(dominant_exposure, base_lot)
    if hedge_lot <= 0:
        hedge_lot = base_lot
    if constraints.get("can_open_order") and constraints.get("volume_step"):
        hedge_lot = normalize_lot_with_constraints(hedge_lot, constraints)
    if hedge_lot <= 0:
        return {"status": "skip", "reason": "invalid_hedge_lot"}

    adapter, method = get_broker_adapter(broker, broker.get("execution_mode"))
    result = adapter.open_trade(symbol, hedge_lot, hedge_direction)
    order = (result or {}).get("order") or {}
    now = int(time.time())
    trade_id = str(uuid.uuid4())

    estimated_margin = _coerce_float((metrics or {}).get("estimated_margin_per_lot"), 0.0) * hedge_lot
    margin_free = _coerce_float((metrics or {}).get("margin_free"), 0.0)
    margin_usage_pct = (estimated_margin / margin_free) * 100.0 if margin_free > 0 and estimated_margin > 0 else None
    balance = _coerce_float((metrics or {}).get("balance"), 0.0)
    equity = _coerce_float((metrics or {}).get("equity"), balance)

    open_payload = {
        "trade_id": trade_id,
        "status": "open",
        "type": hedge_type,
        "symbol": symbol,
        "lot": hedge_lot,
        "ticket": order.get("ticket"),
        "entry": order.get("price"),
        "entryTime": now,
        "reason": f"hedge_open:floating={floating_loss_ratio:.4f}",
        "tpValue": None,
        "slValue": None,
        "broker_id": broker.get("id"),
        "broker_name": broker.get("name"),
        "account_id": (metrics or {}).get("account_id"),
        "platform": broker.get("platform"),
        "execution_mode": method,
        "terminal_path": broker.get("terminal_path"),
        "risk_mode": "hedge",
        "signal_score": _coerce_float(feat.get("signal_score"), 0.0),
        "spread_points": _coerce_int((metrics or {}).get("spread_points"), -1),
        "margin_usage_pct": margin_usage_pct,
        "equity": equity,
        "balance": balance,
        "session_hour": datetime.now().hour,
    }
    create_trade_open_record(open_payload)
    log_trade(
        open_payload,
        features={
            "spread_points": open_payload.get("spread_points"),
            "signal_score": open_payload.get("signal_score"),
            "margin_usage_pct": margin_usage_pct,
            "balance": balance,
            "equity": equity,
            "session_time": open_payload.get("session_hour"),
        },
        result={"status": "open", "risk_mode": "hedge"},
    )

    log_hedge_event(
        {
            "timestamp": now,
            "event_type": "hedge_open",
            "decision": "hedge_triggered",
            "trade_id": trade_id,
            "broker_id": broker.get("id"),
            "broker_name": broker.get("name"),
            "account_id": (metrics or {}).get("account_id"),
            "symbol": symbol,
            "signal_score": open_payload.get("signal_score"),
            "spread_points": open_payload.get("spread_points"),
            "margin_usage_pct": margin_usage_pct,
            "equity": equity,
            "balance": balance,
            "lot": hedge_lot,
            "profit": None,
            "rr": floating_loss_ratio,
            "reason": "floating_loss_threshold_breached",
            "payload": {
                "hedge_threshold": hedge_threshold,
                "floating_loss_ratio": floating_loss_ratio,
                "hedge_type": hedge_type,
            },
        }
    )
    return {"status": "ok", "trade_id": trade_id, "ticket": order.get("ticket"), "hedge_type": hedge_type}


def release_hedge(trade_id):
    open_rows = list_open_trades()
    target = None
    for row in open_rows:
        if str(row.get("trade_id") or "") == str(trade_id) and _is_hedge_trade(row):
            target = row
            break
    if not target:
        return {"status": "skip", "reason": "hedge_trade_not_found"}

    broker = get_broker(target.get("broker_id")) if target.get("broker_id") else get_default_broker()
    if not broker:
        return {"status": "error", "reason": "broker_not_found"}

    adapter, _ = get_broker_adapter(broker, target.get("execution_mode"))
    symbol = str(target.get("symbol") or "XAUUSD")
    ticket = _coerce_int(target.get("ticket"), 0)
    lot = max(0.01, _coerce_float(target.get("lot"), 0.01))
    if ticket <= 0:
        return {"status": "error", "reason": "invalid_ticket"}

    result = adapter.close_trade(symbol, lot, ticket)
    order = (result or {}).get("order") or {}
    now = int(time.time())

    close_payload = {
        "trade_id": target.get("trade_id"),
        "status": "closed",
        "type": target.get("type"),
        "symbol": symbol,
        "lot": lot,
        "ticket": ticket,
        "entry": target.get("entry"),
        "exit": order.get("price"),
        "profit": order.get("profit"),
        "entryTime": target.get("entryTime"),
        "exitTime": now,
        "reason": "hedge_close:market_normalized",
        "broker_id": target.get("broker_id"),
        "broker_name": target.get("broker_name"),
        "account_id": target.get("account_id"),
        "platform": target.get("platform"),
        "execution_mode": target.get("execution_mode"),
        "terminal_path": target.get("terminal_path"),
        "risk_mode": "hedge",
        "signal_score": target.get("signal_score"),
        "spread_points": target.get("spread_points"),
        "margin_usage_pct": target.get("margin_usage_pct"),
        "equity": target.get("equity"),
        "balance": target.get("balance"),
        "session_hour": datetime.now().hour,
    }
    log_trade(
        close_payload,
        features={
            "spread_points": close_payload.get("spread_points"),
            "signal_score": close_payload.get("signal_score"),
            "margin_usage_pct": close_payload.get("margin_usage_pct"),
            "balance": close_payload.get("balance"),
            "equity": close_payload.get("equity"),
            "session_time": close_payload.get("session_hour"),
        },
        result={"status": "closed", "risk_mode": "hedge", "profit": close_payload.get("profit")},
    )
    close_trade_record(
        close_payload.get("trade_id"),
        exit_price=close_payload.get("exit"),
        profit=close_payload.get("profit"),
        exit_time=now,
        ticket=ticket,
        reason="hedge_close:market_normalized",
    )

    log_hedge_event(
        {
            "timestamp": now,
            "event_type": "hedge_close",
            "decision": "hedge_triggered",
            "trade_id": close_payload.get("trade_id"),
            "broker_id": close_payload.get("broker_id"),
            "broker_name": close_payload.get("broker_name"),
            "account_id": close_payload.get("account_id"),
            "symbol": close_payload.get("symbol"),
            "signal_score": close_payload.get("signal_score"),
            "spread_points": close_payload.get("spread_points"),
            "margin_usage_pct": close_payload.get("margin_usage_pct"),
            "equity": close_payload.get("equity"),
            "balance": close_payload.get("balance"),
            "lot": close_payload.get("lot"),
            "profit": close_payload.get("profit"),
            "rr": None,
            "reason": "hedge_release_condition_met",
        }
    )
    return {"status": "ok", "trade_id": close_payload.get("trade_id")}


def _should_release_hedge(state, metrics, hedge_rows):
    if not hedge_rows:
        return False
    floating_loss_ratio = _floating_loss_ratio_from_metrics(metrics)
    threshold = _coerce_float((state or {}).get("hedge_threshold"), -0.05)
    release_threshold = min(-0.005, threshold * 0.5)
    return floating_loss_ratio > release_threshold


def _select_effective_risk_mode(state, metrics, signal_score, atr_value, open_rows, symbol, broker_id):
    manual_mode = _normalize_risk_mode(state.get("auto_trade_risk_mode"))
    strategy = str(state.get("auto_trade_risk_selector_strategy") or "manual").strip().lower()
    spread_points = _coerce_int((metrics or {}).get("spread_points"), -1)
    balance = _coerce_float((metrics or {}).get("balance"), _coerce_float(state.get("balance"), 0.0))
    conf = _coerce_float(signal_score, 0.0)
    atr = _coerce_float(atr_value, 0.0)

    atr_threshold = max(0.0, _coerce_float(state.get("auto_trade_risk_atr_threshold"), 12.0))
    balance_threshold = max(0.0, _coerce_float(state.get("auto_trade_risk_balance_fixed_threshold"), 500.0))
    confidence_threshold = max(0.0, min(1.0, _coerce_float(state.get("auto_trade_risk_confidence_threshold"), 0.70)))
    spread_fixed_threshold = max(0, _coerce_int(state.get("auto_trade_risk_spread_fixed_threshold"), 120))
    spread_low_threshold = max(0, _coerce_int(state.get("auto_trade_risk_spread_low_threshold"), 60))
    hybrid_addon_rr_threshold = max(0.2, _coerce_float(state.get("auto_trade_risk_hybrid_addon_rr_threshold"), 2.0))
    hybrid_entry_mode = _normalize_risk_mode(state.get("auto_trade_risk_hybrid_entry_mode") or "risk_percent")
    hybrid_addon_mode = _normalize_risk_mode(state.get("auto_trade_risk_hybrid_addon_mode") or "balance_scaled")

    selected = manual_mode
    reason = "manual"

    if strategy == "rule_based":
        if balance > 0 and balance < balance_threshold:
            selected, reason = "fixed_lot", "rule_balance_low"
        elif atr > 0 and atr >= atr_threshold:
            selected, reason = "atr_dynamic", "rule_atr_high"
        elif conf >= confidence_threshold:
            selected, reason = "risk_percent", "rule_confident_signal"
    elif strategy == "condition_driven":
        if spread_points >= 0 and spread_points >= spread_fixed_threshold:
            selected, reason = "fixed_lot", "condition_spread_high"
        elif spread_points >= 0 and spread_points <= spread_low_threshold and conf >= confidence_threshold:
            selected, reason = "balance_scaled", "condition_spread_low_confident"
        elif conf >= confidence_threshold:
            selected, reason = "risk_percent", "condition_confident_signal"
    elif strategy == "hybrid":
        selected, reason = hybrid_entry_mode, "hybrid_entry_mode"
        if open_rows:
            strongest_rr = 0.0
            for row in open_rows:
                runtime = _TRADE_RUNTIME.get(row.get("trade_id")) or {}
                rr_now = _coerce_float(runtime.get("rr_now"), 0.0)
                strongest_rr = max(strongest_rr, rr_now)
            if strongest_rr >= hybrid_addon_rr_threshold:
                selected, reason = hybrid_addon_mode, "hybrid_addon_mode"
    elif strategy == "adaptive":
        ml_result = predict_risk_mode(
            {
                "atr": atr,
                "spread_points": spread_points,
                "signal_score": conf,
                "margin_usage_pct": _coerce_float((metrics or {}).get("margin_usage_pct"), 0.0),
                "balance": balance,
                "equity": _coerce_float((metrics or {}).get("equity"), balance),
                "session_time": datetime.now().hour,
            }
        )
        ml_mode = _normalize_risk_mode((ml_result or {}).get("risk_mode"))
        if ml_mode in ("fixed_lot", "risk_percent", "balance_scaled", "atr_dynamic", "hedge"):
            selected = ml_mode
            reason = "adaptive_ml_prediction"
            return selected, reason, strategy, ml_result

        perf_rows = get_risk_mode_performance(
            window_days=max(7, _coerce_int(state.get("auto_trade_risk_adaptive_window_days"), 90)),
            broker_id=broker_id,
            account_id=(metrics or {}).get("account_id"),
            symbol=symbol,
        )
        min_trades = max(3, _coerce_int(state.get("auto_trade_risk_adaptive_min_trades"), 12))
        scored = []
        for row in perf_rows:
            total = int(row.get("total") or 0)
            if total < min_trades:
                continue
            score = (_coerce_float(row.get("winrate"), 0.0) * 0.7) + (_coerce_float(row.get("avg_profit"), 0.0) * 0.3)
            scored.append((score, _normalize_risk_mode(row.get("risk_mode"))))
        if scored:
            scored.sort(key=lambda item: item[0], reverse=True)
            selected = scored[0][1]
            reason = "adaptive_best_history"
        else:
            reason = "adaptive_fallback_manual"

    return selected, reason, strategy, None


def _passes_margin_guards(state, metrics, lot_to_open):
    estimated_margin_per_lot = _coerce_float((metrics or {}).get("estimated_margin_per_lot"), 0.0)
    if estimated_margin_per_lot <= 0:
        return True

    margin_free = _coerce_float((metrics or {}).get("margin_free"), 0.0)
    equity = _coerce_float((metrics or {}).get("equity"), _coerce_float((metrics or {}).get("balance"), 0.0))
    required_margin = estimated_margin_per_lot * max(0.0, _coerce_float(lot_to_open, 0.0))

    if margin_free <= 0:
        return False

    min_free_margin_pct = max(0.0, min(95.0, _coerce_float(state.get("auto_trade_min_free_margin_pct"), 30.0)))
    min_free_margin_value = equity * (min_free_margin_pct / 100.0)
    if margin_free - required_margin < min_free_margin_value:
        return False

    max_margin_usage_pct = max(1.0, min(100.0, _coerce_float(state.get("auto_trade_max_margin_usage_pct"), 70.0)))
    usage_pct = (required_margin / margin_free) * 100.0
    if usage_pct > max_margin_usage_pct:
        return False

    return True


def _run_auto_trade_cycle():
    _diag_event("cycle", "start")
    state = get_account_state()
    feed_broker = _get_feed_broker(state)
    symbol = "XAUUSD"
    if feed_broker and feed_broker.get("default_symbol"):
        symbol = str(feed_broker.get("default_symbol")).strip() or "XAUUSD"
    elif state.get("auto_trade_symbol"):
        symbol = str(state.get("auto_trade_symbol")).strip() or "XAUUSD"

    # Resolve per-account profile for the currently connected account on active broker.
    profile_account_id = None
    if feed_broker:
        profile_metrics = get_broker_account_metrics(feed_broker, symbol=symbol, auto_start=False)
        profile_account_id = profile_metrics.get("account_id") if isinstance(profile_metrics, dict) else None
        if profile_account_id is not None:
            state = apply_auto_trade_profile_to_state(state, feed_broker.get("id"), profile_account_id)
            symbol = str(state.get("auto_trade_symbol") or symbol).strip() or symbol

    auto_open_broker, _ = _resolve_auto_open_broker(state, symbol)

    keep_alive = bool(state.get("keep_terminal_alive", True))
    if keep_alive:
        preferred_terminal = None
        if auto_open_broker and auto_open_broker.get("terminal_path"):
            preferred_terminal = auto_open_broker.get("terminal_path")
        elif feed_broker and feed_broker.get("terminal_path"):
            preferred_terminal = feed_broker.get("terminal_path")

        if preferred_terminal:
            ensure_terminal_running(preferred_terminal)
        for t in list_open_trades():
            if t.get("terminal_path"):
                ensure_terminal_running(t.get("terminal_path"))

    if not state.get("auto_trade_enabled", False):
        _diag_event("skip", "auto_trade_disabled", symbol=symbol)
        return
    if not state.get("enable_real_trade", False):
        _diag_event("skip", "real_trade_disabled", symbol=symbol)
        return

    if not _within_trade_session(
        state.get("auto_trade_session_start_hour", 0),
        state.get("auto_trade_session_end_hour", 24),
    ):
        _diag_event("skip", "outside_session", symbol=symbol)
        return

    cooldown_sec = max(0, min(3600, _coerce_int(state.get("auto_trade_cooldown_sec"), 30)))
    last_action_at = _last_auto_action_at()
    if cooldown_sec > 0 and last_action_at > 0 and int(time.time()) - last_action_at < cooldown_sec:
        _diag_event("skip", "cooldown_active", symbol=symbol)
        return

    terminal_path = feed_broker.get("terminal_path") if feed_broker else None
    atr_period = max(5, min(100, _coerce_int(state.get("auto_trade_atr_period"), 14)))
    timeframes = _resolve_analysis_timeframes(state)
    signal_payload = analyze_symbol(symbol, mode="real", terminal_path=terminal_path, atr_period=atr_period, timeframes=timeframes)
    raw_signal = str(signal_payload.get("signal") or "wait").lower()
    signal_scoring = _signal_strength(signal_payload, state)
    signal = raw_signal if raw_signal in ("buy", "sell") else signal_scoring.get("direction", "wait")
    current_hour = datetime.now().hour
    _diag_event(
        "analysis",
        "signal_ready",
        symbol=symbol,
        signal=signal,
        signal_score=_coerce_float(signal_scoring.get("score"), 0.0),
    )

    min_signal_score = max(
        max(0.0, min(0.95, _coerce_float(state.get("auto_trade_min_signal_score"), 0.55))),
        max(0.0, min(0.95, _coerce_float(state.get("auto_trade_confidence_threshold"), 0.6))),
    )
    if signal in ("buy", "sell") and _coerce_float(signal_scoring.get("score"), 0.0) < min_signal_score:
        _diag_event(
            "skip",
            "signal_score_below_threshold",
            symbol=symbol,
            signal=signal,
            signal_score=_coerce_float(signal_scoring.get("score"), 0.0),
        )
        log_auto_trade_event(
            {
                "timestamp": int(time.time()),
                "event_type": "blocked",
                "reason": "signal_score_below_threshold",
                "broker_id": (auto_open_broker or {}).get("id") if auto_open_broker else None,
                "broker_name": (auto_open_broker or {}).get("name") if auto_open_broker else None,
                "account_id": (auto_open_broker or {}).get("account_id") if auto_open_broker else None,
                "symbol": symbol,
                "signal": signal,
                "signal_score": _coerce_float(signal_scoring.get("score"), 0.0),
                "session_hour": current_hour,
            }
        )
        signal = "wait"

    atr_value = _resolve_atr_value(signal_payload)
    signal_context = _build_signal_context(signal_payload, signal_scoring, raw_signal, signal, atr_value)

    if signal == "sell" and not bool(state.get("auto_trade_allow_sell", True)):
        _diag_event("skip", "sell_disabled", symbol=symbol, signal=signal)
        log_auto_trade_event(
            {
                "timestamp": int(time.time()),
                "event_type": "blocked",
                "reason": "sell_disabled",
                "symbol": symbol,
                "signal": signal,
                "session_hour": current_hour,
            }
        )
        signal = "wait"

    broker_for_guard = (auto_open_broker or feed_broker or {}).get("id") if (auto_open_broker or feed_broker) else None
    account_for_guard = profile_account_id
    if signal in ("buy", "sell"):
        guard_passed, guard_meta = _passes_direction_bias_guard(signal, broker_id=broker_for_guard, account_id=account_for_guard)
        if not guard_passed:
            _diag_event("skip", guard_meta.get("reason") or "direction_guard_blocked", symbol=symbol, signal=signal)
            log_auto_trade_event(
                {
                    "timestamp": int(time.time()),
                    "event_type": "blocked",
                    "reason": guard_meta.get("reason") or "direction_guard_blocked",
                    "broker_id": broker_for_guard,
                    "account_id": account_for_guard,
                    "symbol": symbol,
                    "signal": signal,
                    "signal_score": _coerce_float(signal_scoring.get("score"), 0.0),
                    "session_hour": current_hour,
                    "payload": {
                        "guard": guard_meta,
                        "signal_context": signal_context,
                    },
                }
            )
            signal = "wait"

    open_rows = list_open_trades()
    _cleanup_runtime_for_open_trades(open_rows)
    normal_open_rows = [row for row in open_rows if not _is_hedge_trade(row)]
    hedge_open_rows = [row for row in open_rows if _is_hedge_trade(row)]
    max_open_trades = max(1, _coerce_int(state.get("max_open_trades", 1), 1))

    if signal in ("buy", "sell"):
        passed_side_open_guard, side_open_meta = _passes_same_direction_open_guard(
            state,
            normal_open_rows,
            signal,
            max_open_trades,
        )
        if not passed_side_open_guard:
            _diag_event("skip", side_open_meta.get("reason") or "same_direction_open_limit", symbol=symbol, signal=signal)
            log_auto_trade_event(
                {
                    "timestamp": int(time.time()),
                    "event_type": "blocked",
                    "reason": side_open_meta.get("reason") or "same_direction_open_limit",
                    "broker_id": (auto_open_broker or feed_broker or {}).get("id") if (auto_open_broker or feed_broker) else None,
                    "broker_name": (auto_open_broker or feed_broker or {}).get("name") if (auto_open_broker or feed_broker) else None,
                    "account_id": profile_account_id,
                    "symbol": symbol,
                    "signal": signal,
                    "signal_score": _coerce_float(signal_scoring.get("score"), 0.0),
                    "session_hour": current_hour,
                    "payload": {
                        "guard": side_open_meta,
                        "signal_context": signal_context,
                    },
                }
            )
            signal = "wait"

    hedge_broker = auto_open_broker or feed_broker
    hedge_metrics = {}
    hedge_constraints = {}
    if hedge_broker:
        try:
            hedge_metrics = get_broker_account_metrics(hedge_broker, symbol=symbol, auto_start=False) or {}
            hedge_constraints = get_broker_symbol_constraints(hedge_broker, symbol=symbol, auto_start=False) or {}
        except Exception as exc:
            log_mt5_error(
                f"hedge precheck failed: {exc}",
                broker_id=(hedge_broker or {}).get("id"),
                broker_name=(hedge_broker or {}).get("name"),
                account_id=(hedge_metrics or {}).get("account_id"),
            )

    if _should_release_hedge(state, hedge_metrics, hedge_open_rows):
        for hedge_row in hedge_open_rows:
            try:
                release_hedge(hedge_row.get("trade_id"))
            except Exception as exc:
                log_mt5_error(
                    f"hedge release failed for {hedge_row.get('trade_id')}: {exc}",
                    broker_id=hedge_row.get("broker_id"),
                    broker_name=hedge_row.get("broker_name"),
                    account_id=hedge_row.get("account_id"),
                )

    try:
        trigger_hedge(
            {
                "state": state,
                "broker": hedge_broker,
                "symbol": symbol,
                "metrics": hedge_metrics,
                "constraints": hedge_constraints,
                "open_rows": open_rows,
            },
            {
                "floating_loss_ratio": _floating_loss_ratio_from_metrics(hedge_metrics),
                "signal_score": _coerce_float(signal_scoring.get("score"), 0.0),
            },
        )
    except Exception as exc:
        log_mt5_error(
            f"hedge trigger failed: {exc}",
            broker_id=(hedge_broker or {}).get("id"),
            broker_name=(hedge_broker or {}).get("name"),
            account_id=(hedge_metrics or {}).get("account_id"),
        )

    if len(normal_open_rows) < max_open_trades and signal in ("buy", "sell"):
        broker = auto_open_broker
        if not broker:
            _diag_open_attempt("error", reason="no_broker", symbol=symbol, signal=signal)
            _diag_event("skip", "no_broker_for_open", symbol=symbol, signal=signal)
            log_auto_trade_event({"timestamp": int(time.time()), "event_type": "blocked", "reason": "no_broker", "symbol": symbol, "signal": signal, "session_hour": current_hour})
            return
        broker_status = probe_broker_order_status(broker, symbol=symbol, auto_start=True)
        if not broker_status.get("can_open_order"):
            _diag_open_attempt(
                "error",
                reason="broker_not_ready",
                broker_name=broker.get("name"),
                broker_reason=broker_status.get("reason"),
                symbol=symbol,
                signal=signal,
            )
            _diag_event(
                "skip",
                "broker_not_ready",
                symbol=symbol,
                signal=signal,
                signal_score=_coerce_float(signal_scoring.get("score"), 0.0),
            )
            log_auto_trade_event(
                {
                    "timestamp": int(time.time()),
                    "event_type": "blocked",
                    "reason": "broker_not_ready",
                    "broker_id": broker.get("id"),
                    "broker_name": broker.get("name"),
                    "symbol": symbol,
                    "signal": signal,
                    "signal_score": _coerce_float(signal_scoring.get("score"), 0.0),
                    "session_hour": current_hour,
                }
            )
            return

        constraints = get_broker_symbol_constraints(broker, symbol=symbol, auto_start=False)
        metrics = get_broker_account_metrics(broker, symbol=symbol, auto_start=False)

        max_spread_points = max(0, _coerce_int(state.get("auto_trade_max_spread_points"), 120))
        spread_points = _coerce_int((metrics or {}).get("spread_points"), -1)
        if spread_points >= 0 and max_spread_points > 0 and spread_points > max_spread_points:
            _diag_open_attempt(
                "error",
                reason="spread_too_high",
                spread_points=spread_points,
                max_spread_points=max_spread_points,
                broker_name=broker.get("name"),
                symbol=symbol,
                signal=signal,
            )
            _diag_event("skip", "spread_too_high", symbol=symbol, signal=signal)
            margin_usage_pct = None
            margin_free = _coerce_float((metrics or {}).get("margin_free"), 0.0)
            equity = _coerce_float((metrics or {}).get("equity"), _coerce_float((metrics or {}).get("balance"), 0.0))
            estimated_margin = _coerce_float((metrics or {}).get("estimated_margin_per_lot"), 0.0) * max(0.0, _coerce_float(state.get("lot"), 0.0))
            if margin_free > 0 and estimated_margin > 0:
                margin_usage_pct = (estimated_margin / margin_free) * 100.0
            log_auto_trade_event(
                {
                    "timestamp": int(time.time()),
                    "event_type": "blocked",
                    "reason": "spread_too_high",
                    "broker_id": broker.get("id"),
                    "broker_name": broker.get("name"),
                    "account_id": (metrics or {}).get("account_id"),
                    "symbol": symbol,
                    "signal": signal,
                    "signal_score": _coerce_float(signal_scoring.get("score"), 0.0),
                    "spread_points": spread_points,
                    "max_spread_points": max_spread_points,
                    "margin_free": margin_free,
                    "equity": equity,
                    "balance": _coerce_float((metrics or {}).get("balance"), equity),
                    "margin_usage_pct": margin_usage_pct,
                    "atr_value": atr_value,
                    "trailing_mode": state.get("auto_trade_trailing_mode"),
                    "risk_mode": state.get("auto_trade_risk_mode"),
                    "session_hour": current_hour,
                }
            )
            return

        manual_lot = _coerce_float(state.get("lot"), 0.01)
        sl_for_risk = state.get("sl_value")
        if state.get("auto_analytic_tpsl", False):
            sl_for_risk = round(1 * manual_lot, 2)
        if bool(state.get("auto_trade_use_atr_tpsl", True)) and atr_value and atr_value > 0:
            sl_for_risk = atr_value * max(0.2, min(10.0, _coerce_float(state.get("auto_trade_atr_sl_mult"), 1.5)))
        effective_risk_mode, risk_mode_reason, risk_selector_strategy, adaptive_meta = _select_effective_risk_mode(
            state,
            metrics,
            _coerce_float(signal_scoring.get("score"), 0.0),
            atr_value,
            open_rows,
            symbol,
            broker.get("id"),
        )
        estimated_margin = _coerce_float((metrics or {}).get("estimated_margin_per_lot"), 0.0) * max(0.0, _coerce_float(state.get("lot"), 0.0))
        margin_free_snapshot = _coerce_float((metrics or {}).get("margin_free"), 0.0)
        margin_usage_snapshot = (estimated_margin / margin_free_snapshot) * 100.0 if margin_free_snapshot > 0 and estimated_margin > 0 else None
        log_auto_trade_event(
            {
                "timestamp": int(time.time()),
                "event_type": "analysis",
                "decision": f"risk_mode_recommendation:{effective_risk_mode}",
                "reason": risk_mode_reason,
                "broker_id": broker.get("id"),
                "broker_name": broker.get("name"),
                "account_id": (metrics or {}).get("account_id"),
                "symbol": symbol,
                "signal": signal,
                "signal_score": _coerce_float(signal_scoring.get("score"), 0.0),
                "spread_points": spread_points if spread_points >= 0 else None,
                "max_spread_points": max_spread_points,
                "margin_free": margin_free_snapshot,
                "equity": _coerce_float((metrics or {}).get("equity"), _coerce_float((metrics or {}).get("balance"), 0.0)),
                "balance": _coerce_float((metrics or {}).get("balance"), 0.0),
                "margin_usage_pct": margin_usage_snapshot,
                "atr_value": atr_value,
                "trailing_mode": state.get("auto_trade_trailing_mode"),
                "risk_mode": effective_risk_mode,
                "lot_mode": effective_risk_mode,
                "lot": _coerce_float(state.get("lot"), 0.01),
                "session_hour": current_hour,
                "payload": {
                    "risk_selector_strategy": risk_selector_strategy,
                    "manual_mode": state.get("auto_trade_risk_mode"),
                    "adaptive_meta": adaptive_meta,
                },
            }
        )
        if effective_risk_mode == "hedge":
            trigger_hedge(
                {
                    "state": state,
                    "broker": broker,
                    "symbol": symbol,
                    "metrics": metrics,
                    "constraints": constraints,
                    "open_rows": open_rows,
                },
                {
                    "floating_loss_ratio": _floating_loss_ratio_from_metrics(metrics),
                    "signal_score": _coerce_float(signal_scoring.get("score"), 0.0),
                },
            )
            _diag_event("action", "hedge_triggered_by_adaptive_ml", symbol=symbol, signal=signal)
            return

        lot_to_open = _risk_based_lot(
            state,
            constraints,
            metrics,
            manual_lot,
            sl_for_risk,
            atr_value=atr_value,
            risk_mode_override=effective_risk_mode,
        )

        if constraints.get("can_open_order") and constraints.get("volume_step"):
            lot_to_open = normalize_lot_with_constraints(lot_to_open, constraints)

        if lot_to_open <= 0:
            _diag_open_attempt("error", reason="lot_to_open_zero", broker_name=broker.get("name"), symbol=symbol, signal=signal)
            _diag_event("skip", "lot_to_open_zero", symbol=symbol, signal=signal)
            log_auto_trade_event({"timestamp": int(time.time()), "event_type": "blocked", "reason": "lot_to_open_zero", "broker_id": broker.get("id"), "broker_name": broker.get("name"), "account_id": (metrics or {}).get("account_id"), "symbol": symbol, "signal": signal, "signal_score": _coerce_float(signal_scoring.get("score"), 0.0), "atr_value": atr_value, "session_hour": current_hour})
            return

        if not _passes_margin_guards(state, metrics, lot_to_open):
            _diag_open_attempt("error", reason="margin_guard_blocked", broker_name=broker.get("name"), symbol=symbol, signal=signal)
            _diag_event("skip", "margin_guard_blocked", symbol=symbol, signal=signal)
            log_auto_trade_event(
                {
                    "timestamp": int(time.time()),
                    "event_type": "blocked",
                    "reason": "margin_guard_blocked",
                    "broker_id": broker.get("id"),
                    "broker_name": broker.get("name"),
                    "account_id": (metrics or {}).get("account_id"),
                    "symbol": symbol,
                    "signal": signal,
                    "signal_score": _coerce_float(signal_scoring.get("score"), 0.0),
                    "margin_free": _coerce_float((metrics or {}).get("margin_free"), 0.0),
                    "equity": _coerce_float((metrics or {}).get("equity"), _coerce_float((metrics or {}).get("balance"), 0.0)),
                    "balance": _coerce_float((metrics or {}).get("balance"), 0.0),
                    "margin_usage_pct": None,
                    "atr_value": atr_value,
                    "trailing_mode": state.get("auto_trade_trailing_mode"),
                    "risk_mode": state.get("auto_trade_risk_mode"),
                    "lot": lot_to_open,
                    "session_hour": current_hour,
                }
            )
            return

        if abs(lot_to_open - manual_lot) > 1e-9:
            state["lot"] = lot_to_open
            save_account_state(state)

        adapter, method = get_broker_adapter(broker, broker.get("execution_mode"))
        _diag_open_attempt(
            "attempt",
            broker_name=broker.get("name"),
            symbol=symbol,
            signal=signal,
            lot=lot_to_open,
            method=method,
            score=_coerce_float(signal_scoring.get("score"), 0.0),
        )
        tp_value, sl_value = _resolve_initial_tpsl(state, lot_to_open, atr_value)
        try:
            protective_tp, protective_sl = (None, None)
            if method != "mouse":
                protective_tp, protective_sl = _resolve_protective_order_prices(
                    state,
                    broker,
                    symbol,
                    signal,
                    tp_value,
                    sl_value,
                )
            result = adapter.open_trade(symbol, lot_to_open, signal, tp=protective_tp, sl=protective_sl)
        except Exception as exc:
            _diag_open_attempt(
                "error",
                reason="open_trade_exception",
                broker_name=broker.get("name"),
                symbol=symbol,
                signal=signal,
                lot=lot_to_open,
                method=method,
                error=str(exc),
            )
            _diag_event("skip", "open_trade_exception", symbol=symbol, signal=signal)
            log_auto_trade_event(
                {
                    "timestamp": int(time.time()),
                    "event_type": "open_error",
                    "reason": "open_trade_exception",
                    "broker_id": broker.get("id"),
                    "broker_name": broker.get("name"),
                    "account_id": (metrics or {}).get("account_id"),
                    "symbol": symbol,
                    "signal": signal,
                    "signal_score": _coerce_float(signal_scoring.get("score"), 0.0),
                    "lot": lot_to_open,
                    "trailing_mode": state.get("auto_trade_trailing_mode"),
                    "risk_mode": state.get("auto_trade_risk_mode"),
                    "atr_value": atr_value,
                    "session_hour": current_hour,
                    "payload": {"error": str(exc)},
                }
            )
            raise
        order = result.get("order", {})
        now = int(time.time())
        trade_id = str(uuid.uuid4())
        estimated_margin = _coerce_float((metrics or {}).get("estimated_margin_per_lot"), 0.0) * max(0.0, lot_to_open)
        margin_free = _coerce_float((metrics or {}).get("margin_free"), 0.0)
        equity = _coerce_float((metrics or {}).get("equity"), _coerce_float((metrics or {}).get("balance"), 0.0))
        margin_usage_pct = (estimated_margin / margin_free) * 100.0 if margin_free > 0 and estimated_margin > 0 else None

        open_trade_payload = {
            "trade_id": trade_id,
            "status": "open",
            "type": signal.upper(),
            "symbol": symbol,
            "lot": lot_to_open,
            "ticket": order.get("ticket"),
            "entry": order.get("price"),
            "entryTime": now,
            "reason": f"auto_open:{signal_scoring.get('score', 0.0):.3f}",
            "tpValue": tp_value,
            "slValue": sl_value,
            "broker_id": broker.get("id"),
            "broker_name": broker.get("name"),
            "account_id": (metrics or {}).get("account_id"),
            "platform": broker.get("platform"),
            "execution_mode": method,
            "terminal_path": broker.get("terminal_path"),
            "trailing_mode": state.get("auto_trade_trailing_mode"),
            "risk_mode": effective_risk_mode,
            "signal_score": _coerce_float(signal_scoring.get("score"), 0.0),
            "spread_points": spread_points if spread_points >= 0 else None,
            "margin_usage_pct": margin_usage_pct,
            "equity": equity,
            "balance": _coerce_float((metrics or {}).get("balance"), equity),
            "atr_value": atr_value,
            "session_hour": current_hour,
            "signal_context": signal_context,
        }
        target_snapshot = build_adaptive_target_snapshot(
            open_trade_payload,
            state,
            recent_closed_rows=get_recent_closed_trades(
                limit=40,
                broker_id=broker.get("id"),
                account_id=(metrics or {}).get("account_id"),
            ),
            fallback_atr=atr_value,
        )
        if isinstance(open_trade_payload.get("signal_context"), dict):
            open_trade_payload["signal_context"] = {
                **open_trade_payload["signal_context"],
                "target_plan": {
                    "base_tp_value": target_snapshot.get("base_tp_value"),
                    "effective_tp_value": target_snapshot.get("effective_tp_value"),
                    "target_price": target_snapshot.get("target_price"),
                    "adaptive_factor": target_snapshot.get("adaptive_factor"),
                    "recent_winrate": target_snapshot.get("recent_winrate"),
                    "recent_samples": target_snapshot.get("recent_samples"),
                },
            }
        create_trade_open_record(open_trade_payload)
        log_trade(
            open_trade_payload,
            features={
                "atr": atr_value,
                "spread_points": spread_points if spread_points >= 0 else None,
                "signal_score": _coerce_float(signal_scoring.get("score"), 0.0),
                "margin_usage_pct": margin_usage_pct,
                "balance": _coerce_float((metrics or {}).get("balance"), equity),
                "equity": equity,
                "session_time": current_hour,
                "target_tp_value": target_snapshot.get("effective_tp_value"),
                "target_factor": target_snapshot.get("adaptive_factor"),
            },
            result={"status": "open", "risk_mode": effective_risk_mode},
        )
        log_auto_trade_event(
            {
                "timestamp": now,
                "event_type": "open_success",
                "trade_id": trade_id,
                "broker_id": broker.get("id"),
                "broker_name": broker.get("name"),
                "account_id": (metrics or {}).get("account_id"),
                "symbol": symbol,
                "signal": signal,
                "signal_score": _coerce_float(signal_scoring.get("score"), 0.0),
                "spread_points": spread_points if spread_points >= 0 else None,
                "max_spread_points": max_spread_points,
                "margin_free": margin_free,
                "equity": equity,
                "balance": _coerce_float((metrics or {}).get("balance"), equity),
                "margin_usage_pct": margin_usage_pct,
                "atr_value": atr_value,
                "trailing_mode": state.get("auto_trade_trailing_mode"),
                "risk_mode": effective_risk_mode,
                "lot_mode": effective_risk_mode,
                "lot": lot_to_open,
                "session_hour": current_hour,
                "payload": {
                    "risk_selector_strategy": risk_selector_strategy,
                    "risk_mode_reason": risk_mode_reason,
                    "manual_mode": state.get("auto_trade_risk_mode"),
                    "adaptive_meta": adaptive_meta,
                    "signal_context": signal_context,
                },
            }
        )
        _diag_open_attempt(
            "ok",
            broker_name=broker.get("name"),
            symbol=symbol,
            signal=signal,
            lot=lot_to_open,
            ticket=order.get("ticket"),
            method=method,
            score=_coerce_float(signal_scoring.get("score"), 0.0),
        )
        _diag_event("action", "open_trade_created", symbol=symbol, signal=signal)
        return

    if len(normal_open_rows) >= max_open_trades and signal in ("buy", "sell"):
        _diag_event("skip", "max_open_trades_reached", symbol=symbol, signal=signal)
    elif signal == "wait":
        _diag_event(
            "skip",
            "no_actionable_signal",
            symbol=symbol,
            signal=signal,
            signal_score=_coerce_float(signal_scoring.get("score"), 0.0),
        )

    recent_closed_rows = get_recent_closed_trades(limit=40)
    for t in open_rows:
        if _is_hedge_trade(t):
            continue
        broker = get_broker(t.get("broker_id")) if t.get("broker_id") else get_default_broker()
        if not broker:
            continue
        adapter, method = get_broker_adapter(broker, t.get("execution_mode"))
        if method == "mouse":
            continue

        direction = _normalize_trade_direction(t.get("type"))
        if direction not in ("buy", "sell"):
            continue

        last_price = 0.0
        tick_snapshot = get_broker_symbol_tick(broker, symbol=t.get("symbol") or symbol, auto_start=False)
        if tick_snapshot.get("ready"):
            if direction == "buy":
                last_price = _coerce_float(tick_snapshot.get("close_buy_price"), 0.0)
            elif direction == "sell":
                last_price = _coerce_float(tick_snapshot.get("close_sell_price"), 0.0)
            if last_price <= 0:
                last_price = _coerce_float(tick_snapshot.get("mid"), 0.0)

        if last_price <= 0:
            latest_bar = _latest_bar(t.get("symbol") or symbol, broker.get("terminal_path"))
            if latest_bar is None:
                continue
            last_price = _coerce_float(latest_bar.get("close"), 0.0)
        if last_price <= 0:
            continue

        entry = t.get("entry")
        if entry is None:
            continue
        entry = float(entry)
        tp = t.get("tpValue")
        sl = t.get("slValue")
        trade_runtime = _get_trade_runtime(t, direction, atr_value)
        ticket = int(t.get("ticket") or 0)
        target_snapshot = build_adaptive_target_snapshot(t, state, recent_closed_rows=recent_closed_rows, fallback_atr=atr_value)
        effective_tp_value = _coerce_float(target_snapshot.get("effective_tp_value"), _coerce_float(tp, 0.0))
        _update_trade_runtime_path_metrics(t, trade_runtime, direction, entry, last_price, target_snapshot)

        constraints = get_broker_symbol_constraints(broker, symbol=t.get("symbol") or symbol, auto_start=False)
        if ticket > 0:
            did_partial_close = _apply_partial_take_profit(
                state,
                t,
                trade_runtime,
                adapter,
                t.get("symbol") or symbol,
                ticket,
                direction,
                entry,
                last_price,
                constraints,
            )
            if did_partial_close:
                continue

        break_even_sl = _apply_break_even_lock(state, t, trade_runtime, direction, entry, last_price, atr_value)
        if break_even_sl is not None:
            sl = break_even_sl

        updated_sl = _apply_trailing_policy(state, t, direction, entry, last_price, atr_value)
        if updated_sl is not None:
            sl = updated_sl

        should_close = False
        close_reason = None
        if effective_tp_value > 0:
            if direction == "buy" and last_price >= entry + effective_tp_value:
                should_close = True
                close_reason = "auto_close_tp"
            if direction == "sell" and last_price <= entry - effective_tp_value:
                should_close = True
                close_reason = "auto_close_tp"

        if (not should_close) and sl is not None:
            sl = float(sl)
            if direction == "buy" and last_price <= entry - sl:
                should_close = True
                close_reason = "auto_close_sl"
            if direction == "sell" and last_price >= entry + sl:
                should_close = True
                close_reason = "auto_close_sl"

        if not should_close and signal in ("buy", "sell") and signal != direction:
            required_cycles = max(1, min(20, _coerce_int(state.get("auto_trade_reversal_confirm_cycles"), 2)))
            min_hold_sec = max(0, min(86400, _coerce_int(state.get("auto_trade_min_hold_sec"), 15)))
            entry_time = _coerce_int(t.get("entryTime"), int(time.time()))
            held_sec = max(0, int(time.time()) - entry_time)

            previous_signal = str(trade_runtime.get("reversal_signal") or "")
            if previous_signal == signal:
                trade_runtime["reversal_count"] = _coerce_int(trade_runtime.get("reversal_count"), 0) + 1
            else:
                trade_runtime["reversal_signal"] = signal
                trade_runtime["reversal_count"] = 1

            if held_sec >= min_hold_sec and _coerce_int(trade_runtime.get("reversal_count"), 0) >= required_cycles:
                should_close = True
                close_reason = "auto_close_reversal_confirmed"
        elif signal == direction or signal == "wait":
            trade_runtime["reversal_signal"] = None
            trade_runtime["reversal_count"] = 0

        if not should_close:
            continue

        if ticket <= 0:
            continue

        try:
            _diag_close_attempt(
                "attempt",
                trade_id=t.get("trade_id"),
                symbol=t.get("symbol") or symbol,
                ticket=ticket,
                direction=direction,
            )
            result = adapter.close_trade(t.get("symbol") or symbol, float(t.get("lot") or 0.01), ticket)
            order = result.get("order", {})
            close_trade_record(
                t.get("trade_id"),
                exit_price=order.get("price", last_price),
                profit=order.get("profit"),
                exit_time=int(time.time()),
                ticket=ticket,
                reason=close_reason or "auto_close",
                runtime_metrics={
                    "mfe_price_distance": trade_runtime.get("mfe_price_distance"),
                    "mae_price_distance": trade_runtime.get("mae_price_distance"),
                    "target_first_crossed_at": trade_runtime.get("target_first_crossed_at"),
                },
            )
            _diag_close_attempt(
                "ok",
                trade_id=t.get("trade_id"),
                symbol=t.get("symbol") or symbol,
                ticket=ticket,
            )
            _diag_event("action", "auto_close_done", symbol=t.get("symbol") or symbol)
        except Exception as exc:
            _diag_close_attempt(
                "error",
                trade_id=t.get("trade_id"),
                symbol=t.get("symbol") or symbol,
                ticket=ticket,
                error=str(exc),
            )
            log_mt5_error(
                f"Auto close failed for trade {t.get('trade_id')}: {exc}",
                broker_id=broker.get("id"),
                broker_name=broker.get("name"),
                account_id=t.get("account_id"),
            )


def _auto_trade_loop():
    while True:
        try:
            _run_auto_trade_cycle()
        except Exception as exc:
            _diag_event("error", "cycle_exception", error=str(exc))
        try:
            state = get_account_state()
            interval = float(state.get("auto_trade_interval_sec", 2) or 2)
        except Exception:
            interval = 2
        interval = max(1.0, min(interval, 60.0))
        time.sleep(interval)


def start_auto_trader_thread():
    global _loop_started
    if _loop_started:
        return
    _loop_started = True
    t = threading.Thread(target=_auto_trade_loop, daemon=True)
    t.start()


def is_auto_trader_thread_started():
    return bool(_loop_started)
