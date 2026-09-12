from __future__ import annotations

import time
from typing import Any

try:  # pragma: no cover - runtime dependency
    import MetaTrader5 as mt5
except Exception:  # pragma: no cover
    mt5 = None


def _require_mt5_keep_alive_permission(terminal_path: str | None = None) -> None:
    try:
        from trading_bot.app import terminal_adapters as terminal_adapters
    except Exception:
        return
    if not terminal_adapters._is_keep_terminal_alive_enabled():
        raise RuntimeError("MT5 startup denied: Keep MT5 alive is disabled.")


def build_mock_ohlcv(symbol: str, timeframe: str, bars: int) -> list[dict[str, Any]]:
    now = int(time.time())
    step_map = {
        "M1": 60,
        "M5": 300,
        "M15": 900,
        "M30": 1800,
        "H1": 3600,
        "H4": 14400,
        "D1": 86400,
    }
    step = step_map.get(str(timeframe).upper(), 60)
    base = 2300.0 if str(symbol).upper() == "XAUUSD" else 1.1000
    rows: list[dict[str, Any]] = []
    total = max(1, int(bars))
    for i in range(total):
        drift = (i - (total / 2)) * 0.05
        close = base + drift
        rows.append(
            {
                "time": now - (total - i) * step,
                "open": close - 0.10,
                "high": close + 0.20,
                "low": close - 0.20,
                "close": close,
                "tick_volume": 100 + i,
            }
        )
    return rows


def fetch_ohlcv(symbol: str, timeframe: str = "M1", bars: int = 100, terminal_path: str | None = None, broker: str | None = None) -> list[dict[str, Any]]:
    del broker
    tf_map = {
        "M1": "TIMEFRAME_M1",
        "M5": "TIMEFRAME_M5",
        "M15": "TIMEFRAME_M15",
        "M30": "TIMEFRAME_M30",
        "H1": "TIMEFRAME_H1",
        "H4": "TIMEFRAME_H4",
        "D1": "TIMEFRAME_D1",
    }
    tf = str(timeframe or "").strip().upper()
    if tf not in tf_map:
        raise RuntimeError(f"Unsupported timeframe: {timeframe}")

    if mt5 is None:
        return build_mock_ohlcv(symbol, tf, bars)

    initialized = False
    try:
        from trading_bot.app import terminal_adapters as terminal_adapters

        allowed_path = terminal_adapters._require_default_mt5_terminal_permission(terminal_path)
        initialized = bool(mt5.initialize(path=allowed_path))
        if not initialized:
            raise RuntimeError("MT5 not connected")

        timeframe_id = getattr(mt5, tf_map[tf], None)
        if timeframe_id is None:
            raise RuntimeError(f"Unsupported MT5 timeframe: {tf}")

        bars_fetch = max(1, int(bars)) + 60
        rates = mt5.copy_rates_from_pos(str(symbol), timeframe_id, 0, bars_fetch)
        if rates is None or len(rates) == 0:
            raise RuntimeError(f"No data for {symbol} {timeframe}")

        result: list[dict[str, Any]] = []
        for row in rates:
            result.append(
                {
                    "time": int(row[0]),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "tick_volume": int(row[5] or 0),
                }
            )
        return result
    finally:
        if initialized:
            try:
                mt5.shutdown()
            except Exception:
                pass
