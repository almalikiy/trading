import os
import subprocess
import threading
import time
from datetime import datetime, timedelta
import math
from typing import Optional

import MetaTrader5 as mt5

from .db import list_brokers, list_open_trades, log_mt5_error, upsert_trade_history_record


_PROCESS_PATHS_CACHE = {"data": set(), "expires_at": 0.0}
_PROCESS_CACHE_LOCK = threading.Lock()
_BROKER_STATUS_CACHE = {}
_BROKER_STATUS_REFRESHING = set()
_BROKER_STATUS_LOCK = threading.Lock()
_SYNC_ERROR_THROTTLE = {}
_SYNC_ERROR_LOCK = threading.Lock()


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


def _log_mt5_error_throttled(message, *, broker_id=None, broker_name=None, account_id=None, key=None, cooldown_sec=30):
    now = time.time()
    throttle_key = key or f"{broker_id}:{broker_name}:{message}"
    with _SYNC_ERROR_LOCK:
        last_ts = _SYNC_ERROR_THROTTLE.get(throttle_key, 0.0)
        if now - last_ts < float(cooldown_sec):
            return False
        _SYNC_ERROR_THROTTLE[throttle_key] = now

    log_mt5_error(message, broker_id=broker_id, broker_name=broker_name, account_id=account_id)
    return True


