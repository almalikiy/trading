from fastapi import APIRouter, Request, Query, Body
import os
import json
router = APIRouter()
from .logic import log_mt5_error, load_mt5_error_log
import subprocess
from pydantic import BaseModel

# === Analytic TP/SL Logic ===
ACCOUNT_STATE_FILE = "account_state.json"
def load_account_state():
    if os.path.exists(ACCOUNT_STATE_FILE):
        with open(ACCOUNT_STATE_FILE, "r") as f:
            state = json.load(f)
            if "enable_real_trade" not in state:
                state["enable_real_trade"] = False
            if "auto_analytic_tpsl" not in state:
                state["auto_analytic_tpsl"] = False
            if "tp_value" not in state:
                state["tp_value"] = 0.5
            if "sl_value" not in state:
                state["sl_value"] = None
            return state
    return {"balance": 1000, "enable_real_trade": False, "auto_analytic_tpsl": False, "tp_value": 0.5, "sl_value": None}

def save_account_state(state):
    with open(ACCOUNT_STATE_FILE, "w") as f:
        json.dump(state, f)

# Endpoint: Get analytic TP/SL state
@router.get("/account/state")
def get_account_state():
    return load_account_state()

# Endpoint: Set analytic TP/SL value
class AnalyticTPSLRequest(BaseModel):
    tp_value: float
    sl_value: float | None = None

@router.post("/account/set_analytic_tpsl")
def set_analytic_tpsl(request: AnalyticTPSLRequest):
    try:
        state = load_account_state()
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
        state = load_account_state()
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
    log = load_mt5_error_log()
    # Urutkan dari terbaru ke terlama
    log = sorted(log, key=lambda x: x["timestamp"], reverse=True)
    return log


TRADE_HISTORY_FILE = "trade_history.json"
from .logic import open_real_trade, close_real_trade, analyze_symbol

# === Real Trade Execution Endpoints ===
@router.post("/trade/open")
def open_trade(symbol: str = Body(...), lot: float = Body(0.01), trade_type: str = Body(...), signal_time: float = Body(None), order_method: str = Body('pyautogui')):
    """
    Open a real trade on MT5. trade_type: 'buy' or 'sell'.
    Only executes if enable_real_trade is True and signal is not expired.
    """
    import time
    if not account_state.get("enable_real_trade", False):
        return {"status": "error", "message": "Real trading not enabled"}
    # Check signal timeliness (default max 60s)
    if signal_time is not None:
        now = time.time()
        if now - signal_time > 60:
            return {"status": "skipped", "message": "Signal expired, trade skipped"}
    try:
        if order_method == 'pyautogui':
            # Jalankan script PyAutoGUI untuk order (hanya argumen buy/sell)
            proc = subprocess.run([
                'python', os.path.join(os.path.dirname(__file__), 'pyautogui_order.py'),
                trade_type
            ], capture_output=True, text=True)
            if proc.returncode != 0:
                return {"status": "error", "message": proc.stderr or proc.stdout}
            entry_price = None  # Tidak bisa dapat harga pasti dari GUI
            result = {"status": "ok", "order": {"method": "pyautogui", "output": proc.stdout}}
        else:
            result = open_real_trade(symbol, lot, trade_type)
            order = result.get("order", {})
            entry_price = order.get("price", None)
        entry_time = int(time.time())
        # --- TP/SL Value: auto hitung jika auto_analytic_tpsl aktif ---
        state = load_account_state()
        tp_value = state.get("tp_value", 0.5)
        sl_value = state.get("sl_value", None)
        if state.get("auto_analytic_tpsl", False):
            # Contoh auto: TP = 2x lot, SL = 1x lot (bisa diganti sesuai logic analitik)
            tp_value = round(2 * float(lot), 2)
            sl_value = round(1 * float(lot), 2)
            # Simpan ke state
            state["tp_value"] = tp_value
            state["sl_value"] = sl_value
            save_account_state(state)
        trade = {
            "type": trade_type.upper(),
            "entry": entry_price,
            "exit": None,
            "profit": None,
            "entryTime": entry_time,
            "exitTime": None,
            "reason": "open",
            "tpValue": tp_value,
            "slValue": sl_value
        }
        trade_history.append(trade)
        save_trade_history()
        # --- Update user_open_trade ---
        user_id = result.get("user_id", "default")
        user_open_trade[user_id] = user_open_trade.get(user_id, {
            "balance": 1000,
            "openTrade": False,
            "entryPrice": None,
            "entryTime": None,
            "direction": None,
            "pnl": 0,
            "lastSignal": "wait",
            "tradeHistory": []
        })
        user_open_trade[user_id]["openTrade"] = True
        user_open_trade[user_id]["entryPrice"] = entry_price
        user_open_trade[user_id]["entryTime"] = entry_time
        user_open_trade[user_id]["direction"] = trade_type.lower()
        user_open_trade[user_id]["tradeHistory"].append(trade)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


