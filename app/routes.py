from fastapi import APIRouter, Request, Query, Body
from .db import get_account_state, save_account_state, insert_trade, get_trade_history, get_broker, get_default_broker, get_open_trades_count, list_open_trades, close_trade_record, resolve_feed_broker, update_open_trade_tpsl, apply_auto_trade_profile_to_state, save_auto_trade_profile, has_auto_trade_profile
router = APIRouter()
from .logic import log_mt5_error
from datetime import datetime
import subprocess
import os
import time
import threading
from pydantic import BaseModel
from .broker_routes import TradeOpenRequest, open_trade_v2
from .terminal_adapters import (
    get_broker_adapter,
    get_broker_account_metrics,
    probe_broker_order_status,
    get_broker_symbol_constraints,
    normalize_lot_with_constraints,
    sync_all_terminal_trade_state,
)
from .terminal_adapters import ensure_terminal_running

# === Analytic TP/SL Logic ===

# Endpoint: Get analytic TP/SL state
@router.get("/account/state")
def get_account_state_route():
    base_state = get_account_state()
    state, broker, _, account_id, _ = _apply_profile_for_active_account(base_state)
    synced_symbol = _resolve_auto_trade_symbol_for_state(state)
    state["auto_trade_symbol"] = synced_symbol
    state["auto_trade_symbol_scope"] = "profile_or_broker_default"
    state["auto_trade_profile_broker_id"] = (broker or {}).get("id")
    state["auto_trade_profile_account_id"] = account_id
    state["auto_trade_profile_scope"] = "account" if (broker and account_id is not None and has_auto_trade_profile(broker.get("id"), account_id)) else "global"
    return state

# Endpoint: Set analytic TP/SL value
class AnalyticTPSLRequest(BaseModel):
    tp_value: float
    sl_value: float | None = None


class TradeTPSLUpdateRequest(BaseModel):
    trade_id: str
    tp_value: float | None = None
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

@router.post("/account/set_analytic_tpsl")
def set_analytic_tpsl(request: AnalyticTPSLRequest):
    try:
        state = get_account_state()
        state["tp_value"] = request.tp_value
        state["sl_value"] = request.sl_value
        save_account_state(state)
        return {"status": "ok", "tp_value": request.tp_value, "sl_value": request.sl_value}
    except Exception as e:
        import traceback
        print("Error in set_analytic_tpsl:", traceback.format_exc())
        return {"status": "error", "detail": str(e)}
    
class AutoTPSLRequest(BaseModel):
    enabled: bool

# Endpoint: Toggle auto analytic TP/SL
@router.post("/account/set_auto_analytic_tpsl")
def set_auto_analytic_tpsl(request: AutoTPSLRequest):
    try:
        state = get_account_state()
        state["auto_analytic_tpsl"] = request.enabled
        save_account_state(state)
        return {"status": "ok", "auto_analytic_tpsl": request.enabled}
    except Exception as e:
        import traceback
        print("Error in set_auto_analytic_tpsl:", traceback.format_exc())
        return {"status": "error", "detail": str(e)}        


# === Trading Order Method ===
# Endpoint /trade/open kini mendukung parameter order_method: 'pyautogui' (default) atau 'mt5'.
# Jika order_method tidak diberikan, backend akan menjalankan order via PyAutoGUI (otomasi desktop, tanpa jejak EA/robot di MT5).
# Untuk order via MT5 API, kirim order_method='mt5'.


# Endpoint: Close trade by index (PyAutoGUI)
@router.post("/trade/close_by_index")
def close_trade_by_index(index: int = Body(...), window_hint: str = Body('FinexBisnisSolusi')):
    """
    Close trade at row index (0-based) in MT5 trade panel using PyAutoGUI.
    Example: index=0 (TRADE #1), index=1 (TRADE #2)
    SELL: X:149 Y:256
    BUY : X:430 Y:256
    TRADE #1: x:438 Y:1409
    TRADE #2: x:438 Y:1429
    TRADE CLOSE #1: x:550 Y:859
    TRADE CLOSE #2: x:550 Y:879
    """
    import subprocess
    # Koordinat baris trade (asumsi jarak antar baris 20px, baris pertama Y=1409)
    base_x = 438
    base_y = 1409
    row_height = 20
    y = base_y + index * row_height
    # Klik kanan pada baris trade ke-index
    proc1 = subprocess.run([
        'python', os.path.join(os.path.dirname(__file__), 'pyautogui_order.py'),
        'rightclick', str(base_x), str(y), window_hint
    ], capture_output=True, text=True)
    if proc1.returncode != 0:
        return {"status": "error", "message": proc1.stderr or proc1.stdout}
    # Klik menu Close (misal: X=550, Y=1460, sesuaikan jika perlu)
    close_x, close_y = 550, y - 550  # Asumsi menu close muncul 50px di bawah baris
    proc2 = subprocess.run([
        'python', os.path.join(os.path.dirname(__file__), 'pyautogui_order.py'),
        'click', str(close_x), str(close_y), window_hint
    ], capture_output=True, text=True)
    if proc2.returncode != 0:
        return {"status": "error", "message": proc2.stderr or proc2.stdout}
    return {"status": "ok", "output": proc1.stdout + proc2.stdout}


# Endpoint: Status koneksi backend ke MT5
@router.get("/mt5/status")
def mt5_status():
    import MetaTrader5 as mt5
    status = mt5.initialize()
    if status:
        mt5.shutdown()
    return {"connected": bool(status)}

# Endpoint: Ambil log error MT5
    

@router.get("/mt5/error_log")
def mt5_error_log():
    from .db import get_mt5_error_log
    return get_mt5_error_log()


def _mt5_error_kind(message: str):
    text = str(message or "")
    if text.startswith("history_deals_get exception"):
        return "history_deals_get_exception"
    if text.startswith("history_deals_get failed"):
        return "history_deals_get_failed"
    if text.startswith("history_deals_get fallback failed"):
        return "history_deals_get_fallback_failed"
    if text.startswith("Terminal sync failed for broker"):
        return "terminal_sync_failed"
    if text.startswith("Auto close failed for trade"):
        return "auto_close_failed"
    if text.startswith("Partial TP failed for trade"):
        return "partial_tp_failed"
    if text.startswith("close_trade context:"):
        return "close_trade_context"
    return "other"


