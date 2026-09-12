from __future__ import annotations

import time
from typing import Any

from trading_bot.app.db import get_mt5_error_log
from trading_bot.app.logic.cache import (
    cache_key,
    ohlcv_cache as _ohlcv_cache,
    refreshing_ohlcv as _refreshing_ohlcv,
    refreshing_signal as _refreshing_signal,
    signal_cache as _signal_cache,
    start_background_refresh as _start_background_refresh,
)
from trading_bot.app.logic.core import (
    DEFAULT_SIGNAL_TIMEFRAMES,
    SUPPORTED_TIMEFRAMES,
    SignalSimulator,
    calculate_indicators,
    generate_signal,
    normalize_timeframes,
)
from trading_bot.app.logic.execution import close_real_trade, open_real_trade
from trading_bot.app.logic.ohlcv_provider import fetch_ohlcv

simulator = SignalSimulator()


def analyze_symbol(
    symbol: str,
    bars: int = 60,
    timeframes: list[str] | tuple[str, ...] | None = None,
    mode: str = "real",
    terminal_path: str | None = None,
    atr_period: int = 14,
) -> dict[str, Any]:
    tfs = normalize_timeframes(list(timeframes) if timeframes else None)
    indicators: dict[str, dict[str, float]] = {}
    errors: dict[str, str] = {}

    for tf in tfs:
        try:
            rows = fetch_ohlcv(symbol, tf, bars=bars, terminal_path=terminal_path)
            indicators[tf] = calculate_indicators(rows, atr_period=atr_period)
        except Exception as exc:
            errors[tf] = str(exc)

    if errors:
        return {"error": "Failed to fetch data for some timeframes", "details": errors}

    signal = generate_signal(indicators, mode=mode)
    if "M1" in indicators:
        sim_result = simulator.update(float(indicators["M1"].get("sma") or 0.0), signal)
    else:
        sim_result = {}

    return {"signal": signal, "indicators": indicators, "simulator": sim_result}


def get_signal_snapshot(symbol: str, mode: str = "real", terminal_path: str | None = None) -> dict[str, Any]:
    key = cache_key(symbol, mode, terminal_path)

    def producer() -> dict[str, Any]:
        return analyze_symbol(symbol, mode=mode, terminal_path=terminal_path)

    _start_background_refresh("signal", key, producer)

    with_cache = _signal_cache.get(key)
    if with_cache and isinstance(with_cache.get("data"), dict):
        payload = dict(with_cache["data"])
        payload["cached"] = True
        payload["cached_at"] = with_cache.get("updated_at")
        payload["symbol"] = symbol
        payload["mode"] = mode
        return payload

    return {
        "signal": "wait",
        "indicators": {},
        "simulator": {},
        "cached": False,
        "refreshing": True,
        "symbol": symbol,
        "mode": mode,
    }


def get_ohlcv_snapshot(symbol: str, timeframe: str, bars: int = 100, terminal_path: str | None = None) -> list[dict[str, Any]]:
    key = cache_key(symbol, timeframe, bars, terminal_path)

    def producer() -> list[dict[str, Any]]:
        rows = fetch_ohlcv(symbol, timeframe, bars=bars, terminal_path=terminal_path)
        normalized = []
        for row in rows:
            item = dict(row)
            item["time"] = int(item.get("time") or time.time()) - (3 * 3600)
            normalized.append(item)
        return normalized

    _start_background_refresh("ohlcv", key, producer)

    with_cache = _ohlcv_cache.get(key)
    if with_cache and isinstance(with_cache.get("data"), list):
        return with_cache["data"]
    return []


__all__ = [
    "SUPPORTED_TIMEFRAMES",
    "DEFAULT_SIGNAL_TIMEFRAMES",
    "normalize_timeframes",
    "fetch_ohlcv",
    "calculate_indicators",
    "generate_signal",
    "analyze_symbol",
    "get_signal_snapshot",
    "get_ohlcv_snapshot",
    "open_real_trade",
    "close_real_trade",
    "_start_background_refresh",
    "_signal_cache",
    "_ohlcv_cache",
    "_refreshing_signal",
    "_refreshing_ohlcv",
    "get_mt5_error_log",
]
