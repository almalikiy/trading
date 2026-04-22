# =============================================
# Penjelasan singkat keyword, API, dan library (FastAPI):
#
# - FastAPI: Framework Python modern untuk membuat REST API/web backend dengan cepat dan mudah.
# - APIRouter: Fitur FastAPI untuk mengelompokkan endpoint (route) dalam modul terpisah.
# - @router.get/@router.post: Dekorator untuk mendefinisikan endpoint HTTP GET/POST.
# - Request: Objek permintaan HTTP, bisa digunakan untuk akses data request.
#
# Keyword penting Python/FastAPI:
# - def: Mendefinisikan fungsi endpoint.
# - return: Mengembalikan response ke client (frontend).
# - try/except: Penanganan error agar API tetap stabil.
#
# Endpoint utama file ini:
# - /signal: Mengambil sinyal trading dan indikator (multi-timeframe).
# - /ohlcv: Mengambil data harga OHLCV untuk chart.
# - /set-params: (Placeholder) Untuk update parameter dari frontend.
# =============================================
from fastapi import APIRouter, Request, Query, Body
from .logic import analyze_symbol

router = APIRouter()



# In-memory user open trade storage (for demo; replace with DB in production)
user_open_trade = {}
# In-memory trade history (all closed trades)
trade_history = []
# In-memory balance and settings (single account, no user management)
account_state = {
    "balance": 1000.0,
    "initial_balance": 1000.0,
    "lot": 0.01,
    "max_open_trades": 1,
    "history": [],
}
# --- Balance & Account Management Endpoints ---
@router.get("/account/state")
def get_account_state():
    return account_state

@router.post("/account/set_initial_balance")
def set_initial_balance(amount: float = Body(...)):
    account_state["initial_balance"] = amount
    account_state["balance"] = amount
    return {"status": "ok", "balance": account_state["balance"]}

@router.post("/account/deposit")
def deposit(amount: float = Body(...)):
    account_state["balance"] += amount
    account_state["history"].append({"type": "deposit", "amount": amount})
    return {"status": "ok", "balance": account_state["balance"]}

@router.post("/account/withdraw")
def withdraw(amount: float = Body(...)):
    if amount > account_state["balance"]:
        return {"status": "error", "message": "Insufficient balance"}
    account_state["balance"] -= amount
    account_state["history"].append({"type": "withdraw", "amount": amount})
    return {"status": "ok", "balance": account_state["balance"]}

@router.post("/account/adjustment")
def adjustment(amount: float = Body(...), note: str = Body("")):
    account_state["balance"] += amount
    account_state["history"].append({"type": "adjustment", "amount": amount, "note": note})
    return {"status": "ok", "balance": account_state["balance"]}

@router.post("/account/set_lot")
def set_lot(lot: float = Body(...)):
    account_state["lot"] = lot
    return {"status": "ok", "lot": lot}

@router.post("/account/set_max_open_trades")
def set_max_open_trades(count: int = Body(...)):
    account_state["max_open_trades"] = count
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
    return {"status": "ok"}

# Endpoint to get all trade history
@router.get("/trade/history")
def get_trade_history():
    return trade_history

@router.post("/set-params")
def set_params(request: Request):
    # Placeholder: implement parameter update logic
    return {"status": "ok"}