# Endpoint: Force close all open trades (for emergency/manual fix)
@router.post("/trade/force_close")
def force_close_all_trades():
    """
    Force close all open trades on MT5. Use if trade stuck open due to backend error.
    """
    import MetaTrader5 as mt5
    import time
    if not account_state.get("enable_real_trade", False):
        return {"status": "error", "message": "Real trading not enabled"}
    if not mt5.initialize():
        return {"status": "error", "message": "MT5 not connected"}
    try:
        positions = mt5.positions_get()
        closed = []
        errors = []
        if positions:
            for pos in positions:
                symbol = pos.symbol
                lot = pos.volume
                ticket = pos.ticket
                entry_price = pos.price_open
                entry_time = pos.time
                direction = "buy" if pos.type == mt5.POSITION_TYPE_BUY else "sell"
                try:
                    result = close_real_trade(symbol, lot, ticket)
                    # Extract exit price and time from result if available
                    order = result.get("order", {})
                    exit_price = order.get("price", None)
                    exit_time = int(time.time())
                    profit = pos.profit if hasattr(pos, "profit") else None
                    # Record to trade_history
                    trade_history.append({
                        "type": direction.upper(),
                        "entry": entry_price,
                        "exit": exit_price,
                        "profit": profit,
                        "entryTime": entry_time,
                        "exitTime": exit_time,
                        "reason": "force_close"
                    })
                    save_trade_history()
                    closed.append({"symbol": symbol, "ticket": ticket, "result": result})
    
                    # --- Simulation Endpoints ---
                    @router.get("/sim/state")
                    def get_sim_state():
                        with sim_lock:
                            return sim_state.copy()

                    @router.get("/sim/settings")
                    def get_sim_settings():
                        with sim_lock:
                            return sim_settings.copy()

                    @router.post("/sim/settings")
                    def update_sim_settings(settings: dict = Body(...)):
                        with sim_lock:
                            sim_settings.update(settings)
                            save_sim_settings()
                        return {"status": "ok", "settings": sim_settings}

                except Exception as e:
                    errors.append({"symbol": symbol, "ticket": ticket, "error": str(e)})
        # Clear all user open trades (so frontend sees no active trade)
        for user_id in list(user_open_trade.keys()):
            user_open_trade[user_id]["openTrade"] = False
            user_open_trade[user_id]["entryPrice"] = None
            user_open_trade[user_id]["entryTime"] = None
            user_open_trade[user_id]["direction"] = None
            user_open_trade[user_id]["pnl"] = 0
            user_open_trade[user_id]["lastSignal"] = "wait"
            # Optionally, update tradeHistory if needed
        mt5.shutdown()
        return {"status": "ok", "closed": closed, "errors": errors}
    except Exception as e:
        mt5.shutdown()
        return {"status": "error", "message": str(e)}

