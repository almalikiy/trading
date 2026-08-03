import threading
import time
import uuid

from .db import (
    close_trade_record,
    create_trade_open_record,
    get_account_state,
    get_broker,
    get_default_broker,
    list_brokers,
    list_open_trades,
    resolve_feed_broker,
    save_account_state,
)
from .logic import analyze_symbol, fetch_ohlcv
from .terminal_adapters import (
    ensure_terminal_running,
    get_broker_adapter,
    get_broker_symbol_constraints,
    normalize_lot_with_constraints,
    probe_broker_order_status,
)


_loop_started = False


def _get_feed_broker(state):
    broker = resolve_feed_broker(state=state, require_terminal_path=True)
    if broker:
        return broker
    return resolve_feed_broker(state=state, require_terminal_path=False)


def _latest_close(symbol, terminal_path):
    try:
        df = fetch_ohlcv(symbol, "M1", bars=2, terminal_path=terminal_path)
        return float(df.iloc[-1]["close"])
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


def _run_auto_trade_cycle():
    state = get_account_state()
    feed_broker = _get_feed_broker(state)
    symbol = "XAUUSD"
    if feed_broker and feed_broker.get("default_symbol"):
        symbol = str(feed_broker.get("default_symbol")).strip() or "XAUUSD"
    elif state.get("auto_trade_symbol"):
        symbol = str(state.get("auto_trade_symbol")).strip() or "XAUUSD"
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
        return
    if not state.get("enable_real_trade", False):
        return

    terminal_path = feed_broker.get("terminal_path") if feed_broker else None
    signal_payload = analyze_symbol(symbol, mode="real", terminal_path=terminal_path)
    signal = signal_payload.get("signal")

    open_rows = list_open_trades()
    if not open_rows and signal in ("buy", "sell"):
        broker = auto_open_broker
        if not broker:
            return
        broker_status = probe_broker_order_status(broker, symbol=symbol, auto_start=True)
        if not broker_status.get("can_open_order"):
            return
        lot_to_open = float(state.get("lot", 0.01))
        constraints = get_broker_symbol_constraints(broker, symbol=symbol, auto_start=False)
        if constraints.get("can_open_order") and constraints.get("volume_step"):
            lot_to_open = normalize_lot_with_constraints(lot_to_open, constraints)
            if abs(lot_to_open - float(state.get("lot", 0.01))) > 1e-9:
                state["lot"] = lot_to_open
                save_account_state(state)
        adapter, method = get_broker_adapter(broker, broker.get("execution_mode"))
        result = adapter.open_trade(symbol, lot_to_open, signal)
        order = result.get("order", {})
        now = int(time.time())
        trade_id = str(uuid.uuid4())

        tp_value = state.get("tp_value", 0.5)
        sl_value = state.get("sl_value", None)
        if state.get("auto_analytic_tpsl", False):
            tp_value = round(2 * float(state.get("lot", 0.01)), 2)
            sl_value = round(1 * float(state.get("lot", 0.01)), 2)

        create_trade_open_record(
            {
                "trade_id": trade_id,
                "type": signal.upper(),
                "symbol": symbol,
                "lot": lot_to_open,
                "ticket": order.get("ticket"),
                "entry": order.get("price"),
                "entryTime": now,
                "reason": "auto_open",
                "tpValue": tp_value,
                "slValue": sl_value,
                "broker_id": broker.get("id"),
                "broker_name": broker.get("name"),
                "platform": broker.get("platform"),
                "execution_mode": method,
                "terminal_path": broker.get("terminal_path"),
            }
        )
        return

    if len(open_rows) == 1:
        t = open_rows[0]
        broker = get_broker(t.get("broker_id")) if t.get("broker_id") else get_default_broker()
        if not broker:
            return
        adapter, method = get_broker_adapter(broker, t.get("execution_mode"))
        if method == "mouse":
            return

        last_price = _latest_close(t.get("symbol") or symbol, broker.get("terminal_path"))
        if last_price is None:
            return

        entry = t.get("entry")
        if entry is None:
            return
        entry = float(entry)
        tp = t.get("tpValue")
        sl = t.get("slValue")
        direction = str(t.get("type", "")).lower()

        should_close = False
        if tp not in (None, 0):
            tp = float(tp)
            if direction == "buy" and last_price >= entry + tp:
                should_close = True
            if direction == "sell" and last_price <= entry - tp:
                should_close = True

        if (not should_close) and sl not in (None, 0):
            sl = float(sl)
            if direction == "buy" and last_price <= entry - sl:
                should_close = True
            if direction == "sell" and last_price >= entry + sl:
                should_close = True

        if not should_close:
            return

        ticket = int(t.get("ticket") or 0)
        if ticket <= 0:
            return
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


def _auto_trade_loop():
    while True:
        try:
            _run_auto_trade_cycle()
        except Exception:
            pass
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