class TerminalAdapter:
    terminal_type = "simulation"

    def open_trade(self, symbol: str, lot: float, trade_type: str, tp: float = None, sl: float = None):
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

    def _current_account_id(self):
        account = mt5.account_info()
        login = getattr(account, "login", None) if account else None
        return int(login) if login is not None else None

    def _find_open_position(self, symbol: str, lot: float, trade_type: str):
        expected_type = mt5.POSITION_TYPE_BUY if trade_type == "buy" else mt5.POSITION_TYPE_SELL
        positions = mt5.positions_get(symbol=symbol) or []
        candidates = []
        for position in positions:
            if getattr(position, "type", None) != expected_type:
                continue
            volume = float(getattr(position, "volume", 0) or 0)
            if abs(volume - float(lot)) > 1e-9:
                continue
            candidates.append(position)
        if not candidates:
            return None
        return max(candidates, key=lambda position: (int(getattr(position, "time", 0) or 0), int(getattr(position, "ticket", 0) or 0)))

    def open_trade(self, symbol: str, lot: float, trade_type: str, tp: float = None, sl: float = None):
        if not self._initialize():
            raise RuntimeError("MT5 not connected")
        account_id = self._current_account_id()
        info = mt5.symbol_info(symbol)
        if not info:
            mt5.shutdown()
            raise RuntimeError(f"Symbol {symbol} not found")
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            mt5.shutdown()
            raise RuntimeError(f"No tick data for {symbol}")

        if lot < info.volume_min or lot > info.volume_max or (lot % info.volume_step != 0):
            mt5.shutdown()
            raise RuntimeError(
                f"Invalid lot {lot} for {symbol}. "
                f"Allowed range: {info.volume_min} - {info.volume_max}, step {info.volume_step}"
            )
        order_type = mt5.ORDER_TYPE_BUY if trade_type == "buy" else mt5.ORDER_TYPE_SELL                
        price = tick.ask if trade_type == "buy" else tick.bid
        if tp:
            tp = round(tp / info.point) * info.point
            if trade_type == "buy" and tp <= price:
                tp = price + info.point
            elif trade_type == "sell" and tp >= price:
                tp = price - info.point
        if sl:
            sl = round(sl / info.point) * info.point
            if trade_type == "buy" and sl >= price:
                sl = price - info.point
            elif trade_type == "sell" and sl <= price:
                sl = price + info.point        
        # Coba beberapa filling mode yang umum didukung broker
        filling_modes = [mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_RETURN, mt5.ORDER_FILLING_IOC]
        last_error = None
        for filling_mode in filling_modes:
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
                "type_filling": filling_mode,
            }
            if tp:
                req["tp"] = tp
            if sl:
                req["sl"] = sl            
            result = mt5.order_send(req)
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                position = self._find_open_position(symbol, lot, trade_type)
                ticket = getattr(position, "ticket", None) if position else None
                entry_price = getattr(position, "price_open", None) if position else price
                mt5.shutdown()
                return {
                    "status": "ok",
                    "order": {
                        **result._asdict(),
                        "ticket": ticket or getattr(result, "order", None) or getattr(result, "deal", None),
                        "price": entry_price,
                        "symbol": symbol,
                        "broker_name": self.broker_name,
                        "account_id": account_id,
                        "lot": lot,
                        "trade_type": trade_type,
                        "tp": tp,
                        "sl": sl,
                    },
                }
            else:
                last_error = f"{result.retcode} {result.comment}"
        mt5.shutdown()
        error_msg = (
            f"Order send failed on {symbol} "
            f"(Broker: {self.broker_name}, Type: {trade_type}, Lot: {lot}, TP: {tp}, SL: {sl}, Price: {price}): {last_error}"
        )   
        log_mt5_error(error_msg, broker_name=self.broker_name, account_id=account_id)
        raise RuntimeError(error_msg)
    
    def close_trade(self, symbol: str, lot: float, ticket: int):
        if not self._initialize():
            raise RuntimeError("MT5 not connected")
        account_id = self._current_account_id()
        position = mt5.positions_get(ticket=ticket)
        if not position:
            mt5.shutdown()
            error_msg = f"No open position with ticket {ticket} (Broker: {self.broker_name}, Symbol: {symbol})"
            log_mt5_error(
                f"close_trade context: broker={self.broker_name}, account_id={account_id}, "
                f"symbol={symbol}, lot={lot}, ticket={ticket}, error=Position not found, source=backend"
            )
            raise RuntimeError(error_msg)
        pos = position[0]
        order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            mt5.shutdown()
            error_msg = f"No tick data for {symbol}"
            log_mt5_error(
                f"close_trade context: broker={self.broker_name}, account_id={account_id}, "
                f"symbol={symbol}, lot={lot}, ticket={ticket}, error=No tick data, source=backend"
            )
            raise RuntimeError(error_msg)
        price = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask
        filling_modes = [mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_RETURN, mt5.ORDER_FILLING_IOC]
        result = None
        last_error = "unknown"
        for filling_mode in filling_modes:
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
                "type_filling": filling_mode,
            }
            result = mt5.order_send(req)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                mt5.shutdown()
                return {"status": "ok", "order": {**result._asdict(), "account_id": account_id, "broker_name": self.broker_name}}
            if result:
                last_error = f"{result.retcode} {result.comment}"
            else:
                last_error = "order_send returned None"

        mt5.shutdown()

        if not result or result.retcode != mt5.TRADE_RETCODE_DONE:
            error_msg = (
                f"Order close failed on {symbol} "
                f"(Broker: {self.broker_name}, Ticket: {ticket}, Lot: {lot}): {last_error}"
            )
            log_mt5_error(
                f"close_trade context: broker={self.broker_name}, account_id={account_id}, symbol={symbol}, "
                f"lot={lot}, ticket={ticket}, last_error={last_error}, tried_filling_modes={filling_modes}, source=backend"
            )
            raise RuntimeError(error_msg)


class MouseAdapter(TerminalAdapter):
    terminal_type = "mouse"

    def __init__(self, window_hint: Optional[str]):
        self.window_hint = window_hint or "FinexBisnisSolusi"

    def open_trade(self, symbol: str, lot: float, trade_type: str, tp: float = None, sl: float = None):
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

    def open_trade(self, symbol: str, lot: float, trade_type: str, tp: float = None, sl: float = None):
        price = 2000.0
        return {
            "status": "ok",
            "order": {
                "ticket": int(time.time()),
                "price": price,
                "symbol": symbol,
                "volume": lot,
                "type": trade_type,
                "tp": tp,
                "sl": sl,
            },
        }

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