@router.get("/mt5/error_log_summary")
def mt5_error_log_summary(window_minutes: int = 180, limit: int = 5000):
    from .db import get_mt5_error_log

    safe_window = max(1, min(int(window_minutes or 180), 24 * 60))
    safe_limit = max(100, min(int(limit or 5000), 50000))
    since = int(time.time()) - safe_window * 60

    rows = [row for row in get_mt5_error_log(limit=safe_limit) if int(row.get("timestamp") or 0) >= since]

    by_broker = {}
    by_kind = {}
    for row in rows:
        broker = row.get("broker_name") or "-"
        kind = _mt5_error_kind(row.get("message"))
        by_broker[broker] = by_broker.get(broker, 0) + 1
        by_kind[kind] = by_kind.get(kind, 0) + 1

    return {
        "status": "ok",
        "window_minutes": safe_window,
        "total": len(rows),
        "by_broker": sorted(
            [{"broker": k, "count": v} for k, v in by_broker.items()],
            key=lambda x: x["count"],
            reverse=True,
        ),
        "by_kind": sorted(
            [{"kind": k, "count": v} for k, v in by_kind.items()],
            key=lambda x: x["count"],
            reverse=True,
        ),
    }


@router.post("/mt5/error_log/clear")
def mt5_error_log_clear():
    from .db import clear_mt5_error_log

    clear_mt5_error_log()
    return {"status": "ok"}


from .logic import analyze_symbol, get_signal_snapshot, get_ohlcv_snapshot
from .auto_trader import is_auto_trader_thread_started, get_auto_trader_runtime_status

_SYNC_LOCK = threading.Lock()
_LAST_TERMINAL_SYNC_TS = 0.0
_SYNC_MIN_INTERVAL_SEC = 15.0

def save_trade_history(trade):
    insert_trade(trade)

def load_trade_history():
    return get_trade_history()


def _resolve_auto_trade_symbol_for_state(state):
    broker = resolve_feed_broker(state=state, require_terminal_path=False)
    if not broker:
        broker = get_default_broker()
    symbol = (broker or {}).get("default_symbol") or state.get("auto_trade_symbol") or "XAUUSD"
    return str(symbol).strip().upper() or "XAUUSD"


def _resolve_auto_trade_broker_for_state(state):
    broker = resolve_feed_broker(state=state, require_terminal_path=False)
    if broker:
        return broker
    return get_default_broker()


def _resolve_active_profile_context(state):
    broker = _resolve_auto_trade_broker_for_state(state)
    symbol = _resolve_auto_trade_symbol_for_state(state)
    account_id = None
    metrics = {}
    if broker:
        metrics = get_broker_account_metrics(broker, symbol=symbol, auto_start=False) or {}
        account_id = metrics.get("account_id")
    return broker, symbol, account_id, metrics


def _apply_profile_for_active_account(state):
    broker, symbol, account_id, metrics = _resolve_active_profile_context(state)
    if broker and account_id is not None:
        effective = apply_auto_trade_profile_to_state(state, broker.get("id"), account_id)
    else:
        effective = dict(state)
    return effective, broker, symbol, account_id, metrics


def _sync_terminal_trade_views():
    global _LAST_TERMINAL_SYNC_TS
    now = time.time()
    with _SYNC_LOCK:
        if now - _LAST_TERMINAL_SYNC_TS < _SYNC_MIN_INTERVAL_SEC:
            return
        _LAST_TERMINAL_SYNC_TS = now

    state = get_account_state()
    history_days = None if state.get("trade_history_sync_all") else int(state.get("trade_history_sync_days") or 90)
    sync_all_terminal_trade_state(history_days=history_days)


def _decorate_open_positions_with_strategy_state(open_rows, history_rows, account_state):
    history_rows = history_rows or []
    trailing_enabled = bool(account_state.get("auto_trade_trailing_enabled", True))
    trailing_mode = str(account_state.get("auto_trade_trailing_mode") or "stateful_hl")

    decorated = []
    for trade in open_rows:
        trade_id = str(trade.get("trade_id") or "")
        partial_stage1_done = False
        partial_stage2_done = False
        for row in history_rows:
            reason = str(row.get("reason") or "")
            history_trade_id = str(row.get("trade_id") or "")
            if not history_trade_id.startswith(f"{trade_id}:partial:"):
                continue
            if "partial_take_profit_stage1" in reason:
                partial_stage1_done = True
            if "partial_take_profit_stage2" in reason:
                partial_stage2_done = True

        break_even_locked = False
        try:
            sl_val = trade.get("slValue")
            entry_val = trade.get("entry")
            side = str(trade.get("type") or "").upper()
            if sl_val is not None and entry_val is not None:
                sl_num = float(sl_val)
                entry_num = float(entry_val)
                if side == "BUY":
                    break_even_locked = sl_num >= entry_num
                elif side == "SELL":
                    break_even_locked = sl_num <= entry_num
        except Exception:
            break_even_locked = False

        badges = []
        if partial_stage1_done:
            badges.append("PTP S1")
        if partial_stage2_done:
            badges.append("PTP S2")
        if break_even_locked:
            badges.append("BE Lock")
        if trailing_enabled:
            badges.append("Trail HL" if trailing_mode == "stateful_hl" else "Trail ATR")

        row = dict(trade)
        row["strategy_state"] = {
            "partial_stage1_done": partial_stage1_done,
            "partial_stage2_done": partial_stage2_done,
            "break_even_locked": break_even_locked,
            "trailing_enabled": trailing_enabled,
            "trailing_mode": trailing_mode,
        }
        row["strategy_badges"] = badges
        decorated.append(row)
    return decorated


