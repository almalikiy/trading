from __future__ import annotations

import os
import subprocess
import threading
import time
from typing import Any

from trading_bot.app import db
from trading_bot.app.logic import close_real_trade, fetch_ohlcv, open_real_trade
from trading_bot.app.terminal_lifecycle import ensure_terminal_running
from trading_bot.app.terminal_runtime import (
    _BROKER_STATUS_CACHE,
    _BROKER_STATUS_LOCK,
    _BROKER_STATUS_REFRESHING,
    _MT5_LOCK,
    _check_mt5_non_strategy_confirmation,
    _is_keep_terminal_alive_enabled,
    _safe_mt5_shutdown,
    _build_mt5_call_notice,
    mt5,
)


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
        started = ensure_terminal_running(terminal_path, force=True, broker=broker)
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
        except Exception as exc:
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
    from trading_bot.app.terminal_runtime import _normalize_terminal_time_offset_seconds

    broker = broker or {}
    if str(broker.get("platform", "mt5")).lower() != "mt5":
        return 0, None
    tick_payload = get_broker_symbol_tick(broker, symbol=symbol, auto_start=auto_start)
    tick_epoch = int(tick_payload.get("time") or 0)
    if not tick_payload.get("ready") or tick_epoch <= 0:
        return 0, None
    raw_offset = int(time.time()) - tick_epoch
    return _normalize_terminal_time_offset_seconds(raw_offset), tick_epoch


__all__ = [
    "TerminalAdapter",
    "MT5Adapter",
    "MouseAdapter",
    "SimulationAdapter",
    "get_broker_adapter",
    "probe_broker_order_status",
    "get_broker_order_status_snapshot",
    "normalize_lot_with_constraints",
    "get_broker_symbol_constraints",
    "get_broker_account_metrics",
    "get_broker_symbol_tick",
    "estimate_broker_time_offset_seconds",
]