def normalize_lot_with_constraints(lot: float, constraints: dict):
    """
    Snap lot into broker-valid min/max/step boundaries.
    Returns a normalized float lot.
    """
    if constraints is None:
        return max(0.01, float(lot))

    step = float(constraints.get("volume_step") or 0)
    minimum = float(constraints.get("volume_min") or 0.01)
    maximum = float(constraints.get("volume_max") or max(minimum, float(lot)))

    value = float(lot)
    if value < minimum:
        value = minimum
    if value > maximum:
        value = maximum

    if step > 0:
        offset_steps = round((value - minimum) / step)
        value = minimum + (offset_steps * step)
        value = min(max(value, minimum), maximum)
        decimals = 0
        step_text = f"{step:.12f}".rstrip("0")
        if "." in step_text:
            decimals = len(step_text.split(".")[1])
        value = round(value, min(max(decimals, 2), 8))

    return value


def get_broker_symbol_constraints(broker, symbol: str = "XAUUSD", auto_start: bool = True):
    broker = broker or {}
    platform = str(broker.get("platform", "mt5")).lower()
    terminal_path = broker.get("terminal_path")
    symbol = str(symbol or "XAUUSD").strip().upper() or "XAUUSD"

    payload = {
        "broker_id": broker.get("id"),
        "broker_name": broker.get("name"),
        "platform": platform,
        "terminal_path": terminal_path,
        "symbol": symbol,
        "can_open_order": False,
        "reason": "unknown",
        "account_id": None,
        "volume_min": None,
        "volume_max": None,
        "volume_step": None,
        "volume_limit": None,
        "digits": None,
        "point": None,
        "tick_size": None,
        "tick_value": None,
        "trade_stops_level": None,
        "trade_freeze_level": None,
        "trade_mode": None,
        "spread": None,
    }

    if platform != "mt5":
        payload["can_open_order"] = True
        payload["reason"] = "non_mt5_platform"
        return payload

    if not terminal_path:
        payload["reason"] = "terminal_path_missing"
        return payload

    if auto_start:
        ensure_terminal_running(terminal_path)

    initialized = False
    try:
        initialized = mt5.initialize(path=terminal_path)
        if not initialized:
            payload["reason"] = "mt5_initialize_failed"
            return payload

        account = mt5.account_info()
        payload["account_id"] = int(getattr(account, "login", 0) or 0) or None

        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            payload["reason"] = "symbol_not_found"
            return payload

        if not bool(getattr(symbol_info, "visible", False)):
            mt5.symbol_select(symbol, True)
            symbol_info = mt5.symbol_info(symbol)

        tick = mt5.symbol_info_tick(symbol)
        terminal_info = mt5.terminal_info()

        payload.update(
            {
                "volume_min": float(getattr(symbol_info, "volume_min", 0) or 0),
                "volume_max": float(getattr(symbol_info, "volume_max", 0) or 0),
                "volume_step": float(getattr(symbol_info, "volume_step", 0) or 0),
                "volume_limit": float(getattr(symbol_info, "volume_limit", 0) or 0),
                "digits": int(getattr(symbol_info, "digits", 0) or 0),
                "point": float(getattr(symbol_info, "point", 0) or 0),
                "tick_size": float(getattr(symbol_info, "trade_tick_size", 0) or 0),
                "tick_value": float(getattr(symbol_info, "trade_tick_value", 0) or 0),
                "trade_stops_level": int(getattr(symbol_info, "trade_stops_level", 0) or 0),
                "trade_freeze_level": int(getattr(symbol_info, "trade_freeze_level", 0) or 0),
                "trade_mode": int(getattr(symbol_info, "trade_mode", 0) or 0),
                "spread": int(getattr(symbol_info, "spread", 0) or 0),
            }
        )

        terminal_connected = bool(getattr(terminal_info, "connected", False)) if terminal_info else False
        terminal_trade_allowed = bool(getattr(terminal_info, "trade_allowed", False)) if terminal_info else False
        account_trade_allowed = bool(getattr(account, "trade_allowed", False)) if account else False
        has_tick = tick is not None

        if not terminal_connected:
            payload["reason"] = "terminal_disconnected"
            return payload
        if not terminal_trade_allowed:
            payload["reason"] = "terminal_trade_disabled"
            return payload
        if not account_trade_allowed:
            payload["reason"] = "account_trade_disabled"
            return payload
        if not has_tick:
            payload["reason"] = "no_tick_data"
            return payload

        payload["can_open_order"] = True
        payload["reason"] = "ready"
        return payload
    except Exception as exc:
        payload["reason"] = f"constraints_failed: {exc}"
        return payload
    finally:
        if initialized:
            mt5.shutdown()


