
from fastapi import APIRouter, Request, Query, Body
import os
import json

TRADE_HISTORY_FILE = "trade_history.json"
from .logic import open_real_trade, close_real_trade, analyze_symbol

router = APIRouter()

# === Real Trade Execution Endpoints ===
@router.post("/trade/open")
def open_trade(symbol: str = Body(...), lot: float = Body(0.01), trade_type: str = Body(...), signal_time: float = Body(None)):
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
        result = open_real_trade(symbol, lot, trade_type)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/trade/close")
def close_trade(symbol: str = Body(...), lot: float = Body(0.01), ticket: int = Body(...)):
    """
    Close a real trade on MT5 by ticket.
    """
    try:
        result = close_real_trade(symbol, lot, ticket)
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
        return df.to_dict(orient="records")
    except Exception as e:
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
    return {"status": "ok"}

# Endpoint to get all trade history
@router.get("/trade/history")
def get_trade_history():
    return trade_history

@router.post("/set-params")
def set_params(request: Request):
    # Placeholder: implement parameter update logic
    return {"status": "ok"}