@router.get("/account/auto_trade_health")
def get_auto_trade_health():
    base_state = get_account_state()
    state, active_broker, _, active_account_id, _ = _apply_profile_for_active_account(base_state)
    checks = []
    blockers = []

    thread_started = bool(is_auto_trader_thread_started())
    checks.append({"key": "auto_trader_thread", "ok": thread_started, "value": thread_started, "message": "Auto-trader worker thread"})
    if not thread_started:
        blockers.append("Worker thread auto-trader belum aktif.")

    auto_trade_enabled = bool(state.get("auto_trade_enabled", False))
    checks.append({"key": "auto_trade_enabled", "ok": auto_trade_enabled, "value": auto_trade_enabled, "message": "Auto trade backend enabled"})
    if not auto_trade_enabled:
        blockers.append("Toggle Auto Trade Backend masih OFF.")

    real_trade_enabled = bool(state.get("enable_real_trade", False))
    checks.append({"key": "enable_real_trade", "ok": real_trade_enabled, "value": real_trade_enabled, "message": "Real trade MT5 enabled"})
    if not real_trade_enabled:
        blockers.append("Enable Trading on MT5 masih OFF.")

    feed_broker = active_broker or resolve_feed_broker(state=state, require_terminal_path=False) or get_default_broker()
    has_broker = feed_broker is not None
    checks.append({"key": "feed_broker", "ok": has_broker, "value": (feed_broker or {}).get("name"), "message": "Data feed broker tersedia"})
    if not has_broker:
        blockers.append("Tidak ada broker aktif/default untuk feed dan eksekusi.")

    symbol = str((feed_broker or {}).get("default_symbol") or state.get("auto_trade_symbol") or "XAUUSD").strip().upper() or "XAUUSD"
    checks.append({"key": "auto_trade_symbol", "ok": True, "value": symbol, "message": "Symbol auto trade"})

    if has_broker:
        broker_status = probe_broker_order_status(feed_broker, symbol=symbol, auto_start=False)
        broker_ready = bool(broker_status.get("can_open_order"))
        checks.append({"key": "broker_ready", "ok": broker_ready, "value": broker_status.get("reason"), "message": "Kesiapan broker open order"})
        if not broker_ready:
            blockers.append(f"Broker belum ready untuk open order: {broker_status.get('reason')}")

        metrics = get_broker_account_metrics(feed_broker, symbol=symbol, auto_start=False)
        checks.append({"key": "account_metrics_ready", "ok": bool(metrics.get("can_trade")), "value": metrics.get("reason"), "message": "Metrik akun/leverage/margin"})
        if not metrics.get("can_trade"):
            blockers.append(f"Metrik akun belum siap: {metrics.get('reason')}")

        max_spread_points = int(state.get("auto_trade_max_spread_points", 120) or 120)
        spread_points = metrics.get("spread_points")
        spread_ok = True
        if isinstance(spread_points, int) and max_spread_points > 0:
            spread_ok = spread_points <= max_spread_points
        checks.append(
            {
                "key": "spread_guard",
                "ok": spread_ok,
                "value": f"{spread_points}/{max_spread_points}",
                "message": "Spread saat ini vs max spread points",
            }
        )
        if not spread_ok:
            blockers.append(f"Spread terlalu tinggi: {spread_points} > {max_spread_points}.")

    start_hour = int(state.get("auto_trade_session_start_hour", 0) or 0)
    end_hour = int(state.get("auto_trade_session_end_hour", 24) or 24)
    hour_now = datetime.now().hour
    if start_hour == end_hour:
        in_session = True
    elif start_hour < end_hour:
        in_session = start_hour <= hour_now < end_hour
    else:
        in_session = hour_now >= start_hour or hour_now < end_hour
    checks.append({"key": "session_window", "ok": in_session, "value": f"{start_hour}-{end_hour}", "message": "Session trading saat ini"})
    if not in_session:
        blockers.append("Di luar jam session trading yang dikonfigurasi.")

    open_rows = list_open_trades()
    mouse_open_rows = [row for row in open_rows if str(row.get("execution_mode") or "").lower() == "mouse"]
    checks.append({"key": "open_positions_mouse_mode", "ok": len(mouse_open_rows) == 0, "value": len(mouse_open_rows), "message": "Open trade mode mouse"})
    if mouse_open_rows:
        blockers.append("Ada open trade dengan execution mode mouse; auto close/partial/trailing backend tidak bisa mengeksekusi posisi ini.")

    atr_period = int(state.get("auto_trade_atr_period", 14) or 14)
    terminal_path = (feed_broker or {}).get("terminal_path") if feed_broker else None
    signal_payload = analyze_symbol(symbol, mode="real", terminal_path=terminal_path, atr_period=atr_period)
    signal_ok = "error" not in signal_payload
    checks.append({"key": "signal_pipeline", "ok": signal_ok, "value": signal_payload.get("signal") if signal_ok else signal_payload.get("details"), "message": "Pipeline sinyal real-time"})
    if not signal_ok:
        blockers.append("Pipeline sinyal gagal mengambil data timeframe dari terminal.")

    return {
        "status": "ok",
        "active": len(blockers) == 0,
        "blockers": blockers,
        "checks": checks,
        "symbol": symbol,
        "feed_broker": feed_broker,
        "profile": {
            "broker_id": (feed_broker or {}).get("id"),
            "account_id": active_account_id,
            "scope": "account" if (feed_broker and active_account_id is not None and has_auto_trade_profile(feed_broker.get("id"), active_account_id)) else "global",
        },
    }


@router.get("/account/auto_trade_runtime")
def get_auto_trade_runtime():
    return {
        "status": "ok",
        "runtime": get_auto_trader_runtime_status(),
    }

# === Real Trade Execution Endpoints ===

@router.post("/trade/open")
def open_trade(symbol: str = Body(...), lot: float = Body(0.01), trade_type: str = Body(...), signal_time: float = Body(None), order_method: str = Body('pyautogui')):
    """
    Open a real trade on MT5. trade_type: 'buy' or 'sell'.
    Only executes if enable_real_trade is True and signal is not expired.
    """
    import time

    mode = str(order_method or "pyautogui").lower()
    mapped_method = "mouse" if mode in ("pyautogui", "mouse") else "direct"
    result = open_trade_v2(
        TradeOpenRequest(
            symbol=symbol,
            lot=lot,
            trade_type=trade_type,
            signal_time=signal_time,
            broker_id=None,
            order_method=mapped_method,
        )
    )
    if result.get("status") != "ok":
        return result

    order = (result.get("result") or {}).get("order", {})
    user_id = "default"
    row = user_open_trade.get(user_id, {
        "balance": 1000,
        "openTrade": False,
        "entryPrice": None,
        "entryTime": None,
        "direction": None,
        "pnl": 0,
        "lastSignal": "wait",
        "tradeHistory": []
    })
    row["openTrade"] = True
    row["entryPrice"] = order.get("price")
    row["entryTime"] = int(time.time())
    row["direction"] = trade_type.lower()
    user_open_trade[user_id] = row
    return result