def get_broker_account_metrics(broker, symbol: str = "XAUUSD", auto_start: bool = True):
    broker = broker or {}
    platform = str(broker.get("platform", "mt5")).lower()
    terminal_path = broker.get("terminal_path")
    symbol = str(symbol or "XAUUSD").strip().upper() or "XAUUSD"

    payload = {
        "broker_id": broker.get("id"),
        "broker_name": broker.get("name"),
        "platform": platform,
        "symbol": symbol,
        "can_trade": False,
        "reason": "unknown",
        "account_id": None,
        "balance": None,
        "equity": None,
        "margin": None,
        "margin_free": None,
        "margin_level": None,
        "leverage": None,
        "currency": None,
        "terminal_connected": False,
        "terminal_trade_allowed": False,
        "account_trade_allowed": False,
        "spread_points": None,
        "point": None,
        "tick_size": None,
        "tick_value": None,
        "contract_size": None,
        "estimated_margin_per_lot": None,
    }

    if platform != "mt5":
        payload["can_trade"] = True
        payload["reason"] = "non_mt5_platform"
        return payload

    if not terminal_path:
        payload["reason"] = "terminal_path_missing"
        return payload

    if auto_start:
        ensure_terminal_running(terminal_path)

    initialized = False
    try:
        initialized = mt5.initialize(path=terminal_path)
        if not initialized:
            payload["reason"] = "mt5_initialize_failed"
            return payload

        account = mt5.account_info()
        terminal_info = mt5.terminal_info()
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info and not bool(getattr(symbol_info, "visible", False)):
            mt5.symbol_select(symbol, True)
            symbol_info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)

        payload["terminal_connected"] = bool(getattr(terminal_info, "connected", False)) if terminal_info else False
        payload["terminal_trade_allowed"] = bool(getattr(terminal_info, "trade_allowed", False)) if terminal_info else False
        payload["account_trade_allowed"] = bool(getattr(account, "trade_allowed", False)) if account else False

        payload["account_id"] = int(getattr(account, "login", 0) or 0) or None
        payload["balance"] = float(getattr(account, "balance", 0) or 0) if account else None
        payload["equity"] = float(getattr(account, "equity", 0) or 0) if account else None
        payload["margin"] = float(getattr(account, "margin", 0) or 0) if account else None
        payload["margin_free"] = float(getattr(account, "margin_free", 0) or 0) if account else None
        payload["margin_level"] = float(getattr(account, "margin_level", 0) or 0) if account else None
        payload["leverage"] = int(getattr(account, "leverage", 0) or 0) if account else None
        payload["currency"] = getattr(account, "currency", None) if account else None

        point = float(getattr(symbol_info, "point", 0) or 0) if symbol_info else 0.0
        ask = float(getattr(tick, "ask", 0) or 0) if tick else 0.0
        bid = float(getattr(tick, "bid", 0) or 0) if tick else 0.0
        spread_points = None
        if point > 0 and ask > 0 and bid > 0:
            spread_points = int(round((ask - bid) / point))
        elif symbol_info is not None:
            spread_points = int(getattr(symbol_info, "spread", 0) or 0)

        contract_size = float(getattr(symbol_info, "trade_contract_size", 0) or 0) if symbol_info else 0.0
        leverage = int(payload["leverage"] or 0)
        ref_price = ask if ask > 0 else bid
        estimated_margin_per_lot = None
        if contract_size > 0 and leverage > 0 and ref_price > 0:
            estimated_margin_per_lot = contract_size * ref_price / leverage

        payload.update(
            {
                "spread_points": spread_points,
                "point": point if point > 0 else None,
                "tick_size": float(getattr(symbol_info, "trade_tick_size", 0) or 0) if symbol_info else None,
                "tick_value": float(getattr(symbol_info, "trade_tick_value", 0) or 0) if symbol_info else None,
                "contract_size": contract_size if contract_size > 0 else None,
                "estimated_margin_per_lot": estimated_margin_per_lot,
            }
        )

        if not payload["terminal_connected"]:
            payload["reason"] = "terminal_disconnected"
            return payload
        if not payload["terminal_trade_allowed"]:
            payload["reason"] = "terminal_trade_disabled"
            return payload
        if not payload["account_trade_allowed"]:
            payload["reason"] = "account_trade_disabled"
            return payload
        if tick is None:
            payload["reason"] = "no_tick_data"
            return payload

        payload["can_trade"] = True
        payload["reason"] = "ready"
        return payload
    except Exception as exc:
        payload["reason"] = f"account_metrics_failed: {exc}"
        return payload
    finally:
        if initialized:
            mt5.shutdown()