@router.post("/trade/close")
def close_trade(symbol: str = Body(...), lot: float = Body(0.01), ticket: int = Body(...)):
    """
    Close a real trade on MT5 by ticket.
    """
    import time
    try:
        result = close_real_trade(symbol, lot, ticket)
        # --- Tambahkan pencatatan close trade ke trade_history ---
        order = result.get("order", {})
        exit_price = order.get("price", None)
        exit_time = int(time.time())
        # Cari trade open terakhir yang belum di-close
        for t in reversed(trade_history):
            if t["exit"] is None and t["type"].lower() in ["buy", "sell"]:
                t["exit"] = exit_price
                t["exitTime"] = exit_time
                t["profit"] = order.get("profit", None)
                t["reason"] = "close"
                break
        save_trade_history()
        # --- Update user_open_trade ---
        user_id = result.get("user_id", "default")
        if user_id in user_open_trade:
            user_open_trade[user_id]["openTrade"] = False
            user_open_trade[user_id]["entryPrice"] = None
            user_open_trade[user_id]["entryTime"] = None
            user_open_trade[user_id]["direction"] = None
            user_open_trade[user_id]["pnl"] = 0
            user_open_trade[user_id]["lastSignal"] = "wait"
            # Optionally, update tradeHistory if needed
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}

ACCOUNT_STATE_FILE = "account_state.json"
def load_account_state():
    if os.path.exists(ACCOUNT_STATE_FILE):
        with open(ACCOUNT_STATE_FILE, "r") as f:
            state = json.load(f)
            if "enable_real_trade" not in state:
                state["enable_real_trade"] = False
            if "auto_analytic_tpsl" not in state:
                state["auto_analytic_tpsl"] = False
            return state
    return {
        "balance": 1000.0,
        "initial_balance": 1000.0,
        "lot": 0.01,
        "max_open_trades": 1,
        "history": [],
        "enable_real_trade": False,
        "auto_analytic_tpsl": False,
    }
# Endpoint to set auto_analytic_tpsl
@router.post("/account/set_auto_analytic_tpsl")
def set_auto_analytic_tpsl(enabled: bool = Body(...)):
    account_state["auto_analytic_tpsl"] = enabled
    save_account_state()
    return {"status": "ok", "auto_analytic_tpsl": enabled}

# Endpoint to set enable_real_trade
@router.post("/account/set_enable_real_trade")
def set_enable_real_trade(enabled: bool = Body(...)):
    account_state["enable_real_trade"] = enabled
    save_account_state()
    return {"status": "ok", "enable_real_trade": enabled}

def save_account_state():
    with open(ACCOUNT_STATE_FILE, "w") as f:
        json.dump(account_state, f)



