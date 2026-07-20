from fastapi import APIRouter, Request, Query, Body
from .db import get_account_state, save_account_state, insert_trade, get_trade_history, get_broker, get_default_broker, get_open_trades_count, list_open_trades, close_trade_record, resolve_feed_broker, update_open_trade_tpsl
router = APIRouter()
from .logic import log_mt5_error
import subprocess
import os
from pydantic import BaseModel
from .broker_routes import TradeOpenRequest, open_trade_v2
from .terminal_adapters import get_broker_adapter
from .terminal_adapters import ensure_terminal_running

# === Analytic TP/SL Logic ===

# Endpoint: Get analytic TP/SL state
@router.get("/account/state")
def get_account_state_route():
    return get_account_state()

# Endpoint: Set analytic TP/SL value
class AnalyticTPSLRequest(BaseModel):
    tp_value: float
    sl_value: float | None = None


class TradeTPSLUpdateRequest(BaseModel):
    trade_id: str
    tp_value: float | None = None
    sl_value: float | None = None

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


from .logic import analyze_symbol, get_signal_snapshot, get_ohlcv_snapshot

def save_trade_history(trade):
    insert_trade(trade)

def load_trade_history():
    return get_trade_history()

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
        order = result.get("order", {})
        close_trade_record(
            target.get("trade_id"),
            exit_price=order.get("price"),
            profit=order.get("profit"),
            exit_time=int(time.time()),
            ticket=ticket,
            reason="close_legacy",
        )

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
    save_account_state(state)
    return {"status": "ok", "data_feed_broker_id": broker_id}

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
    if terminal_path:
        ensure_terminal_running(terminal_path)
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
        if terminal_path:
            ensure_terminal_running(terminal_path)
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
    return load_trade_history()


@router.get("/trade/open_count")
def get_trade_open_count():
    return {"open_count": get_open_trades_count()}


@router.get("/trade/open_positions")
def get_trade_open_positions():
    return list_open_trades()


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