def get_broker_symbol_tick(broker, symbol: str = "XAUUSD", auto_start: bool = True):
    broker = broker or {}
    platform = str(broker.get("platform", "mt5")).lower()
    terminal_path = broker.get("terminal_path")
    symbol = str(symbol or "XAUUSD").strip().upper() or "XAUUSD"

    payload = {
        "broker_id": broker.get("id"),
        "broker_name": broker.get("name"),
        "platform": platform,
        "symbol": symbol,
        "ready": False,
        "reason": "unknown",
        "bid": None,
        "ask": None,
        "last": None,
        "point": None,
        "time": None,
        "close_buy_price": None,
        "close_sell_price": None,
        "mid": None,
    }

    if platform != "mt5":
        payload["reason"] = "non_mt5_platform"
        return payload

    if not terminal_path:
        payload["reason"] = "terminal_path_missing"
        return payload

    if auto_start:
        ensure_terminal_running(terminal_path)

    initialized = False
    try:
        initialized = mt5.initialize(path=terminal_path)
        if not initialized:
            payload["reason"] = "mt5_initialize_failed"
            return payload

        info = mt5.symbol_info(symbol)
        if not info:
            payload["reason"] = "symbol_not_found"
            return payload
        if not bool(getattr(info, "visible", False)):
            mt5.symbol_select(symbol, True)
            info = mt5.symbol_info(symbol)

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            payload["reason"] = "no_tick_data"
            return payload

        bid = float(getattr(tick, "bid", 0) or 0)
        ask = float(getattr(tick, "ask", 0) or 0)
        last = float(getattr(tick, "last", 0) or 0)
        point = float(getattr(info, "point", 0) or 0)

        payload.update(
            {
                "ready": True,
                "reason": "ready",
                "bid": bid if bid > 0 else None,
                "ask": ask if ask > 0 else None,
                "last": last if last > 0 else None,
                "point": point if point > 0 else None,
                "time": int(getattr(tick, "time", 0) or 0) or None,
                "close_buy_price": bid if bid > 0 else None,
                "close_sell_price": ask if ask > 0 else None,
                "mid": ((bid + ask) / 2.0) if bid > 0 and ask > 0 else None,
            }
        )
        return payload
    except Exception as exc:
        payload["reason"] = f"tick_failed: {exc}"
        return payload
    finally:
        if initialized:
            mt5.shutdown()


def _mt5_account_id(account):
    login = getattr(account, "login", None) if account else None
    return int(login) if login is not None else None


def _trade_type_from_position(position_type):
    return "BUY" if position_type == mt5.POSITION_TYPE_BUY else "SELL"


def _trade_type_from_deal(deal_type):
    return "BUY" if deal_type == mt5.DEAL_TYPE_BUY else "SELL"


def _weighted_price(deals):
    total_volume = sum(float(getattr(deal, "volume", 0) or 0) for deal in deals)
    if total_volume <= 0:
        return None
    total_value = sum(float(getattr(deal, "price", 0) or 0) * float(getattr(deal, "volume", 0) or 0) for deal in deals)
    return total_value / total_volume


def _derive_tp_sl_values(position):
    entry = float(getattr(position, "price_open", 0) or 0)
    if entry <= 0:
        return None, None
    tp_price = float(getattr(position, "tp", 0) or 0)
    sl_price = float(getattr(position, "sl", 0) or 0)
    tp_value = abs(tp_price - entry) if tp_price > 0 else None
    sl_value = abs(sl_price - entry) if sl_price > 0 else None
    return tp_value, sl_value


