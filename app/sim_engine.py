import threading
import time
import json
import os

SIM_STATE_FILE = os.path.join(os.path.dirname(__file__), "sim_state.json")
SIM_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "sim_settings.json")

sim_state = {
    "balance": 1000.0,
    "open_trade": False,
    "entry_price": None,
    "entry_time": None,
    "direction": None,
    "pnl": 0,
    "last_signal": "wait",
    "trade_history": []
}

sim_settings = {
    "symbol": "XAUUSD",
    "lot": 0.01,
    "interval": 5,  # seconds
    "auto": True
}

sim_lock = threading.Lock()

# Load state/settings if exist
if os.path.exists(SIM_STATE_FILE):
    with open(SIM_STATE_FILE, "r") as f:
        sim_state.update(json.load(f))
if os.path.exists(SIM_SETTINGS_FILE):
    with open(SIM_SETTINGS_FILE, "r") as f:
        sim_settings.update(json.load(f))

def save_sim_state():
    with sim_lock:
        with open(SIM_STATE_FILE, "w") as f:
            json.dump(sim_state, f)

def save_sim_settings():
    with sim_lock:
        with open(SIM_SETTINGS_FILE, "w") as f:
            json.dump(sim_settings, f)

def simulate_once():
    # Dummy logic: open trade if not open, close after 10s, random PnL
    now = int(time.time())
    with sim_lock:
        if not sim_state["open_trade"]:
            sim_state["open_trade"] = True
            sim_state["entry_price"] = 2000.0
            sim_state["entry_time"] = now
            sim_state["direction"] = "buy"
            sim_state["last_signal"] = "buy"
        else:
            # Close after 10s
            if now - sim_state["entry_time"] > 10:
                exit_price = sim_state["entry_price"] + 1.0
                pnl = exit_price - sim_state["entry_price"]
                sim_state["balance"] += pnl
                sim_state["trade_history"].append({
                    "type": sim_state["direction"],
                    "entry": sim_state["entry_price"],
                    "exit": exit_price,
                    "profit": pnl,
                    "entryTime": sim_state["entry_time"],
                    "exitTime": now,
                    "reason": "sim_auto"
                })
                sim_state["open_trade"] = False
                sim_state["entry_price"] = None
                sim_state["entry_time"] = None
                sim_state["direction"] = None
                sim_state["pnl"] = 0
                sim_state["last_signal"] = "wait"
        save_sim_state()

def sim_loop():
    while True:
        if sim_settings.get("auto", True):
            simulate_once()
        time.sleep(sim_settings.get("interval", 5))

def start_simulation_thread():
    t = threading.Thread(target=sim_loop, daemon=True)
    t.start()

# Call this from main app (e.g. in FastAPI startup event)
