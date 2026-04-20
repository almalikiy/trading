from fastapi import Body


# Simpan status open trade per user (dummy, in-memory)
user_open_trade = {}

# Simpan data simulasi global (open, target close price, loss)
global_simulation_data = []


# Endpoint untuk simpan status open trade user
@app.post("/user/open_trade")
def save_open_trade(user_id: str = Query(...), open_trade: dict = Body(...)):
    user_open_trade[user_id] = open_trade
    # Jika open_trade mengandung tradeHistory, tambahkan ke global_simulation_data
    trade_history = open_trade.get("tradeHistory")
    if trade_history:
        for trade in trade_history:
            # Cek apakah trade sudah ada di global_simulation_data (berdasarkan entryTime dan user_id)
            exists = any(
                t.get("entryTime") == trade.get("entryTime") and t.get("user_id") == user_id
                for t in global_simulation_data
            )
            if not exists:
                trade_copy = trade.copy()
                trade_copy["user_id"] = user_id
                global_simulation_data.append(trade_copy)
    return {"status": "ok"}


# Endpoint untuk ambil status open trade user
@app.get("/user/open_trade")
def get_open_trade(user_id: str = Query(...)):
    return user_open_trade.get(user_id, None)

# Endpoint untuk ambil data simulasi global (semua user)
@app.get("/simulation/global_data")
def get_global_simulation_data():
    return global_simulation_data
# Simulasi Trading Engine (FastAPI)
# Engine ini hanya untuk simulasi, tidak mengambil data dari MT5
# Data time bisa diubah/digenerate untuk keperluan simulasi

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

app = FastAPI()

# Allow CORS for all origins (for frontend testing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/ohlcv")
def get_ohlcv(symbol: str = "XAUUSD", timeframe: str = "M1", bars: int = 100, start_time: int = None, interval_sec: int = 60):
    # Generate dummy/simulated OHLCV data
    np.random.seed(42)
    base = 2000
    if start_time is None:
        start_time = int(datetime.utcnow().timestamp())
    times = [start_time + i * interval_sec for i in range(bars)]
    prices = base + np.cumsum(np.random.randn(bars))
    df = pd.DataFrame({
        'time': times,
        'open': prices + np.random.randn(bars),
        'high': prices + np.abs(np.random.randn(bars)),
        'low': prices - np.abs(np.random.randn(bars)),
        'close': prices,
        'tick_volume': np.random.randint(100, 200, bars)
    })
    return df.to_dict(orient="records")

@app.get("/signal")
def get_signal(symbol: str = "XAUUSD", mode: str = "real"):
    # Dummy signal: buy if random > 0, else wait
    import random
    signal = "buy" if random.random() > 0.5 else "wait"
    # Dummy indicators for all TF
    tfs = ['M1','M5','M15','M30']
    indicators = {tf: {
        'rsi': np.random.uniform(30, 70),
        'macd': np.random.uniform(-2, 2),
        'macd_signal': np.random.uniform(-2, 2),
        'bb_lower': np.random.uniform(1900, 2000),
        'bb_mid': np.random.uniform(2000, 2100),
        'bb_upper': np.random.uniform(2100, 2200),
        'sma': np.random.uniform(2000, 2100),
        'stoch_k': np.random.uniform(0, 100),
        'stoch_d': np.random.uniform(0, 100),
    } for tf in tfs}
    sim = {'balance': 1000 + np.random.uniform(-50, 50), 'open_trade': bool(random.getrandbits(1)), 'pnl': np.random.uniform(-10, 10)}
    return {'signal': signal, 'indicators': indicators, 'simulator': sim}