def _sync_trade_id(broker_id, account_id, ticket):
    return f"terminal-sync:{broker_id}:{account_id or 'unknown'}:{ticket}"


def _group_deals_by_position(deals):
    grouped = {}
    for deal in deals or []:
        position_id = int(getattr(deal, "position_id", 0) or 0)
        if position_id <= 0:
            continue
        grouped.setdefault(position_id, []).append(deal)
    for items in grouped.values():
        items.sort(key=lambda deal: (int(getattr(deal, "time", 0) or 0), int(getattr(deal, "ticket", 0) or 0)))
    return grouped


def _build_open_trade_from_position(broker, account_id, position, deals_for_position=None):
    tp_value, sl_value = _derive_tp_sl_values(position)
    ticket = int(getattr(position, "ticket", 0) or 0)
    entry_time = int(getattr(position, "time", 0) or 0) or int(time.time())
    entry_price = float(getattr(position, "price_open", 0) or 0)
    if (not entry_price) and deals_for_position:
        entry_deals = [deal for deal in deals_for_position if getattr(deal, "entry", None) == mt5.DEAL_ENTRY_IN]
        entry_price = _weighted_price(entry_deals) or entry_price
        if not entry_time and entry_deals:
            entry_time = int(getattr(entry_deals[0], "time", 0) or 0)
    return {
        "trade_id": _sync_trade_id(broker.get("id"), account_id, ticket),
        "status": "open",
        "type": _trade_type_from_position(getattr(position, "type", None)),
        "symbol": getattr(position, "symbol", None),
        "lot": float(getattr(position, "volume", 0) or 0),
        "ticket": ticket,
        "entry": entry_price,
        "profit": float(getattr(position, "profit", 0) or 0),
        "entryTime": entry_time,
        "exitTime": None,
        "reason": "terminal_sync_open",
        "tpValue": tp_value,
        "slValue": sl_value,
        "broker_id": broker.get("id"),
        "broker_name": broker.get("name"),
        "account_id": account_id,
        "platform": broker.get("platform"),
        "execution_mode": broker.get("execution_mode"),
        "terminal_path": broker.get("terminal_path"),
    }


def _build_closed_trade_from_deals(broker, account_id, ticket, deals_for_position):
    entry_deals = [deal for deal in deals_for_position if getattr(deal, "entry", None) == mt5.DEAL_ENTRY_IN]
    exit_values = {mt5.DEAL_ENTRY_OUT}
    deal_entry_out_by = getattr(mt5, "DEAL_ENTRY_OUT_BY", None)
    if deal_entry_out_by is not None:
        exit_values.add(deal_entry_out_by)
    exit_deals = [deal for deal in deals_for_position if getattr(deal, "entry", None) in exit_values]
    if not entry_deals or not exit_deals:
        return None

    first_entry = entry_deals[0]
    last_exit = exit_deals[-1]
    return {
        "trade_id": _sync_trade_id(broker.get("id"), account_id, ticket),
        "status": "closed",
        "type": _trade_type_from_deal(getattr(first_entry, "type", None)),
        "symbol": getattr(first_entry, "symbol", None),
        "lot": sum(float(getattr(deal, "volume", 0) or 0) for deal in entry_deals) or float(getattr(first_entry, "volume", 0) or 0),
        "ticket": int(ticket),
        "entry": _weighted_price(entry_deals),
        "exit": _weighted_price(exit_deals),
        "profit": sum(float(getattr(deal, "profit", 0) or 0) for deal in deals_for_position),
        "entryTime": int(getattr(first_entry, "time", 0) or 0) or None,
        "exitTime": int(getattr(last_exit, "time", 0) or 0) or None,
        "reason": "terminal_sync_closed",
        "tpValue": None,
        "slValue": None,
        "broker_id": broker.get("id"),
        "broker_name": broker.get("name"),
        "account_id": account_id,
        "platform": broker.get("platform"),
        "execution_mode": broker.get("execution_mode"),
        "terminal_path": broker.get("terminal_path"),
    }