# Endpoint: Force close all open trades (for emergency/manual fix)
@router.post("/trade/force_close")
def force_close_all_trades():
    """
    Force close all open trades on MT5. Use if trade stuck open due to backend error.
    """
    import time
    state = get_account_state()
    closed = []
    errors = []

    if state.get("enable_real_trade", False):
        for t in list_open_trades():
            try:
                broker = get_broker(t.get("broker_id")) if t.get("broker_id") else get_default_broker()
                if not broker:
                    errors.append({"trade_id": t.get("trade_id"), "error": "Broker not found"})
                    continue
                adapter, method = get_broker_adapter(broker, t.get("execution_mode"))
                if method == "mouse":
                    errors.append({"trade_id": t.get("trade_id"), "error": "Force close tidak mendukung mode mouse."})
                    continue
                ticket = int(t.get("ticket") or 0)
                if ticket <= 0:
                    errors.append({"trade_id": t.get("trade_id"), "error": "Ticket tidak valid"})
                    continue
                result = adapter.close_trade(t.get("symbol") or "XAUUSD", float(t.get("lot") or 0.01), ticket)
                order = result.get("order", {})
                close_trade_record(
                    t.get("trade_id"),
                    exit_price=order.get("price"),
                    profit=order.get("profit"),
                    exit_time=int(time.time()),
                    ticket=ticket,
                    reason="force_close",
                )
                closed.append({"trade_id": t.get("trade_id"), "ticket": ticket, "result": result})
            except Exception as e:
                errors.append({"trade_id": t.get("trade_id"), "error": str(e)})
        
    # Clear all user open trades (so frontend sees no active trade)
    for user_id in list(user_open_trade.keys()):
        user_open_trade[user_id]["openTrade"] = False
        user_open_trade[user_id]["entryPrice"] = None
        user_open_trade[user_id]["entryTime"] = None
        user_open_trade[user_id]["direction"] = None
        user_open_trade[user_id]["pnl"] = 0
        user_open_trade[user_id]["lastSignal"] = "wait"
        # Optionally, update tradeHistory if needed
    return {"status": "ok", "closed": closed, "errors": errors}

@router.post("/trade/close")
def close_trade(symbol: str = Body(...), lot: float = Body(0.01), ticket: int = Body(...)):
    """
    Close a real trade on MT5 by ticket.
    """
    import time
    try:
        target = next((t for t in list_open_trades() if int(t.get("ticket") or -1) == int(ticket)), None)
        if not target:
            return {"status": "error", "message": "Open trade tidak ditemukan untuk ticket ini."}

        broker = get_broker(target.get("broker_id")) if target.get("broker_id") else get_default_broker()
        if not broker:
            return {"status": "error", "message": "Broker not found"}

        adapter, method = get_broker_adapter(broker, target.get("execution_mode"))
        if method == "mouse":
            return {"status": "error", "message": "Close by ticket hanya tersedia untuk mode direct/API."}

        result = adapter.close_trade(symbol or target.get("symbol") or "XAUUSD", lot or float(target.get("lot") or 0.01), ticket)
        print("DEBUG ini mau assign order binding")
        order = result.get("order", {})
        exit_price = float(order.get("price") or 0) # safe for SQLite
        profit = float(order.get("profit") or 0) # safe for SQLite
        close_trade_record(
            target.get("trade_id"),
            exit_price=exit_price,
            profit=profit,
            exit_time=int(time.time()),
            ticket=ticket,
            reason="close_legacy",
        )
        print("DEBUG close_trade_record params:", {
            "trade_id": target.get("trade_id"),
            "exit_price": exit_price,
            "profit": profit,
            "ticket": ticket,
        })

        user_id = "default"
        if user_id in user_open_trade:
            user_open_trade[user_id]["openTrade"] = False
            user_open_trade[user_id]["entryPrice"] = None
            user_open_trade[user_id]["entryTime"] = None
            user_open_trade[user_id]["direction"] = None
            user_open_trade[user_id]["pnl"] = 0
            user_open_trade[user_id]["lastSignal"] = "wait"
        return {"status": "ok", "result": result, "trade_id": target.get("trade_id")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# Endpoint to set enable_real_trade
@router.post("/account/set_enable_real_trade")
def set_enable_real_trade(enabled: bool = Body(...)):
    """
    Set flag enable_real_trade in account_state.
    Controls whether real trades are executed via MT5 (pyautogui/API).
    """
    # Ambil state saat ini dari SQLite
    state = get_account_state()
    # Update nilai enable_real_trade
    state["enable_real_trade"] = bool(enabled)
    # Simpan kembali ke SQLite
    save_account_state(state)
    # Return konfirmasi
    return {"status": "ok", "enable_real_trade": state["enable_real_trade"]}


@router.post("/account/set_auto_trade_enabled")
def set_auto_trade_enabled(enabled: bool = Body(...)):
    state = get_account_state()
    state["auto_trade_enabled"] = bool(enabled)
    save_account_state(state)
    return {"status": "ok", "auto_trade_enabled": state["auto_trade_enabled"]}


@router.post("/account/set_keep_terminal_alive")
def set_keep_terminal_alive(enabled: bool = Body(...)):
    state = get_account_state()
    state["keep_terminal_alive"] = bool(enabled)
    save_account_state(state)
    return {"status": "ok", "keep_terminal_alive": state["keep_terminal_alive"]}


@router.post("/account/set_data_feed_broker")
def set_data_feed_broker(broker_id: int = Body(...)):
    broker = get_broker(broker_id)
    if not broker:
        return {"status": "error", "message": "Broker not found"}
    state = get_account_state()
    state["data_feed_broker_id"] = broker_id
    state["auto_trade_symbol"] = str(broker.get("default_symbol") or "XAUUSD").strip().upper() or "XAUUSD"
    save_account_state(state)
    return {
        "status": "ok",
        "data_feed_broker_id": broker_id,
        "auto_trade_symbol": state["auto_trade_symbol"],
        "auto_trade_symbol_scope": "broker_default",
    }


@router.post("/account/set_trade_history_sync")
def set_trade_history_sync(payload: TradeHistorySyncSettingsRequest):
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
        "trade_history_sync_all": state["trade_history_sync_all"],
        "trade_history_sync_days": state["trade_history_sync_days"],
    }


