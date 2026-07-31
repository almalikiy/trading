import os
import subprocess
import threading
import time
from typing import Optional

import MetaTrader5 as mt5

from .db import log_mt5_error


_PROCESS_PATHS_CACHE = {"data": set(), "expires_at": 0.0}
_PROCESS_CACHE_LOCK = threading.Lock()
_BROKER_STATUS_CACHE = {}
_BROKER_STATUS_REFRESHING = set()
_BROKER_STATUS_LOCK = threading.Lock()


def ensure_terminal_running(terminal_path: Optional[str]):
    if not terminal_path:
        return False
    normalized = os.path.normcase(os.path.abspath(terminal_path))
    for proc in _list_process_paths():
        if proc == normalized:
            return True
    try:
        subprocess.Popen([terminal_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.0)
        return True
    except Exception:
        return False


def _list_process_paths():
    now = time.monotonic()
    with _PROCESS_CACHE_LOCK:
        if _PROCESS_PATHS_CACHE["expires_at"] > now:
            return set(_PROCESS_PATHS_CACHE["data"])

    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process | Select-Object -ExpandProperty ExecutablePath",
            ],
            text=True,
            timeout=1,
        )
        paths = {
            os.path.normcase(os.path.abspath(line.strip()))
            for line in out.splitlines()
            if line and line.strip() and os.path.exists(line.strip())
        }
        with _PROCESS_CACHE_LOCK:
            _PROCESS_PATHS_CACHE["data"] = paths
            _PROCESS_PATHS_CACHE["expires_at"] = time.monotonic() + 3.0
        return paths
    except Exception:
        return set()


class TerminalAdapter:
    terminal_type = "simulation"

    def open_trade(self, symbol: str, lot: float, trade_type: str):
        raise NotImplementedError

    def close_trade(self, symbol: str, lot: float, ticket: int):
        raise NotImplementedError

    def fetch_ohlcv(self, symbol: str, timeframe: str, bars: int):
        raise NotImplementedError


class MT5Adapter(TerminalAdapter):
    terminal_type = "mt5"

    def __init__(self, terminal_path: Optional[str], broker_name: str):
        self.terminal_path = terminal_path
        self.broker_name = broker_name

    def _initialize(self):
        if self.terminal_path:
            ensure_terminal_running(self.terminal_path)
            return mt5.initialize(path=self.terminal_path)
        return mt5.initialize()

    def open_trade(self, symbol: str, lot: float, trade_type: str):
        if not self._initialize():
            raise RuntimeError("MT5 not connected")
        order_type = mt5.ORDER_TYPE_BUY if trade_type == "buy" else mt5.ORDER_TYPE_SELL
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            mt5.shutdown()
            raise RuntimeError(f"No tick data for {symbol}")
        price = tick.ask if trade_type == "buy" else tick.bid
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": 0,
            "comment": "",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(req)
        mt5.shutdown()
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            log_mt5_error(f"[{self.broker_name}] open failed: {result.retcode} {result.comment}")
            raise RuntimeError(f"Order send failed: {result.retcode} {result.comment}")
        return {"status": "ok", "order": result._asdict()}

    def close_trade(self, symbol: str, lot: float, ticket: int):
        if not self._initialize():
            raise RuntimeError("MT5 not connected")
        position = mt5.positions_get(ticket=ticket)
        if not position:
            mt5.shutdown()
            raise RuntimeError(f"No open position with ticket {ticket}")
        pos = position[0]
        order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(symbol).bid if pos.type == mt5.POSITION_TYPE_BUY else mt5.symbol_info_tick(symbol).ask
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": order_type,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "magic": 0,
            "comment": "",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(req)
        mt5.shutdown()
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            log_mt5_error(f"[{self.broker_name}] close failed: {result.retcode} {result.comment}")
            raise RuntimeError(f"Order close failed: {result.retcode} {result.comment}")
        return {"status": "ok", "order": result._asdict()}