def _fetch_history_deals_resilient(broker, from_date, to_date):
    broker_id = broker.get("id")
    broker_name = broker.get("name")

    try:
        deals_raw = mt5.history_deals_get(from_date, to_date)
        if deals_raw is not None:
            return list(deals_raw), True, "ok"
        err = mt5.last_error()
        primary_error = (
            f"history_deals_get failed [phase=primary, from={from_date.isoformat()}, "
            f"to={to_date.isoformat()}, last_error={err}]"
        )
        _log_mt5_error_throttled(
            primary_error,
            broker_id=broker_id,
            broker_name=broker_name,
            key=f"deals_primary_failed:{broker_id}:{err}",
            cooldown_sec=45,
        )
    except Exception as exc:
        err = mt5.last_error()
        primary_error = (
            f"history_deals_get exception [phase=primary, from={from_date.isoformat()}, "
            f"to={to_date.isoformat()}, exc={exc}, last_error={err}]"
        )
        _log_mt5_error_throttled(
            primary_error,
            broker_id=broker_id,
            broker_name=broker_name,
            key=f"deals_primary_exception:{broker_id}:{err}",
            cooldown_sec=45,
        )

    # Fallback: query in smaller windows to avoid MT5 API failures on large ranges.
    cursor = from_date
    chunk_size_days = 7
    merged = []
    fallback_errors = []
    while cursor < to_date:
        chunk_end = min(cursor + timedelta(days=chunk_size_days), to_date)
        try:
            chunk_raw = mt5.history_deals_get(cursor, chunk_end)
            if chunk_raw is None:
                err = mt5.last_error()
                fallback_errors.append(f"{cursor.isoformat()}..{chunk_end.isoformat()}: {err}")
            else:
                merged.extend(list(chunk_raw))
        except Exception as exc:
            fallback_errors.append(f"{cursor.isoformat()}..{chunk_end.isoformat()}: {exc}")
        cursor = chunk_end + timedelta(seconds=1)

    if merged:
        return merged, True, "chunked"

    if fallback_errors:
        _log_mt5_error_throttled(
            "history_deals_get fallback failed [phase=chunked, from="
            f"{from_date.isoformat()}, to={to_date.isoformat()}]: " + " | ".join(fallback_errors[:4]),
            broker_id=broker_id,
            broker_name=broker_name,
            key=f"deals_fallback_failed:{broker_id}:{fallback_errors[0] if fallback_errors else 'unknown'}",
            cooldown_sec=45,
        )
    return [], False, primary_error