@router.post("/account/set_auto_trade_config")
def set_auto_trade_config(payload: AutoTradeConfigRequest):
    base_state = get_account_state()
    state, broker_ctx, _, account_id_ctx, _ = _apply_profile_for_active_account(base_state)

    # Auto-trade symbol selalu mengikuti default symbol broker aktif.
    if payload.symbol is not None:
        pass

    if payload.interval_sec is not None:
        interval = float(payload.interval_sec)
        if interval < 1 or interval > 60:
            return {"status": "error", "message": "Interval auto-trade harus antara 1 sampai 60 detik."}
        state["auto_trade_interval_sec"] = interval

    if payload.auto_analytic_tpsl is not None:
        state["auto_analytic_tpsl"] = bool(payload.auto_analytic_tpsl)

    if payload.tp_value is not None:
        state["tp_value"] = float(payload.tp_value)

    if payload.sl_value is not None:
        state["sl_value"] = float(payload.sl_value)

    if payload.lot is not None:
        lot = float(payload.lot)
        if lot <= 0:
            return {"status": "error", "message": "Lot harus lebih besar dari 0."}

        state_preview = dict(state)
        broker_for_constraints = _resolve_auto_trade_broker_for_state(state_preview)
        symbol_for_constraints = _resolve_auto_trade_symbol_for_state(state_preview)
        constraints = get_broker_symbol_constraints(broker_for_constraints, symbol=symbol_for_constraints, auto_start=False)
        if constraints.get("can_open_order") and constraints.get("volume_step"):
            lot = normalize_lot_with_constraints(lot, constraints)
        state["lot"] = lot

    if payload.max_open_trades is not None:
        max_open = int(payload.max_open_trades)
        if max_open <= 0:
            return {"status": "error", "message": "Max open trades harus lebih besar dari 0."}
        state["max_open_trades"] = max_open

    if payload.risk_mode is not None:
        risk_mode = str(payload.risk_mode).strip().lower()
        if risk_mode not in ("fixed_lot", "risk_percent"):
            return {"status": "error", "message": "Risk mode harus fixed_lot atau risk_percent."}
        state["auto_trade_risk_mode"] = risk_mode

    if payload.risk_percent is not None:
        risk_percent = float(payload.risk_percent)
        if risk_percent < 0.1 or risk_percent > 10:
            return {"status": "error", "message": "Risk percent harus antara 0.1 sampai 10."}
        state["auto_trade_risk_percent"] = risk_percent

    if payload.use_account_balance is not None:
        state["auto_trade_use_account_balance"] = bool(payload.use_account_balance)

    if payload.use_available_margin is not None:
        state["auto_trade_use_available_margin"] = bool(payload.use_available_margin)

    if payload.min_free_margin_pct is not None:
        min_free_margin_pct = float(payload.min_free_margin_pct)
        if min_free_margin_pct < 0 or min_free_margin_pct > 95:
            return {"status": "error", "message": "Min free margin % harus antara 0 sampai 95."}
        state["auto_trade_min_free_margin_pct"] = min_free_margin_pct

    if payload.max_margin_usage_pct is not None:
        max_margin_usage_pct = float(payload.max_margin_usage_pct)
        if max_margin_usage_pct <= 0 or max_margin_usage_pct > 100:
            return {"status": "error", "message": "Max margin usage % harus antara >0 sampai 100."}
        state["auto_trade_max_margin_usage_pct"] = max_margin_usage_pct

    if payload.max_spread_points is not None:
        max_spread_points = int(payload.max_spread_points)
        if max_spread_points < 0:
            return {"status": "error", "message": "Max spread points tidak boleh negatif."}
        state["auto_trade_max_spread_points"] = max_spread_points

    if payload.min_signal_score is not None:
        min_signal_score = float(payload.min_signal_score)
        if min_signal_score < 0 or min_signal_score > 0.95:
            return {"status": "error", "message": "Min signal score harus antara 0 sampai 0.95."}
        state["auto_trade_min_signal_score"] = min_signal_score

    if payload.allow_sell is not None:
        state["auto_trade_allow_sell"] = bool(payload.allow_sell)

    if payload.cooldown_sec is not None:
        cooldown_sec = int(payload.cooldown_sec)
        if cooldown_sec < 0 or cooldown_sec > 3600:
            return {"status": "error", "message": "Cooldown harus antara 0 sampai 3600 detik."}
        state["auto_trade_cooldown_sec"] = cooldown_sec

    if payload.session_start_hour is not None:
        session_start_hour = int(payload.session_start_hour)
        if session_start_hour < 0 or session_start_hour > 23:
            return {"status": "error", "message": "Session start hour harus 0 sampai 23."}
        state["auto_trade_session_start_hour"] = session_start_hour

    if payload.session_end_hour is not None:
        session_end_hour = int(payload.session_end_hour)
        if session_end_hour < 0 or session_end_hour > 24:
            return {"status": "error", "message": "Session end hour harus 0 sampai 24."}
        state["auto_trade_session_end_hour"] = session_end_hour

    if payload.use_atr_tpsl is not None:
        state["auto_trade_use_atr_tpsl"] = bool(payload.use_atr_tpsl)

    if payload.atr_period is not None:
        atr_period = int(payload.atr_period)
        if atr_period < 5 or atr_period > 100:
            return {"status": "error", "message": "ATR period harus antara 5 sampai 100."}
        state["auto_trade_atr_period"] = atr_period

    if payload.atr_sl_mult is not None:
        atr_sl_mult = float(payload.atr_sl_mult)
        if atr_sl_mult < 0.2 or atr_sl_mult > 10:
            return {"status": "error", "message": "ATR SL multiplier harus antara 0.2 sampai 10."}
        state["auto_trade_atr_sl_mult"] = atr_sl_mult

    if payload.atr_tp_mult is not None:
        atr_tp_mult = float(payload.atr_tp_mult)
        if atr_tp_mult < 0.2 or atr_tp_mult > 20:
            return {"status": "error", "message": "ATR TP multiplier harus antara 0.2 sampai 20."}
        state["auto_trade_atr_tp_mult"] = atr_tp_mult

    if payload.trailing_enabled is not None:
        state["auto_trade_trailing_enabled"] = bool(payload.trailing_enabled)

    if payload.trailing_activation_rr is not None:
        trailing_activation_rr = float(payload.trailing_activation_rr)
        if trailing_activation_rr < 0.2 or trailing_activation_rr > 5:
            return {"status": "error", "message": "Trailing activation RR harus antara 0.2 sampai 5."}
        state["auto_trade_trailing_activation_rr"] = trailing_activation_rr

    if payload.trailing_atr_mult is not None:
        trailing_atr_mult = float(payload.trailing_atr_mult)
        if trailing_atr_mult < 0.2 or trailing_atr_mult > 10:
            return {"status": "error", "message": "Trailing ATR multiplier harus antara 0.2 sampai 10."}
        state["auto_trade_trailing_atr_mult"] = trailing_atr_mult

    if payload.confidence_model is not None:
        confidence_model = str(payload.confidence_model).strip().lower()
        if confidence_model not in ("weighted", "equal"):
            return {"status": "error", "message": "Confidence model harus weighted atau equal."}
        state["auto_trade_confidence_model"] = confidence_model

    if payload.confidence_threshold is not None:
        confidence_threshold = float(payload.confidence_threshold)
        if confidence_threshold < 0 or confidence_threshold > 0.95:
            return {"status": "error", "message": "Confidence threshold harus antara 0 sampai 0.95."}
        state["auto_trade_confidence_threshold"] = confidence_threshold

    if payload.tf_weight_m1 is not None:
        state["auto_trade_tf_weight_m1"] = max(0.0, float(payload.tf_weight_m1))
    if payload.tf_weight_m5 is not None:
        state["auto_trade_tf_weight_m5"] = max(0.0, float(payload.tf_weight_m5))
    if payload.tf_weight_m15 is not None:
        state["auto_trade_tf_weight_m15"] = max(0.0, float(payload.tf_weight_m15))
    if payload.tf_weight_m30 is not None:
        state["auto_trade_tf_weight_m30"] = max(0.0, float(payload.tf_weight_m30))

    if payload.partial_tp_enabled is not None:
        state["auto_trade_partial_tp_enabled"] = bool(payload.partial_tp_enabled)

    if payload.partial_tp_rr1 is not None:
        value = float(payload.partial_tp_rr1)
        if value < 0.2 or value > 10:
            return {"status": "error", "message": "Partial TP RR1 harus antara 0.2 sampai 10."}
        state["auto_trade_partial_tp_rr1"] = value

    if payload.partial_tp_close_pct1 is not None:
        value = float(payload.partial_tp_close_pct1)
        if value < 1 or value > 95:
            return {"status": "error", "message": "Partial TP close %1 harus antara 1 sampai 95."}
        state["auto_trade_partial_tp_close_pct1"] = value

    if payload.partial_tp_rr2 is not None:
        value = float(payload.partial_tp_rr2)
        if value < 0.2 or value > 20:
            return {"status": "error", "message": "Partial TP RR2 harus antara 0.2 sampai 20."}
        state["auto_trade_partial_tp_rr2"] = value

    if payload.partial_tp_close_pct2 is not None:
        value = float(payload.partial_tp_close_pct2)
        if value < 1 or value > 95:
            return {"status": "error", "message": "Partial TP close %2 harus antara 1 sampai 95."}
        state["auto_trade_partial_tp_close_pct2"] = value

    if payload.break_even_enabled is not None:
        state["auto_trade_break_even_enabled"] = bool(payload.break_even_enabled)

    if payload.break_even_rr is not None:
        value = float(payload.break_even_rr)
        if value < 0.2 or value > 10:
            return {"status": "error", "message": "Break-even RR harus antara 0.2 sampai 10."}
        state["auto_trade_break_even_rr"] = value

    if payload.break_even_offset_atr_mult is not None:
        value = float(payload.break_even_offset_atr_mult)
        if value < 0 or value > 2:
            return {"status": "error", "message": "Break-even offset ATR mult harus antara 0 sampai 2."}
        state["auto_trade_break_even_offset_atr_mult"] = value

    if payload.trailing_mode is not None:
        value = str(payload.trailing_mode).strip().lower()
        if value not in ("atr", "stateful_hl"):
            return {"status": "error", "message": "Trailing mode harus atr atau stateful_hl."}
        state["auto_trade_trailing_mode"] = value

    if payload.stateful_trail_buffer_atr_mult is not None:
        value = float(payload.stateful_trail_buffer_atr_mult)
        if value < 0 or value > 5:
            return {"status": "error", "message": "Stateful trail buffer ATR mult harus antara 0 sampai 5."}
        state["auto_trade_stateful_trail_buffer_atr_mult"] = value

    state["auto_trade_symbol"] = _resolve_auto_trade_symbol_for_state(state)

    # Keep global state updated as fallback, and persist profile for active broker/account.
    save_account_state(state)
    if broker_ctx and account_id_ctx is not None:
        save_auto_trade_profile(broker_ctx.get("id"), account_id_ctx, state)

    broker_for_response = _resolve_auto_trade_broker_for_state(state)
    symbol_for_response = _resolve_auto_trade_symbol_for_state(state)
    constraints = get_broker_symbol_constraints(broker_for_response, symbol=symbol_for_response, auto_start=False)
    account_metrics = get_broker_account_metrics(broker_for_response, symbol=symbol_for_response, auto_start=False)
    return {
        "status": "ok",
        "auto_trade_symbol": state.get("auto_trade_symbol"),
        "auto_trade_symbol_scope": "broker_default",
        "auto_trade_interval_sec": state.get("auto_trade_interval_sec"),
        "auto_analytic_tpsl": state.get("auto_analytic_tpsl"),
        "tp_value": state.get("tp_value"),
        "sl_value": state.get("sl_value"),
        "lot": state.get("lot"),
        "max_open_trades": state.get("max_open_trades"),
        "risk_mode": state.get("auto_trade_risk_mode", "fixed_lot"),
        "risk_percent": state.get("auto_trade_risk_percent", 1.0),
        "use_account_balance": bool(state.get("auto_trade_use_account_balance", True)),
        "use_available_margin": bool(state.get("auto_trade_use_available_margin", True)),
        "min_free_margin_pct": state.get("auto_trade_min_free_margin_pct", 30.0),
        "max_margin_usage_pct": state.get("auto_trade_max_margin_usage_pct", 70.0),
        "max_spread_points": state.get("auto_trade_max_spread_points", 120),
        "min_signal_score": state.get("auto_trade_min_signal_score", 0.55),
        "allow_sell": bool(state.get("auto_trade_allow_sell", True)),
        "cooldown_sec": state.get("auto_trade_cooldown_sec", 30),
        "session_start_hour": state.get("auto_trade_session_start_hour", 0),
        "session_end_hour": state.get("auto_trade_session_end_hour", 24),
        "use_atr_tpsl": bool(state.get("auto_trade_use_atr_tpsl", True)),
        "atr_period": state.get("auto_trade_atr_period", 14),
        "atr_sl_mult": state.get("auto_trade_atr_sl_mult", 1.5),
        "atr_tp_mult": state.get("auto_trade_atr_tp_mult", 2.5),
        "trailing_enabled": bool(state.get("auto_trade_trailing_enabled", True)),
        "trailing_activation_rr": state.get("auto_trade_trailing_activation_rr", 1.0),
        "trailing_atr_mult": state.get("auto_trade_trailing_atr_mult", 1.0),
        "confidence_model": state.get("auto_trade_confidence_model", "weighted"),
        "confidence_threshold": state.get("auto_trade_confidence_threshold", 0.6),
        "tf_weight_m1": state.get("auto_trade_tf_weight_m1", 0.35),
        "tf_weight_m5": state.get("auto_trade_tf_weight_m5", 0.30),
        "tf_weight_m15": state.get("auto_trade_tf_weight_m15", 0.20),
        "tf_weight_m30": state.get("auto_trade_tf_weight_m30", 0.15),
        "partial_tp_enabled": bool(state.get("auto_trade_partial_tp_enabled", True)),
        "partial_tp_rr1": state.get("auto_trade_partial_tp_rr1", 1.0),
        "partial_tp_close_pct1": state.get("auto_trade_partial_tp_close_pct1", 40.0),
        "partial_tp_rr2": state.get("auto_trade_partial_tp_rr2", 2.0),
        "partial_tp_close_pct2": state.get("auto_trade_partial_tp_close_pct2", 35.0),
        "break_even_enabled": bool(state.get("auto_trade_break_even_enabled", True)),
        "break_even_rr": state.get("auto_trade_break_even_rr", 1.0),
        "break_even_offset_atr_mult": state.get("auto_trade_break_even_offset_atr_mult", 0.1),
        "trailing_mode": state.get("auto_trade_trailing_mode", "stateful_hl"),
        "stateful_trail_buffer_atr_mult": state.get("auto_trade_stateful_trail_buffer_atr_mult", 0.5),
        "constraints": constraints,
        "account_metrics": account_metrics,
        "profile": {
            "broker_id": (broker_for_response or {}).get("id"),
            "account_id": account_id_ctx,
            "scope": "account" if (broker_for_response and account_id_ctx is not None) else "global",
        },
    }