# In-memory user open trade storage (for demo; replace with DB in production)
user_open_trade = {}
def load_trade_history():
    if os.path.exists(TRADE_HISTORY_FILE):
        with open(TRADE_HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

def save_trade_history():
    with open(TRADE_HISTORY_FILE, "w") as f:
        json.dump(trade_history, f)

# In-memory trade history (all closed trades)
trade_history = load_trade_history()
# In-memory balance and settings (single account, no user management)
account_state = load_account_state()
# --- Balance & Account Management Endpoints ---
@router.get("/account/state")
def get_account_state():
    return account_state

@router.post("/account/set_initial_balance")
def set_initial_balance(amount: float = Body(...)):
    account_state["initial_balance"] = amount
    account_state["balance"] = amount
    save_account_state()
    save_account_state()
    return {"status": "ok", "balance": account_state["balance"]}

@router.post("/account/deposit")
def deposit(amount: float = Body(...)):
    account_state["balance"] += amount
    account_state["history"].append({"type": "deposit", "amount": amount})
    save_account_state()
    return {"status": "ok", "balance": account_state["balance"]}

@router.post("/account/withdraw")
def withdraw(amount: float = Body(...)):
    if amount > account_state["balance"]:
        return {"status": "error", "message": "Insufficient balance"}
    account_state["balance"] -= amount
    account_state["history"].append({"type": "withdraw", "amount": amount})
    save_account_state()
    return {"status": "ok", "balance": account_state["balance"]}

@router.post("/account/adjustment")
def adjustment(amount: float = Body(...), note: str = Body("")):
    account_state["balance"] += amount
    account_state["history"].append({"type": "adjustment", "amount": amount, "note": note})
    save_account_state()
    return {"status": "ok", "balance": account_state["balance"]}

@router.post("/account/set_lot")
def set_lot(lot: float = Body(...)):
    account_state["lot"] = lot
    save_account_state()
    return {"status": "ok", "lot": lot}

@router.post("/account/set_max_open_trades")
def set_max_open_trades(count: int = Body(...)):
    account_state["max_open_trades"] = count
    save_account_state()
    return {"status": "ok", "max_open_trades": count}


@router.get("/signal")
def get_signal(symbol: str = "XAUUSD", mode: str = "real"):
    return analyze_symbol(symbol, mode=mode)

# Endpoint: OHLCV data for chart
from .logic import fetch_ohlcv
@router.get("/ohlcv")
def get_ohlcv(symbol: str = "XAUUSD", timeframe: str = "M1", bars: int = 100):
    try:
        df = fetch_ohlcv(symbol, timeframe, bars)
        # Kurangi 3 jam (10800 detik) dari epoch time untuk semua candle
        df["time"] = df["time"] - 3 * 3600
        # Hanya kirim kolom time hasil modifikasi
        df = df[["time", "open", "high", "low", "close", "tick_volume"]]
        # Debug log: print shape dan head
        print("[DEBUG] OHLCV shape:", df.shape)
        print("[DEBUG] OHLCV head:", df.head(3).to_dict(orient="records"))
        result = df.to_dict(orient="records")
        print("[DEBUG] OHLCV result sample:", result[:2])
        return result
    except Exception as e:
        print("[ERROR] OHLCV endpoint:", str(e))
        return {"error": str(e)}


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
    user_open_trade[user_id] = open_trade
    # Save closed trades to trade_history
    trades = open_trade.get("tradeHistory", [])
    for trade in trades:
        # Only add if not already in history (by entryTime+exitTime+type)
        if trade.get("exitTime") and not any(
            t.get("entryTime") == trade.get("entryTime") and t.get("exitTime") == trade.get("exitTime") and t.get("type") == trade.get("type")
            for t in trade_history
        ):
            trade_history.append(trade)
            save_trade_history()
    # Juga pastikan open trade (exitTime=None) dicatat ke trade_history jika belum ada
    for trade in trades:
        if not trade.get("exitTime") and not any(
            t.get("entryTime") == trade.get("entryTime") and t.get("type") == trade.get("type") and t.get("exitTime") is None
            for t in trade_history
        ):
            trade_history.append(trade)
            save_trade_history()
    return {"status": "ok"}

# Endpoint to get all trade history
@router.get("/trade/history")
def get_trade_history():
    # Gabungkan trade_history dengan open trade (jika ada)
    # Selalu baca file trade_history.json agar data sinkron
    if os.path.exists(TRADE_HISTORY_FILE):
        with open(TRADE_HISTORY_FILE, "r") as f:
            file_history = json.load(f)
    else:
        file_history = []
    result = list(file_history)
    # Cek open trade dari sim_state (jika simulasi aktif)
    try:
        from .sim_engine import sim_state, sim_lock
        with sim_lock:
            if sim_state.get("open_trade"):
                result.append({
                    "type": sim_state.get("direction"),
                    "entry": sim_state.get("entry_price"),
                    "exit": None,
                    "profit": None,
                    "entryTime": sim_state.get("entry_time"),
                    "exitTime": None,
                    "reason": "open"
                })
    except Exception:
        pass
    return result

@router.post("/set-params")
def set_params(request: Request):
    # Placeholder: implement parameter update logic
    return {"status": "ok"}
