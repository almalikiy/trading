#file: trading_bot/app/terminal_adapters.py
from __future__ import annotations

import os
import subprocess
import threading
import time
from datetime import datetime, timedelta
from typing import Any

from trading_bot.app import db
from trading_bot.app.logic import close_real_trade, fetch_ohlcv, open_real_trade

try:  # pragma: no cover - runtime dependency
    import MetaTrader5 as mt5
except Exception:  # pragma: no cover
    mt5 = None


_PROCESS_PATHS_CACHE: dict[str, Any] = {"data": set(), "expires_at": 0.0}
_PROCESS_CACHE_LOCK = threading.Lock()
_BROKER_STATUS_CACHE: dict[tuple[Any, Any], dict[str, Any]] = {}
_BROKER_STATUS_REFRESHING: set[tuple[Any, Any]] = set()
_BROKER_STATUS_LOCK = threading.Lock()
_SYNC_ERROR_THROTTLE: dict[str, float] = {}
_SYNC_ERROR_LOCK = threading.Lock()
_MT5_LOCK = threading.Lock()
_BACKGROUND_SYNC_LOCK = threading.Lock()
_BACKGROUND_SYNC_STATE: dict[str, Any] = {
    "status": "idle",
    "queued_at": None,
    "started_at": None,
    "finished_at": None,
    "error": None,
    "last_result": None,
}
_KEEP_MT5_ALIVE_LOCK = threading.Lock()
_KEEP_MT5_ALIVE_STOP = threading.Event()
_KEEP_MT5_ALIVE_THREAD: threading.Thread | None = None
_KEEP_MT5_ALIVE_STATE: dict[str, Any] = {
    "enabled": False,
    "status": "disabled",
    "last_checked_at": None,
    "broker_name": None,
    "terminal_path": None,
    "message": "Keep MT5 alive is disabled.",
}


def _normalize_terminal_time_offset_seconds(raw_offset_sec: Any) -> int:
    try:
        raw = int(raw_offset_sec)
    except Exception:
        return 0

    candidates = [raw - (86400 * day_shift) for day_shift in range(-2, 3)]
    bounded = [value for value in candidates if abs(value) <= (15 * 3600)]
    if bounded:
        return min(bounded, key=lambda value: abs(value))
    return raw


def normalize_terminal_time_offset_seconds(raw_offset_sec: Any) -> int:
    return _normalize_terminal_time_offset_seconds(raw_offset_sec)


def calibrate_terminal_epoch_for_display(epoch_seconds: Any, offset_seconds: Any) -> int | None:
    try:
        ts = int(epoch_seconds or 0)
    except Exception:
        ts = 0
    if ts <= 0:
        return None
    try:
        return int(ts + int(offset_seconds or 0))
    except Exception:
        return ts


def _list_process_paths() -> set[str]:
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
        lines = [line.strip() for line in out.splitlines() if line and line.strip()]
        paths = set()
        for line in lines:
            try:
                if os.path.exists(line):
                    paths.add(os.path.normcase(os.path.abspath(line)))
            except Exception:
                continue
        with _PROCESS_CACHE_LOCK:
            _PROCESS_PATHS_CACHE["data"] = paths
            _PROCESS_PATHS_CACHE["expires_at"] = time.monotonic() + 3.0
        return paths
    except Exception:
        with _PROCESS_CACHE_LOCK:
            _PROCESS_PATHS_CACHE["data"] = set()
            _PROCESS_PATHS_CACHE["expires_at"] = time.monotonic() + 1.0
        return set()


def _safe_mt5_shutdown() -> None:
    if mt5 is None:
        return
    try:
        with _MT5_LOCK:
            mt5.shutdown()
    except Exception:
        pass


def _normalize_terminal_path_value(path_value: Any) -> str | None:
    try:
        text = str(path_value or "").strip()
    except Exception:
        return None
    if not text:
        return None
    return os.path.normcase(os.path.abspath(text))


def _default_broker_terminal_path() -> str | None:
    try:
        default_broker = db.get_default_broker() or {}
    except Exception:
        default_broker = {}
    return _normalize_terminal_path_value(default_broker.get("terminal_path"))