@router.get("/account/auto_trade_constraints")
def get_auto_trade_constraints():
    base_state = get_account_state()
    state, broker, _, account_id, _ = _apply_profile_for_active_account(base_state)
    symbol = _resolve_auto_trade_symbol_for_state(state)
    constraints = get_broker_symbol_constraints(broker, symbol=symbol, auto_start=False)
    account_metrics = get_broker_account_metrics(broker, symbol=symbol, auto_start=False)

    normalized_lot = float(state.get("lot", 0.01) or 0.01)
    if constraints.get("can_open_order") and constraints.get("volume_step"):
        normalized_lot = normalize_lot_with_constraints(normalized_lot, constraints)

    return {
        "status": "ok",
        "symbol": symbol,
        "broker": broker,
        "constraints": constraints,
        "current_settings": {
            "lot": state.get("lot"),
            "max_open_trades": state.get("max_open_trades"),
            "auto_trade_interval_sec": state.get("auto_trade_interval_sec"),
            "tp_value": state.get("tp_value"),
            "sl_value": state.get("sl_value"),
            "auto_analytic_tpsl": state.get("auto_analytic_tpsl"),
            "risk_mode": state.get("auto_trade_risk_mode", "fixed_lot"),
            "risk_percent": state.get("auto_trade_risk_percent", 1.0),
            "use_account_balance": bool(state.get("auto_trade_use_account_balance", True)),
            "use_available_margin": bool(state.get("auto_trade_use_available_margin", True)),
            "min_free_margin_pct": state.get("auto_trade_min_free_margin_pct", 30.0),
            "max_margin_usage_pct": state.get("auto_trade_max_margin_usage_pct", 70.0),
            "max_spread_points": state.get("auto_trade_max_spread_points", 120),
            "min_signal_score": state.get("auto_trade_min_signal_score", 0.55),
            "allow_sell": bool(state.get("auto_trade_allow_sell", True)),
            "cooldown_sec": state.get("auto_trade_cooldown_sec", 30),
            "session_start_hour": state.get("auto_trade_session_start_hour", 0),
            "session_end_hour": state.get("auto_trade_session_end_hour", 24),
            "use_atr_tpsl": bool(state.get("auto_trade_use_atr_tpsl", True)),
            "atr_period": state.get("auto_trade_atr_period", 14),
            "atr_sl_mult": state.get("auto_trade_atr_sl_mult", 1.5),
            "atr_tp_mult": state.get("auto_trade_atr_tp_mult", 2.5),
            "trailing_enabled": bool(state.get("auto_trade_trailing_enabled", True)),
            "trailing_activation_rr": state.get("auto_trade_trailing_activation_rr", 1.0),
            "trailing_atr_mult": state.get("auto_trade_trailing_atr_mult", 1.0),
            "confidence_model": state.get("auto_trade_confidence_model", "weighted"),
            "confidence_threshold": state.get("auto_trade_confidence_threshold", 0.6),
            "tf_weight_m1": state.get("auto_trade_tf_weight_m1", 0.35),
            "tf_weight_m5": state.get("auto_trade_tf_weight_m5", 0.30),
            "tf_weight_m15": state.get("auto_trade_tf_weight_m15", 0.20),
            "tf_weight_m30": state.get("auto_trade_tf_weight_m30", 0.15),
            "partial_tp_enabled": bool(state.get("auto_trade_partial_tp_enabled", True)),
            "partial_tp_rr1": state.get("auto_trade_partial_tp_rr1", 1.0),
            "partial_tp_close_pct1": state.get("auto_trade_partial_tp_close_pct1", 40.0),
            "partial_tp_rr2": state.get("auto_trade_partial_tp_rr2", 2.0),
            "partial_tp_close_pct2": state.get("auto_trade_partial_tp_close_pct2", 35.0),
            "break_even_enabled": bool(state.get("auto_trade_break_even_enabled", True)),
            "break_even_rr": state.get("auto_trade_break_even_rr", 1.0),
            "break_even_offset_atr_mult": state.get("auto_trade_break_even_offset_atr_mult", 0.1),
            "trailing_mode": state.get("auto_trade_trailing_mode", "stateful_hl"),
            "stateful_trail_buffer_atr_mult": state.get("auto_trade_stateful_trail_buffer_atr_mult", 0.5),
        },
        "normalized": {
            "lot": normalized_lot,
        },
        "account_metrics": account_metrics,
        "profile": {
            "broker_id": (broker or {}).get("id"),
            "account_id": account_id,
            "scope": "account" if (broker and account_id is not None and has_auto_trade_profile(broker.get("id"), account_id)) else "global",
        },
    }