def sync_broker_trade_state(broker, history_days: Optional[int] = 90):
    broker = broker or {}
    if str(broker.get("platform", "mt5")).lower() != "mt5":
        return {"broker_id": broker.get("id"), "synced": False, "reason": "non_mt5_platform"}

    terminal_path = broker.get("terminal_path")
    if not terminal_path:
        return {"broker_id": broker.get("id"), "synced": False, "reason": "terminal_path_missing"}

    ensure_terminal_running(terminal_path)
    initialized = False
    saved_count = 0
    errors = []
    try:
        initialized = mt5.initialize(path=terminal_path)
        if not initialized:
            log_mt5_error(
                f"Failed to initialize MT5 for trade sync: {broker.get('name')}",
                broker_id=broker.get("id"),
                broker_name=broker.get("name"),
            )
            return {"broker_id": broker.get("id"), "synced": False, "reason": "mt5_initialize_failed"}

        account = mt5.account_info()
        if account is None:
            return {"broker_id": broker.get("id"), "synced": False, "reason": "account_info_failed"}
        account_id = _mt5_account_id(account)
        positions = list(mt5.positions_get() or [])

        if history_days is None:
            from_date = datetime(1970, 1, 1)
        else:
            from_date = datetime.now() - timedelta(days=max(1, int(history_days)))
        to_date = datetime.now() - timedelta(seconds=1)
        deals, deals_ok, deals_fetch_mode = _fetch_history_deals_resilient(broker, from_date, to_date)


        deals_by_position = _group_deals_by_position(deals)
        live_tickets = set()


        for position in positions:
            ticket = int(getattr(position, "ticket", 0) or 0)
            if ticket <= 0:
                continue
            live_tickets.add(ticket)
            trade = _build_open_trade_from_position(broker, account_id, position, deals_by_position.get(ticket, []))
            try:
                upsert_trade_history_record(trade)
                saved_count += 1
            except Exception as e:
                errors.append({"trade_id": trade.get("trade_id"), "error": str(e)})

        for ticket, deals_for_position in deals_by_position.items():
            if ticket in live_tickets:
                continue
            summary = _build_closed_trade_from_deals(broker, account_id, ticket, deals_for_position)
            if summary:
                try:
                    upsert_trade_history_record(summary)
                    saved_count += 1
                except Exception as e:
                    errors.append({"trade_id": summary.get("trade_id"), "error": str(e)})

        for row in list_open_trades(broker_id=broker.get("id")):
            row_account_id = row.get("account_id")
            if account_id is not None and row_account_id not in (None, account_id):
                continue
            ticket = int(row.get("ticket") or 0)
            if ticket > 0 and ticket in live_tickets:
                continue

            closed_summary = None
            if ticket > 0:
                closed_summary = _build_closed_trade_from_deals(broker, account_id, ticket, deals_by_position.get(ticket, []))
            if closed_summary:
                closed_summary["trade_id"] = row.get("trade_id") or closed_summary.get("trade_id")
                closed_summary["tpValue"] = row.get("tpValue") if closed_summary.get("tpValue") is None else closed_summary.get("tpValue")
                closed_summary["slValue"] = row.get("slValue") if closed_summary.get("slValue") is None else closed_summary.get("slValue")
                upsert_trade_history_record(closed_summary)
                continue

            upsert_trade_history_record(
                {
                    "trade_id": row.get("trade_id") or _sync_trade_id(broker.get("id"), account_id, ticket or f"missing-{row.get('symbol')}-{row.get('entryTime') or 0}"),
                    "status": "closed",
                    "type": row.get("type"),
                    "symbol": row.get("symbol"),
                    "lot": row.get("lot"),
                    "ticket": row.get("ticket"),
                    "entry": row.get("entry"),
                    "exit": row.get("exit"),
                    "profit": row.get("profit"),
                    "entryTime": row.get("entryTime"),
                    "exitTime": int(time.time()),
                    "reason": "terminal_sync_missing",
                    "tpValue": row.get("tpValue"),
                    "slValue": row.get("slValue"),
                    "broker_id": broker.get("id"),
                    "broker_name": broker.get("name"),
                    "account_id": account_id,
                    "platform": broker.get("platform"),
                    "execution_mode": row.get("execution_mode") or broker.get("execution_mode"),
                    "terminal_path": broker.get("terminal_path"),
                }
            )

        had_upsert_errors = len(errors) > 0
        partial = (not deals_ok) or had_upsert_errors
        sync_reason = "ok"
        if not deals_ok:
            sync_reason = "history_deals_fetch_failed"
        elif had_upsert_errors:
            sync_reason = "upsert_failed"

        return {
            "broker_id": broker.get("id"),
            "broker_name": broker.get("name"),
            "account_id": account_id,
            "synced": not partial,
            "partial": partial,
            "reason": sync_reason,
            "open_positions": len(live_tickets),
            "history_deals": len(deals),
            "history_fetch_mode": deals_fetch_mode,
            "saved_count": saved_count,
            "errors": errors,
        }
    except Exception as exc:
        _log_mt5_error_throttled(
            f"Terminal sync failed for broker {broker.get('name')}: {exc}",
            broker_id=broker.get("id"),
            broker_name=broker.get("name"),
            key=f"terminal_sync_failed:{broker.get('id')}:{exc}",
            cooldown_sec=45,
        )
        return {"broker_id": broker.get("id"), "synced": False, "reason": str(exc)}
    finally:
        if initialized:
            mt5.shutdown()


def sync_all_terminal_trade_state(history_days: Optional[int] = 90):
    results = []
    for broker in list_brokers(include_inactive=False):
        if str(broker.get("platform", "mt5")).lower() != "mt5":
            continue
        results.append(sync_broker_trade_state(broker, history_days=history_days))
    return results