class MouseAdapter(TerminalAdapter):
    terminal_type = "mouse"

    def __init__(self, window_hint: Optional[str]):
        self.window_hint = window_hint or "FinexBisnisSolusi"

    def open_trade(self, symbol: str, lot: float, trade_type: str):
        proc = subprocess.run(
            [
                "python",
                os.path.join(os.path.dirname(__file__), "pyautogui_order.py"),
                trade_type,
                self.window_hint,
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout)
        return {"status": "ok", "order": {"method": "mouse", "output": proc.stdout}}


class SimulationAdapter(TerminalAdapter):
    terminal_type = "simulation"

    def open_trade(self, symbol: str, lot: float, trade_type: str):
        price = 2000.0
        return {"status": "ok", "order": {"ticket": int(time.time()), "price": price, "symbol": symbol, "volume": lot, "type": trade_type}}

    def close_trade(self, symbol: str, lot: float, ticket: int):
        price = 2000.0
        return {"status": "ok", "order": {"ticket": ticket, "price": price, "symbol": symbol, "volume": lot}}


def get_broker_adapter(broker, order_method: Optional[str] = None):
    platform = str((broker or {}).get("platform", "mt5")).lower()
    method = str(order_method or (broker or {}).get("execution_mode", "mouse")).lower()
    if platform == "simulation":
        return SimulationAdapter(), method
    if method == "mouse":
        return MouseAdapter((broker or {}).get("window_hint")), method
    if platform == "mt5":
        return MT5Adapter((broker or {}).get("terminal_path"), (broker or {}).get("name", "unknown")), method
    if platform == "mt4":
        # Direct API MT4 not available in this stack; fallback to mouse.
        return MouseAdapter((broker or {}).get("window_hint")), "mouse"
    return SimulationAdapter(), "simulation"


def probe_broker_order_status(broker, symbol: str = "XAUUSD", auto_start: bool = True):
    """
    Return a lightweight readiness check for opening an order on a broker terminal.
    This is used by auto-trader routing and frontend diagnostics.
    """
    broker = broker or {}
    platform = str(broker.get("platform", "mt5")).lower()
    terminal_path = broker.get("terminal_path")

    status = {
        "broker_id": broker.get("id"),
        "broker_name": broker.get("name"),
        "platform": platform,
        "terminal_path": terminal_path,
        "can_open_order": False,
        "reason": "unknown",
        "checks": {},
    }

    if platform != "mt5":
        status["can_open_order"] = True
        status["reason"] = "non_mt5_platform"
        status["checks"] = {"platform_supported": False}
        return status

    if not terminal_path:
        status["reason"] = "terminal_path_missing"
        return status

    if auto_start:
        started = ensure_terminal_running(terminal_path)
        status["checks"]["terminal_process_running"] = bool(started)

    initialized = False
    try:
        initialized = mt5.initialize(path=terminal_path)
        if not initialized:
            status["reason"] = "mt5_initialize_failed"
            return status

        term = mt5.terminal_info()
        account = mt5.account_info()
        symbol_info = mt5.symbol_info(symbol)

        term_connected = bool(getattr(term, "connected", False)) if term else False
        term_trade_allowed = bool(getattr(term, "trade_allowed", False)) if term else False
        account_trade_allowed = bool(getattr(account, "trade_allowed", False)) if account else False

        symbol_visible = bool(getattr(symbol_info, "visible", False)) if symbol_info else False
        if symbol_info and not symbol_visible:
            symbol_visible = bool(mt5.symbol_select(symbol, True))

        tick = mt5.symbol_info_tick(symbol)
        has_tick = tick is not None

        status["checks"].update(
            {
                "terminal_connected": term_connected,
                "terminal_trade_allowed": term_trade_allowed,
                "account_trade_allowed": account_trade_allowed,
                "symbol_visible": symbol_visible,
                "has_tick": has_tick,
            }
        )

        if not term_connected:
            status["reason"] = "terminal_disconnected"
            return status
        if not term_trade_allowed:
            status["reason"] = "terminal_trade_disabled"
            return status
        if not account_trade_allowed:
            status["reason"] = "account_trade_disabled"
            return status
        if not symbol_visible:
            status["reason"] = "symbol_not_visible"
            return status
        if not has_tick:
            status["reason"] = "no_tick_data"
            return status

        status["can_open_order"] = True
        status["reason"] = "ready"
        return status
    except Exception as exc:
        status["reason"] = f"probe_failed: {exc}"
        return status
    finally:
        if initialized:
            mt5.shutdown()


def get_broker_order_status_snapshot(broker, symbol: str = "XAUUSD"):
    broker = broker or {}
    cache_key = (broker.get("id"), symbol)

    def refresh_worker():
        status = probe_broker_order_status(broker, symbol=symbol, auto_start=False)
        with _BROKER_STATUS_LOCK:
            _BROKER_STATUS_CACHE[cache_key] = {
                "data": status,
                "updated_at": time.time(),
            }
            _BROKER_STATUS_REFRESHING.discard(cache_key)

    with _BROKER_STATUS_LOCK:
        cached = _BROKER_STATUS_CACHE.get(cache_key)
        refreshing = cache_key in _BROKER_STATUS_REFRESHING

        if not refreshing:
            _BROKER_STATUS_REFRESHING.add(cache_key)
            thread = threading.Thread(target=refresh_worker, daemon=True)
            thread.start()

    if cached and cached.get("data"):
        payload = dict(cached["data"])
        payload["cached"] = True
        payload["cached_at"] = cached.get("updated_at")
        return payload

    platform = str(broker.get("platform", "mt5")).lower()
    if platform != "mt5":
        return {
            "broker_id": broker.get("id"),
            "broker_name": broker.get("name"),
            "platform": platform,
            "terminal_path": broker.get("terminal_path"),
            "can_open_order": True,
            "reason": "non_mt5_platform",
            "checks": {"platform_supported": False},
            "cached": False,
            "refreshing": True,
        }

    return {
        "broker_id": broker.get("id"),
        "broker_name": broker.get("name"),
        "platform": platform,
        "terminal_path": broker.get("terminal_path"),
        "can_open_order": False,
        "reason": "status_pending",
        "checks": {},
        "cached": False,
        "refreshing": True,
    }