@router.post("/trade/sync_history")
def sync_trade_history_now():
    state = get_account_state()
    history_days = None if state.get("trade_history_sync_all") else int(state.get("trade_history_sync_days") or 90)
    results = sync_all_terminal_trade_state(history_days=history_days)
    total = len(results)
    failed = [r for r in results if not bool(r.get("synced")) and not bool(r.get("partial"))]
    partial = [r for r in results if bool(r.get("partial"))]

    if total == 0:
        status = "error"
        message = "Tidak ada broker MT5 aktif untuk sinkronisasi."
    elif len(failed) == total:
        status = "error"
        message = "Sinkronisasi history gagal untuk semua broker."
    elif failed or partial:
        status = "partial"
        message = f"Sinkronisasi parsial: sukses {total - len(failed) - len(partial)}, partial {len(partial)}, gagal {len(failed)}."
    else:
        status = "ok"
        message = "Sinkronisasi history selesai tanpa error."

    return {
        "status": status,
        "message": message,
        "trade_history_sync_all": bool(state.get("trade_history_sync_all")),
        "trade_history_sync_days": state.get("trade_history_sync_days"),
        "summary": {
            "total": total,
            "ok": total - len(failed) - len(partial),
            "partial": len(partial),
            "failed": len(failed),
        },
        "results": results,
    }