def _allows_backend_terminal_autostart(terminal_path: str | None, *, broker: dict[str, Any] | None = None) -> bool:
    if not terminal_path:
        return False
    normalized = _normalize_terminal_path_value(terminal_path)
    if not normalized:
        return False
    if not _is_keep_terminal_alive_enabled():
        return False
    default_path = _default_broker_terminal_path()
    if default_path and normalized == default_path:
        return True
    if broker and bool(broker.get("is_default")):
        return True
    return False


def ensure_terminal_running(terminal_path: str | None, *, force: bool = False, broker: dict[str, Any] | None = None) -> bool:
    if not terminal_path:
        return False
    if not _allows_backend_terminal_autostart(terminal_path, broker=broker):
        return False
    if force and not _is_keep_terminal_alive_enabled():
        return False
    normalized = os.path.normcase(os.path.abspath(terminal_path))
    for proc in _list_process_paths():
        if proc == normalized:
            return True
    try:
        subprocess.Popen([terminal_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def _get_active_mt5_terminal_target() -> tuple[str | None, str | None]:
    try:
        state = db.get_account_state()
    except Exception:
        state = {}
    broker = db.resolve_feed_broker(state=state, require_terminal_path=False) or db.get_default_broker()
    if not broker:
        return None, None
    if str(broker.get("platform", "mt5")).lower() != "mt5":
        return None, None
    return broker.get("terminal_path"), broker.get("name")


def _is_keep_terminal_alive_enabled(state: dict[str, Any] | None = None) -> bool:
    runtime_enabled = bool(_KEEP_MT5_ALIVE_STATE.get("enabled", False))

    try:
        current = db.get_account_state() if state is None else state
    except Exception:
        current = state or {}

    if not isinstance(current, dict):
        return runtime_enabled

    persisted_enabled = bool(current.get("keep_terminal_alive", False))
    return bool(runtime_enabled or persisted_enabled)


def _keep_mt5_alive_loop() -> None:
    while not _KEEP_MT5_ALIVE_STOP.is_set():
        try:
            enabled = bool(_KEEP_MT5_ALIVE_STATE.get("enabled", False))
            if not enabled:
                _KEEP_MT5_ALIVE_STATE["status"] = "disabled"
                _KEEP_MT5_ALIVE_STATE["message"] = "Keep MT5 alive is disabled."
                break
            terminal_path, broker_name = _get_active_mt5_terminal_target()
            if not terminal_path:
                _KEEP_MT5_ALIVE_STATE.update({
                    "status": "idle",
                    "broker_name": broker_name,
                    "terminal_path": None,
                    "last_checked_at": time.time(),
                    "message": "No active MT5 terminal path found for keep-alive monitoring.",
                })
            else:
                started = ensure_terminal_running(terminal_path, force=True, broker={"is_default": True})
                _KEEP_MT5_ALIVE_STATE.update({
                    "status": "running" if started else "failed",
                    "broker_name": broker_name,
                    "terminal_path": terminal_path,
                    "last_checked_at": time.time(),
                    "message": f"MT5 terminal check completed. started={started}",
                })
        except Exception as exc:
            _KEEP_MT5_ALIVE_STATE.update({
                "status": "failed",
                "broker_name": None,
                "terminal_path": None,
                "last_checked_at": time.time(),
                "message": str(exc),
            })
        _KEEP_MT5_ALIVE_STOP.wait(15.0)


def set_keep_mt5_alive(enabled: bool) -> dict[str, Any]:
    enabled = bool(enabled)
    state = db.get_account_state()
    state["keep_terminal_alive"] = enabled
    db.save_account_state(state)
    with _KEEP_MT5_ALIVE_LOCK:
        _KEEP_MT5_ALIVE_STATE["enabled"] = enabled
        _KEEP_MT5_ALIVE_STATE["status"] = "running" if enabled else "disabled"
        _KEEP_MT5_ALIVE_STATE["message"] = "Keep MT5 alive is enabled." if enabled else "Keep MT5 alive is disabled."
        _KEEP_MT5_ALIVE_STATE["last_checked_at"] = time.time()
    if enabled:
        global _KEEP_MT5_ALIVE_THREAD
        _KEEP_MT5_ALIVE_STOP.clear()
        if (_KEEP_MT5_ALIVE_THREAD is None) or (not _KEEP_MT5_ALIVE_THREAD.is_alive()):
            thread = threading.Thread(target=_keep_mt5_alive_loop, name="mt5-keepalive", daemon=True)
            _KEEP_MT5_ALIVE_THREAD = thread
            thread.start()
    else:
        _KEEP_MT5_ALIVE_STOP.set()
        _KEEP_MT5_ALIVE_STATE["status"] = "disabled"
    return get_keep_mt5_alive_status()


def get_keep_mt5_alive_status() -> dict[str, Any]:
    try:
        state = db.get_account_state()
    except Exception:
        state = {}
    enabled = bool(state.get("keep_terminal_alive", _KEEP_MT5_ALIVE_STATE.get("enabled", False)))
    with _KEEP_MT5_ALIVE_LOCK:
        payload = {
            "enabled": enabled,
            "status": _KEEP_MT5_ALIVE_STATE.get("status", "disabled"),
            "last_checked_at": _KEEP_MT5_ALIVE_STATE.get("last_checked_at"),
            "broker_name": _KEEP_MT5_ALIVE_STATE.get("broker_name"),
            "terminal_path": _KEEP_MT5_ALIVE_STATE.get("terminal_path"),
            "message": _KEEP_MT5_ALIVE_STATE.get("message", "Keep MT5 alive is disabled."),
        }
    payload["enabled"] = enabled
    return payload


def _log_mt5_error_throttled(message: str, *, broker_id: Any = None, broker_name: Any = None, account_id: Any = None, key: str | None = None, cooldown_sec: float = 30.0) -> bool:
    now = time.time()
    throttle_key = key or f"{broker_id}:{broker_name}:{message}"
    with _SYNC_ERROR_LOCK:
        last_ts = _SYNC_ERROR_THROTTLE.get(throttle_key, 0.0)
        if now - last_ts < float(cooldown_sec):
            return False
        _SYNC_ERROR_THROTTLE[throttle_key] = now

    db.log_mt5_error(message, broker_id=broker_id, broker_name=broker_name, account_id=account_id)
    return True


def _build_mt5_call_notice(*, call_name: str, strategy_related: bool) -> dict[str, Any]:
    if strategy_related:
        return {
            "call_classification": "frequent_strategy",
            "strategy_related": True,
            "notice": "This MT5 call is required for live trade strategy monitoring and can run when trade logic needs current market data.",
        }
    return {
        "call_classification": "rare_operational",
        "strategy_related": False,
        "notice": "This is a non-strategy MT5 operational check. It is deferred by default to avoid interfering with active trading and will only run after explicit user confirmation.",
    }


def _defer_non_strategy_mt5_check(*, call_name: str, payload: dict[str, Any], strategy_related: bool) -> bool:
    if strategy_related:
        return False
    notice = _build_mt5_call_notice(call_name=call_name, strategy_related=False)
    payload.update({
        "call_classification": notice["call_classification"],
        "strategy_related": notice["strategy_related"],
        "notice": notice["notice"],
        "reason": "deferred_non_strategy_check",
    })
    return True


def _check_mt5_non_strategy_confirmation(*, call_name: str, payload: dict[str, Any], strategy_related: bool) -> bool:
    if strategy_related:
        return False
    try:
        state = db.get_account_state()
    except Exception:
        state = {}
    if not isinstance(state, dict):
        state = {}
    require_confirmation = bool(state.get("mt5_non_strategy_require_confirmation", True))
    if not require_confirmation:
        return False
    confirmation_key = f"mt5_confirmed_{call_name}"
    confirmed = bool(state.get(confirmation_key, False))
    if confirmed:
        state[confirmation_key] = False
        try:
            db.save_account_state(state)
        except Exception:
            pass
        return False
    notice = _build_mt5_call_notice(call_name=call_name, strategy_related=False)
    payload.update({
        "call_classification": notice["call_classification"],
        "strategy_related": notice["strategy_related"],
        "notice": f"{notice['notice']} User confirmation is required before this operational MT5 check executes.",
        "reason": "confirmation_required",
        "requires_confirmation": True,
        "confirmation_required": True,
        "call_name": call_name,
    })
    return True


class TerminalAdapter:
    terminal_type = "simulation"

    def open_trade(self, symbol: str, lot: float, trade_type: str, tp: float | None = None, sl: float | None = None):
        raise NotImplementedError

    def close_trade(self, symbol: str, lot: float, ticket: int):
        raise NotImplementedError

    def fetch_ohlcv(self, symbol: str, timeframe: str, bars: int):
        return fetch_ohlcv(symbol, timeframe, bars=bars)


class MT5Adapter(TerminalAdapter):
    terminal_type = "mt5"

    def __init__(self, terminal_path: str | None, broker_name: str):
        self.terminal_path = terminal_path
        self.broker_name = broker_name

    def open_trade(self, symbol: str, lot: float, trade_type: str, tp: float | None = None, sl: float | None = None):
        del tp, sl
        return open_real_trade(symbol=symbol, lot=lot, trade_type=trade_type, terminal_path=self.terminal_path)

    def close_trade(self, symbol: str, lot: float, ticket: int):
        return close_real_trade(symbol=symbol, lot=lot, ticket=ticket, terminal_path=self.terminal_path)


class MouseAdapter(TerminalAdapter):
    terminal_type = "mouse"

    def __init__(self, window_hint: str | None):
        self.window_hint = window_hint or "FinexBisnisSolusi"

    def open_trade(self, symbol: str, lot: float, trade_type: str, tp: float | None = None, sl: float | None = None):
        del symbol, lot, tp, sl
        proc = subprocess.run(
            [
                "python",
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "app", "pyautogui_order.py"),
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

    def open_trade(self, symbol: str, lot: float, trade_type: str, tp: float | None = None, sl: float | None = None):
        return {
            "status": "ok",
            "order": {
                "ticket": int(time.time()),
                "price": 2000.0,
                "symbol": symbol,
                "volume": lot,
                "type": trade_type,
                "tp": tp,
                "sl": sl,
            },
        }

    def close_trade(self, symbol: str, lot: float, ticket: int):
        return {"status": "ok", "order": {"ticket": ticket, "price": 2000.0, "symbol": symbol, "volume": lot}}


def get_broker_adapter(broker: dict[str, Any] | None, order_method: str | None = None):
    payload = broker or {}
    platform = str(payload.get("platform", "mt5")).lower()
    method = str(order_method or payload.get("execution_mode", "mouse")).lower()
    if platform == "simulation":
        return SimulationAdapter(), method
    if method == "mouse":
        return MouseAdapter(payload.get("window_hint")), method
    if platform == "mt5":
        return MT5Adapter(payload.get("terminal_path"), payload.get("name", "unknown")), method
    if platform == "mt4":
        return MouseAdapter(payload.get("window_hint")), "mouse"
    return SimulationAdapter(), "simulation"


def probe_broker_order_status(broker: dict[str, Any] | None, symbol: str = "XAUUSD", auto_start: bool = False) -> dict[str, Any]:
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
    status.update(_build_mt5_call_notice(call_name="probe_broker_order_status", strategy_related=False))

    if _check_mt5_non_strategy_confirmation(call_name="probe_broker_order_status", payload=status, strategy_related=False):
        return status

    if platform != "mt5" or mt5 is None:
        status["can_open_order"] = True
        status["reason"] = "non_mt5_platform"
        status["checks"] = {"platform_supported": False}
        return status

    if not terminal_path:
        status["reason"] = "terminal_path_missing"
        return status

    if auto_start and _is_keep_terminal_alive_enabled():
        started = ensure_terminal_running(terminal_path, force=True, broker={"is_default": True})
        status["checks"]["terminal_process_running"] = bool(started)

    initialized = False
    try:
        with _MT5_LOCK:
            initialized = bool(mt5.initialize(path=terminal_path))
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
            _safe_mt5_shutdown()


def get_broker_order_status_snapshot(broker: dict[str, Any] | None, symbol: str = "XAUUSD") -> dict[str, Any]:
    broker = broker or {}
    cache_key = (broker.get("id"), symbol)

    def refresh_worker() -> None:
        try:
            status = probe_broker_order_status(broker, symbol=symbol, auto_start=False)
        except Exception as exc:  # pragma: no cover - defensive guard for runtime shutdown
            status = {
                "broker_id": broker.get("id"),
                "broker_name": broker.get("name"),
                "platform": str(broker.get("platform", "mt5")).lower(),
                "terminal_path": broker.get("terminal_path"),
                "can_open_order": False,
                "reason": f"status_refresh_failed: {exc}",
                "checks": {},
            }
        with _BROKER_STATUS_LOCK:
            _BROKER_STATUS_CACHE[cache_key] = {"data": status, "updated_at": time.time()}
            _BROKER_STATUS_REFRESHING.discard(cache_key)

    with _BROKER_STATUS_LOCK:
        cached = _BROKER_STATUS_CACHE.get(cache_key)
        refreshing = cache_key in _BROKER_STATUS_REFRESHING
        if not refreshing:
            _BROKER_STATUS_REFRESHING.add(cache_key)
            worker = threading.Thread(target=refresh_worker, name=f"mt5-status-{broker.get('id')}-{symbol}", daemon=True)
            worker.start()

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


def normalize_lot_with_constraints(lot: float, constraints: dict[str, Any] | None):
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
        step_text = f"{step:.12f}".rstrip("0")
        decimals = len(step_text.split(".")[1]) if "." in step_text else 0
        value = round(value, min(max(decimals, 2), 8))
    return value


def get_broker_symbol_constraints(broker: dict[str, Any] | None, symbol: str = "XAUUSD", auto_start: bool = False) -> dict[str, Any]:
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
    payload.update(_build_mt5_call_notice(call_name="get_broker_symbol_constraints", strategy_related=False))
    if _check_mt5_non_strategy_confirmation(call_name="get_broker_symbol_constraints", payload=payload, strategy_related=False):
        return payload
    if platform != "mt5" or mt5 is None:
        payload["can_open_order"] = True
        payload["reason"] = "non_mt5_platform"
        return payload
    if not terminal_path:
        payload["reason"] = "terminal_path_missing"
        return payload
    if auto_start and _is_keep_terminal_alive_enabled():
        ensure_terminal_running(terminal_path)
    initialized = False
    try:
        with _MT5_LOCK:
            initialized = bool(mt5.initialize(path=terminal_path))
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
            if not bool(getattr(terminal_info, "connected", False)):
                payload["reason"] = "terminal_disconnected"
                return payload
            if not bool(getattr(terminal_info, "trade_allowed", False)):
                payload["reason"] = "terminal_trade_disabled"
                return payload
            if not bool(getattr(account, "trade_allowed", False)):
                payload["reason"] = "account_trade_disabled"
                return payload
            if tick is None:
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
            _safe_mt5_shutdown()


def get_broker_account_metrics(broker: dict[str, Any] | None, symbol: str = "XAUUSD", auto_start: bool = False) -> dict[str, Any]:
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
    payload.update(_build_mt5_call_notice(call_name="get_broker_account_metrics", strategy_related=False))
    if _check_mt5_non_strategy_confirmation(call_name="get_broker_account_metrics", payload=payload, strategy_related=False):
        return payload
    if platform != "mt5" or mt5 is None:
        payload["can_trade"] = True
        payload["reason"] = "non_mt5_platform"
        return payload
    if not terminal_path:
        payload["reason"] = "terminal_path_missing"
        return payload
    if auto_start and _is_keep_terminal_alive_enabled():
        ensure_terminal_running(terminal_path)
    initialized = False
    try:
        with _MT5_LOCK:
            initialized = bool(mt5.initialize(path=terminal_path))
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
            _safe_mt5_shutdown()


def get_broker_symbol_tick(broker: dict[str, Any] | None, symbol: str = "XAUUSD", auto_start: bool = False) -> dict[str, Any]:
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
    payload.update(_build_mt5_call_notice(call_name="get_broker_symbol_tick", strategy_related=True))
    if platform != "mt5" or mt5 is None:
        payload["reason"] = "non_mt5_platform"
        return payload
    if not terminal_path:
        payload["reason"] = "terminal_path_missing"
        return payload
    if auto_start and _is_keep_terminal_alive_enabled():
        ensure_terminal_running(terminal_path)
    initialized = False
    try:
        with _MT5_LOCK:
            initialized = bool(mt5.initialize(path=terminal_path))
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
            _safe_mt5_shutdown()


def estimate_broker_time_offset_seconds(broker: dict[str, Any] | None, symbol: str = "XAUUSD", auto_start: bool = False):
    broker = broker or {}
    if str(broker.get("platform", "mt5")).lower() != "mt5":
        return 0, None
    tick_payload = get_broker_symbol_tick(broker, symbol=symbol, auto_start=auto_start)
    tick_epoch = int(tick_payload.get("time") or 0)
    if not tick_payload.get("ready") or tick_epoch <= 0:
        return 0, None
    raw_offset = int(time.time()) - tick_epoch
    return _normalize_terminal_time_offset_seconds(raw_offset), tick_epoch


def _trade_type_from_position(position_type: Any) -> str:
    return "BUY" if mt5 is not None and position_type == mt5.POSITION_TYPE_BUY else "SELL"


def _trade_type_from_deal(deal_type: Any) -> str:
    return "BUY" if mt5 is not None and deal_type == mt5.DEAL_TYPE_BUY else "SELL"


def _weighted_price(deals: list[Any]) -> float | None:
    total_volume = sum(float(getattr(deal, "volume", 0) or 0) for deal in deals)
    if total_volume <= 0:
        return None
    total_value = sum(float(getattr(deal, "price", 0) or 0) * float(getattr(deal, "volume", 0) or 0) for deal in deals)
    return total_value / total_volume


def _derive_tp_sl_values(position: Any):
    entry = float(getattr(position, "price_open", 0) or 0)
    if entry <= 0:
        return None, None
    tp_price = float(getattr(position, "tp", 0) or 0)
    sl_price = float(getattr(position, "sl", 0) or 0)
    tp_value = abs(tp_price - entry) if tp_price > 0 else None
    sl_value = abs(sl_price - entry) if sl_price > 0 else None
    return tp_value, sl_value


def _sync_trade_id(broker_id: Any, account_id: Any, ticket: Any) -> str:
    return f"terminal-sync:{broker_id}:{account_id or 'unknown'}:{ticket}"


def _group_deals_by_position(deals: list[Any]):
    grouped: dict[int, list[Any]] = {}
    for deal in deals or []:
        position_id = int(getattr(deal, "position_id", 0) or 0)
        if position_id <= 0:
            continue
        grouped.setdefault(position_id, []).append(deal)
    for items in grouped.values():
        items.sort(key=lambda deal: (int(getattr(deal, "time", 0) or 0), int(getattr(deal, "ticket", 0) or 0)))
    return grouped


def _build_open_trade_from_position(broker: dict[str, Any], account_id: Any, position: Any, deals_for_position: list[Any] | None = None):
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


def _build_closed_trade_from_deals(broker: dict[str, Any], account_id: Any, ticket: Any, deals_for_position: list[Any]):
    if mt5 is None:
        return None
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


def _fetch_history_deals_resilient(broker: dict[str, Any], from_date: datetime, to_date: datetime):
    broker_id = broker.get("id")
    broker_name = broker.get("name")
    primary_error = "history_deals_get_failed"
    try:
        deals_raw = mt5.history_deals_get(from_date, to_date) if mt5 is not None else []
        if deals_raw is not None:
            return list(deals_raw), True, "ok"
        err = mt5.last_error() if mt5 is not None else "mt5_unavailable"
        primary_error = f"history_deals_get failed [phase=primary, from={from_date.isoformat()}, to={to_date.isoformat()}, last_error={err}]"
        _log_mt5_error_throttled(primary_error, broker_id=broker_id, broker_name=broker_name, key=f"deals_primary_failed:{broker_id}:{err}", cooldown_sec=45)
    except Exception as exc:
        err = mt5.last_error() if mt5 is not None else "mt5_unavailable"
        primary_error = f"history_deals_get exception [phase=primary, from={from_date.isoformat()}, to={to_date.isoformat()}, exc={exc}, last_error={err}]"
        _log_mt5_error_throttled(primary_error, broker_id=broker_id, broker_name=broker_name, key=f"deals_primary_exception:{broker_id}:{err}", cooldown_sec=45)
    cursor = from_date
    merged: list[Any] = []
    fallback_errors: list[str] = []
    while cursor < to_date:
        chunk_end = min(cursor + timedelta(days=7), to_date)
        try:
            chunk_raw = mt5.history_deals_get(cursor, chunk_end) if mt5 is not None else []
            if chunk_raw is None:
                err = mt5.last_error() if mt5 is not None else "mt5_unavailable"
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
            "history_deals_get fallback failed [phase=chunked, from=" + f"{from_date.isoformat()}, to={to_date.isoformat()}]: " + " | ".join(fallback_errors[:4]),
            broker_id=broker_id,
            broker_name=broker_name,
            key=f"deals_fallback_failed:{broker_id}:{fallback_errors[0]}",
            cooldown_sec=45,
        )
    return [], False, primary_error


def sync_broker_trade_state(broker: dict[str, Any] | None, history_days: int | None = 90):
    broker = broker or {}
    payload = {
        "broker_id": broker.get("id"),
        "broker_name": broker.get("name"),
        "synced": False,
        "reason": "unknown",
    }
    payload.update(_build_mt5_call_notice(call_name="sync_broker_trade_state", strategy_related=False))
    if _check_mt5_non_strategy_confirmation(call_name="sync_broker_trade_state", payload=payload, strategy_related=False):
        return payload
    if str(broker.get("platform", "mt5")).lower() != "mt5" or mt5 is None:
        return {"broker_id": broker.get("id"), "synced": False, "reason": "non_mt5_platform"}
    terminal_path = broker.get("terminal_path")
    if not terminal_path:
        return {"broker_id": broker.get("id"), "synced": False, "reason": "terminal_path_missing"}
    if _is_keep_terminal_alive_enabled():
        ensure_terminal_running(terminal_path, broker={"is_default": True})
    initialized = False
    saved_count = 0
    errors: list[dict[str, Any]] = []
    try:
        with _MT5_LOCK:
            initialized = bool(mt5.initialize(path=terminal_path))
            if not initialized:
                db.log_mt5_error(f"Failed to initialize MT5 for trade sync: {broker.get('name')}", broker_id=broker.get("id"), broker_name=broker.get("name"))
                return {"broker_id": broker.get("id"), "synced": False, "reason": "mt5_initialize_failed"}
            account = mt5.account_info()
            if account is None:
                return {"broker_id": broker.get("id"), "synced": False, "reason": "account_info_failed"}
            account_id = int(getattr(account, "login", 0) or 0) or None
            positions = list(mt5.positions_get() or [])
            from_date = datetime(1970, 1, 1) if history_days is None else datetime.now() - timedelta(days=max(1, int(history_days)))
            to_date = datetime.now() - timedelta(seconds=1)
            deals, deals_ok, deals_fetch_mode = _fetch_history_deals_resilient(broker, from_date, to_date)
            deals_by_position = _group_deals_by_position(deals)
            live_tickets: set[int] = set()
            for position in positions:
                ticket = int(getattr(position, "ticket", 0) or 0)
                if ticket <= 0:
                    continue
                live_tickets.add(ticket)
                trade = _build_open_trade_from_position(broker, account_id, position, deals_by_position.get(ticket, []))
                try:
                    db.upsert_trade_history_record(trade)
                    saved_count += 1
                except Exception as exc:
                    errors.append({"trade_id": trade.get("trade_id"), "error": str(exc)})
            for ticket, deals_for_position in deals_by_position.items():
                if ticket in live_tickets:
                    continue
                summary = _build_closed_trade_from_deals(broker, account_id, ticket, deals_for_position)
                if summary:
                    try:
                        db.upsert_trade_history_record(summary)
                        saved_count += 1
                    except Exception as exc:
                        errors.append({"trade_id": summary.get("trade_id"), "error": str(exc)})
            return {
                "broker_id": broker.get("id"),
                "broker_name": broker.get("name"),
                "account_id": account_id,
                "synced": deals_ok and not errors,
                "partial": (not deals_ok) or bool(errors),
                "reason": "ok" if deals_ok and not errors else ("history_deals_fetch_failed" if not deals_ok else "upsert_failed"),
                "open_positions": len(live_tickets),
                "history_deals": len(deals),
                "history_fetch_mode": deals_fetch_mode,
                "saved_count": saved_count,
                "errors": errors,
            }
    except Exception as exc:
        _log_mt5_error_throttled(f"Terminal sync failed for broker {broker.get('name')}: {exc}", broker_id=broker.get("id"), broker_name=broker.get("name"), key=f"terminal_sync_failed:{broker.get('id')}:{exc}", cooldown_sec=45)
        return {"broker_id": broker.get("id"), "synced": False, "reason": str(exc)}
    finally:
        if initialized:
            _safe_mt5_shutdown()


def sync_all_terminal_trade_state(history_days: int | None = 90):
    results = []
    for broker in db.list_brokers(include_inactive=False):
        if str(broker.get("platform", "mt5")).lower() != "mt5":
            continue
        results.append(sync_broker_trade_state(broker, history_days=history_days))
    return results


def sync_trade_state_for_history_flow(*, broker_id: int | None = None, state: dict[str, Any] | None = None) -> dict[str, Any]:
    current_state = state if isinstance(state, dict) else db.get_account_state()
    sync_all = bool(current_state.get("trade_history_sync_all", False))
    days_value = current_state.get("trade_history_sync_days", 90)
    try:
        history_days = None if sync_all else max(1, int(days_value or 90))
    except Exception:
        history_days = None if sync_all else 90

    if broker_id is not None:
        broker = db.get_broker(broker_id)
        if not broker or str(broker.get("platform", "mt5")).lower() != "mt5":
            results: list[dict[str, Any]] = []
        else:
            results = [sync_broker_trade_state(broker, history_days=history_days)]
    else:
        results = sync_all_terminal_trade_state(history_days=history_days)

    synced = sum(1 for item in results if item.get("synced"))
    partial = sum(1 for item in results if item.get("partial"))
    failed = sum(1 for item in results if not item.get("synced") and not item.get("partial"))
    if failed and not synced and not partial:
        status = "error"
    elif partial or failed:
        status = "partial"
    else:
        status = "ok"

    return {
        "status": status,
        "summary": {
            "brokers_total": len(results),
            "brokers_synced": synced,
            "brokers_partial": partial,
            "brokers_failed": failed,
            "history_days": history_days,
            "sync_all": sync_all,
        },
        "results": results,
    }


def get_background_mt5_sync_status() -> dict[str, Any]:
    with _BACKGROUND_SYNC_LOCK:
        payload = {
            "status": "ok",
            "sync_status": str(_BACKGROUND_SYNC_STATE.get("status", "idle")),
            "queued_at": _BACKGROUND_SYNC_STATE.get("queued_at"),
            "started_at": _BACKGROUND_SYNC_STATE.get("started_at"),
            "finished_at": _BACKGROUND_SYNC_STATE.get("finished_at"),
            "error": _BACKGROUND_SYNC_STATE.get("error"),
            "last_result": _BACKGROUND_SYNC_STATE.get("last_result"),
        }
        return payload


def sync_trade_state_for_history_flow_in_background(*, broker_id: int | None = None, state: dict[str, Any] | None = None, timeout_sec: float = 1.0) -> dict[str, Any]:
    now = time.time()
    with _BACKGROUND_SYNC_LOCK:
        _BACKGROUND_SYNC_STATE.update(
            {
                "status": "queued",
                "queued_at": now,
                "started_at": None,
                "finished_at": None,
                "error": None,
                "last_result": None,
            }
        )

    def _runner() -> None:
        try:
            with _BACKGROUND_SYNC_LOCK:
                _BACKGROUND_SYNC_STATE["status"] = "running"
                _BACKGROUND_SYNC_STATE["started_at"] = time.time()
                _BACKGROUND_SYNC_STATE["finished_at"] = None
                _BACKGROUND_SYNC_STATE["error"] = None
            payload = sync_trade_state_for_history_flow(broker_id=broker_id, state=state)
            with _BACKGROUND_SYNC_LOCK:
                _BACKGROUND_SYNC_STATE["status"] = "completed"
                _BACKGROUND_SYNC_STATE["finished_at"] = time.time()
                _BACKGROUND_SYNC_STATE["last_result"] = payload
        except Exception as exc:
            with _BACKGROUND_SYNC_LOCK:
                _BACKGROUND_SYNC_STATE["status"] = "failed"
                _BACKGROUND_SYNC_STATE["finished_at"] = time.time()
                _BACKGROUND_SYNC_STATE["error"] = str(exc)

    worker = threading.Thread(target=_runner, name=f"trade-sync-bg-{broker_id or 'all'}", daemon=True)
    worker.start()
    return {"status": "queued", "sync_status": "queued", "message": "MT5 trade sync started in background"}


__all__ = [
    "TerminalAdapter",
    "MT5Adapter",
    "MouseAdapter",
    "SimulationAdapter",
    "_MT5_LOCK",
    "normalize_terminal_time_offset_seconds",
    "calibrate_terminal_epoch_for_display",
    "estimate_broker_time_offset_seconds",
    "ensure_terminal_running",
    "get_broker_adapter",
    "probe_broker_order_status",
    "get_broker_order_status_snapshot",
    "normalize_lot_with_constraints",
    "get_broker_symbol_constraints",
    "get_broker_account_metrics",
    "get_broker_symbol_tick",
    "sync_broker_trade_state",
    "sync_all_terminal_trade_state",
    "sync_trade_state_for_history_flow",
    "get_background_mt5_sync_status",
    "sync_trade_state_for_history_flow_in_background",
]
