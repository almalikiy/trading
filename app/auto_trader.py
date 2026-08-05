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
    list_brokers,
    list_open_trades,
    log_mt5_error,
    resolve_feed_broker,
    save_account_state,
    update_open_trade_tpsl,
)
from .logic import analyze_symbol, fetch_ohlcv
from .terminal_adapters import (
    ensure_terminal_running,
    get_broker_adapter,
    get_broker_account_metrics,
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


def _apply_partial_take_profit(state, trade_row, runtime, adapter, symbol, ticket, direction, entry, last_price, constraints):
    if not bool(state.get("auto_trade_partial_tp_enabled", True)):
        return False

    base_risk = max(1e-6, _coerce_float(runtime.get("base_risk"), 1e-6))
    rr_now = _profit_distance(direction, entry, last_price) / base_risk
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
    }


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


def _risk_based_lot(state, constraints, metrics, manual_lot, sl_value):
    risk_mode = str(state.get("auto_trade_risk_mode") or "fixed_lot").strip().lower()
    if risk_mode != "risk_percent":
        return float(manual_lot)

    sl = _coerce_float(sl_value, 0.0)
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
    signal_payload = analyze_symbol(symbol, mode="real", terminal_path=terminal_path, atr_period=atr_period)
    raw_signal = str(signal_payload.get("signal") or "wait").lower()
    signal_scoring = _signal_strength(signal_payload, state)
    signal = raw_signal if raw_signal in ("buy", "sell") else signal_scoring.get("direction", "wait")
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
        signal = "wait"

    atr_value = _resolve_atr_value(signal_payload)

    if signal == "sell" and not bool(state.get("auto_trade_allow_sell", True)):
        _diag_event("skip", "sell_disabled", symbol=symbol, signal=signal)
        signal = "wait"

    open_rows = list_open_trades()
    _cleanup_runtime_for_open_trades(open_rows)
    max_open_trades = max(1, _coerce_int(state.get("max_open_trades", 1), 1))

    if len(open_rows) < max_open_trades and signal in ("buy", "sell"):
        broker = auto_open_broker
        if not broker:
            _diag_open_attempt("error", reason="no_broker", symbol=symbol, signal=signal)
            _diag_event("skip", "no_broker_for_open", symbol=symbol, signal=signal)
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
            return

        manual_lot = _coerce_float(state.get("lot"), 0.01)
        sl_for_risk = state.get("sl_value")
        if state.get("auto_analytic_tpsl", False):
            sl_for_risk = round(1 * manual_lot, 2)
        if bool(state.get("auto_trade_use_atr_tpsl", True)) and atr_value and atr_value > 0:
            sl_for_risk = atr_value * max(0.2, min(10.0, _coerce_float(state.get("auto_trade_atr_sl_mult"), 1.5)))
        lot_to_open = _risk_based_lot(state, constraints, metrics, manual_lot, sl_for_risk)

        if constraints.get("can_open_order") and constraints.get("volume_step"):
            lot_to_open = normalize_lot_with_constraints(lot_to_open, constraints)

        if lot_to_open <= 0:
            _diag_open_attempt("error", reason="lot_to_open_zero", broker_name=broker.get("name"), symbol=symbol, signal=signal)
            _diag_event("skip", "lot_to_open_zero", symbol=symbol, signal=signal)
            return

        if not _passes_margin_guards(state, metrics, lot_to_open):
            _diag_open_attempt("error", reason="margin_guard_blocked", broker_name=broker.get("name"), symbol=symbol, signal=signal)
            _diag_event("skip", "margin_guard_blocked", symbol=symbol, signal=signal)
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
        try:
            result = adapter.open_trade(symbol, lot_to_open, signal)
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
            raise
        order = result.get("order", {})
        now = int(time.time())
        trade_id = str(uuid.uuid4())

        tp_value, sl_value = _resolve_initial_tpsl(state, lot_to_open, atr_value)

        create_trade_open_record(
            {
                "trade_id": trade_id,
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

    if len(open_rows) >= max_open_trades and signal in ("buy", "sell"):
        _diag_event("skip", "max_open_trades_reached", symbol=symbol, signal=signal)
    elif signal == "wait":
        _diag_event(
            "skip",
            "no_actionable_signal",
            symbol=symbol,
            signal=signal,
            signal_score=_coerce_float(signal_scoring.get("score"), 0.0),
        )

    for t in open_rows:
        broker = get_broker(t.get("broker_id")) if t.get("broker_id") else get_default_broker()
        if not broker:
            continue
        adapter, method = get_broker_adapter(broker, t.get("execution_mode"))
        if method == "mouse":
            continue

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
        direction = str(t.get("type", "")).lower()
        trade_runtime = _get_trade_runtime(t, direction, atr_value)
        ticket = int(t.get("ticket") or 0)

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
        if tp not in (None, 0):
            tp = float(tp)
            if direction == "buy" and last_price >= entry + tp:
                should_close = True
            if direction == "sell" and last_price <= entry - tp:
                should_close = True

        if (not should_close) and sl is not None:
            sl = float(sl)
            if direction == "buy" and last_price <= entry - sl:
                should_close = True
            if direction == "sell" and last_price >= entry + sl:
                should_close = True

        if not should_close and signal in ("buy", "sell") and signal != direction:
            should_close = True

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
                reason="auto_close",
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