# user_open_trade structure:
# { "user_id": {
#     "balance": 1000,
#     "openTrade": False,
#     "entryPrice": None,
#     "entryTime": None,
#     "direction": None,
#     "pnl": 0,
#     "lastSignal": "wait",
#     "tradeHistory": []
#   }
# }
# Note: user_open_trade is an in-memory dict to track open trade state for frontend compatibility.
user_open_trade = {}


@router.post("/account/set_initial_balance")
def set_initial_balance(amount: float = Body(...)):
    state = get_account_state()
    state["initial_balance"] = amount
    state["balance"] = amount
    save_account_state(state)
    return {"status": "ok", "balance": state["balance"]}

@router.post("/account/deposit")
def deposit(amount: float = Body(...)):
    state = get_account_state()
    state["balance"] += amount
    if "history" not in state:
        state["history"] = []
    state["history"].append({"type": "deposit", "amount": amount})
    save_account_state(state)
    return {"status": "ok", "balance": state["balance"]}

@router.post("/account/withdraw")
def withdraw(amount: float = Body(...)):
    state = get_account_state()
    if amount > state["balance"]:
        return {"status": "error", "message": "Insufficient balance"}
    state["balance"] -= amount
    if "history" not in state:
        state["history"] = []
    state["history"].append({"type": "withdraw", "amount": amount})
    save_account_state(state)
    return {"status": "ok", "balance": state["balance"]}

@router.post("/account/adjustment")
def adjustment(amount: float = Body(...), note: str = Body("")):
    state = get_account_state()
    state["balance"] += amount
    if "history" not in state:
        state["history"] = []
    state["history"].append({"type": "adjustment", "amount": amount, "note": note})
    save_account_state(state)
    return {"status": "ok", "balance": state["balance"]}

@router.post("/account/set_lot")
def set_lot(lot: float = Body(...)):
    state = get_account_state()
    state["lot"] = lot
    save_account_state(state)
    return {"status": "ok", "lot": lot}

@router.post("/account/set_max_open_trades")
def set_max_open_trades(count: int = Body(...)):
    state = get_account_state()
    state["max_open_trades"] = count
    save_account_state(state)
    return {"status": "ok", "max_open_trades": count}


@router.get("/signal")
def get_signal(symbol: str = "XAUUSD", mode: str = "real"):
    state = get_account_state()
    broker = resolve_feed_broker(state=state, require_terminal_path=True)
    if not broker:
        broker = resolve_feed_broker(state=state, require_terminal_path=False)
    terminal_path = broker.get("terminal_path") if broker else None
    return get_signal_snapshot(symbol, mode=mode, terminal_path=terminal_path)

# Endpoint: OHLCV data for chart
from .logic import fetch_ohlcv
@router.get("/ohlcv")
def get_ohlcv(symbol: str = "XAUUSD", timeframe: str = "M1", bars: int = 100):
    try:
        state = get_account_state()
        broker = resolve_feed_broker(state=state, require_terminal_path=True)
        if not broker:
            broker = resolve_feed_broker(state=state, require_terminal_path=False)
        terminal_path = broker.get("terminal_path") if broker else None
        result = get_ohlcv_snapshot(symbol, timeframe, bars, terminal_path=terminal_path)
        return result
    except Exception as e:
        print("[ERROR] OHLCV endpoint:", str(e))
        return []


# --- User Open Trade Endpoints (for frontend compatibility) ---
@router.get("/user/open_trade")
def get_open_trade(user_id: str = Query(...)):
    # Return user open trade or default structure
    return user_open_trade.get(user_id, {
        "balance": 1000,
        "openTrade": False,
        "entryPrice": None,
        "entryTime": None,
        "direction": None,
        "pnl": 0,
        "lastSignal": "wait",
        "tradeHistory": []
    })


# Save open trade and append closed trades to history
@router.post("/user/open_trade")
def save_open_trade(user_id: str = Query(...), open_trade: dict = Body(...)):
    # Frontend compatibility only: state mirror in memory.
    # Persistent open/close lifecycle is handled exclusively by backend trade endpoints.
    user_open_trade[user_id] = open_trade
    return {"status": "ok"}

# Endpoint to get all trade history
@router.get("/trade/history")
def get_trade_history_endpoint():
    _sync_terminal_trade_views()
    return load_trade_history()


@router.get("/trade/open_count")
def get_trade_open_count():
    _sync_terminal_trade_views()
    return {"open_count": get_open_trades_count()}


@router.get("/trade/open_positions")
def get_trade_open_positions():
    _sync_terminal_trade_views()
    rows = list_open_trades()
    history = get_trade_history()
    state = get_account_state()
    return _decorate_open_positions_with_strategy_state(rows, history, state)


@router.post("/trade/update_tpsl")
def update_trade_tpsl(request: TradeTPSLUpdateRequest):
    ok = update_open_trade_tpsl(
        trade_id=request.trade_id,
        tp_value=request.tp_value,
        sl_value=request.sl_value,
    )
    if not ok:
        return {"status": "error", "message": "Open trade not found"}
    return {
        "status": "ok",
        "trade_id": request.trade_id,
        "tp_value": request.tp_value,
        "sl_value": request.sl_value,
    }

@router.post("/set-params")
def set_params(request: Request):
    # Placeholder: implement parameter update logic
    return {"status": "ok"}
