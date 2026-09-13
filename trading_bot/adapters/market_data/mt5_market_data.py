#file: trading_bot/adapters/market_data/mt5_market_data.py
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from trading_bot.adapters.market_data.base_market_data import BaseMarketDataAdapter

try:  # pragma: no cover - optional runtime dependency
    import MetaTrader5
except Exception:  # pragma: no cover
    MetaTrader5 = None


class MT5MarketDataAdapter(BaseMarketDataAdapter):
    source = "mt5"

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        return (symbol or "XAUUSD").upper().replace(" ", "")

    @staticmethod
    def _mt5_available() -> bool:
        return MetaTrader5 is not None

    @staticmethod
    def _safe_shutdown() -> None:
        if MetaTrader5 is None:
            return
        try:
            MetaTrader5.shutdown()
        except Exception:
            pass

    def _unavailable_snapshot(self, symbol: str, *, reason: str | None = None) -> dict[str, Any]:
        normalized = self._normalize_symbol(symbol)
        return {
            "symbol": normalized,
            "bid": None,
            "ask": None,
            "last": None,
            "timestamp": datetime.utcnow(),
            "source": self.source,
            "connected": False,
            "status": "unavailable",
            "reason": reason or "MT5 not connected or library unavailable",
        }

    def _resolve_default_mt5_path(self) -> str | None:
        try:
            from trading_bot.app import db
            from trading_bot.app import terminal_adapters as terminal_adapters
            from trading_bot.app.terminal_runtime import _normalize_terminal_path_value
        except Exception:
            return None

        try:
            broker = db.get_default_broker() or {}
            terminal_path = broker.get("terminal_path")
            normalized = _normalize_terminal_path_value(terminal_path)
            if normalized and os.path.exists(normalized):
                return normalized
        except Exception:
            pass

        try:
            if terminal_adapters._is_keep_terminal_alive_enabled():
                return terminal_adapters._require_default_mt5_terminal_permission()
        except Exception:
            pass

        try:
            default_path = terminal_adapters._default_broker_terminal_path()
            if default_path:
                return default_path
        except Exception:
            pass
        return None

    def _degraded_snapshot(self, symbol: str) -> dict[str, Any]:
        normalized = self._normalize_symbol(symbol)
        base_price = 2300.0 if normalized == "XAUUSD" else 100.0
        return {
            "symbol": normalized,
            "bid": base_price - 0.5,
            "ask": base_price + 0.5,
            "last": base_price,
            "timestamp": datetime.utcnow(),
            "source": self.source,
            "connected": False,
            "status": "degraded",
            "reason": "keep_alive_disabled_or_default_broker_denied",
        }

    async def fetch_snapshot(self, symbol: str) -> dict[str, Any]:
        normalized = self._normalize_symbol(symbol)
        if not self._mt5_available():
            return self._unavailable_snapshot(normalized, reason="mt5_library_unavailable")

        allowed_path = self._resolve_default_mt5_path()
        if allowed_path is None:
            return self._degraded_snapshot(normalized)

        try:
            if not MetaTrader5.initialize(path=allowed_path):
                raise RuntimeError("MetaTrader5 initialize failed")
            tick = MetaTrader5.symbol_info_tick(normalized)
            if tick is None:
                return self._degraded_snapshot(normalized)

            return {
                "symbol": normalized,
                "bid": float(getattr(tick, "bid", 0.0) or 0.0),
                "ask": float(getattr(tick, "ask", 0.0) or 0.0),
                "last": float(getattr(tick, "last", 0.0) or 0.0),
                "timestamp": datetime.utcnow(),
                "source": self.source,
                "connected": True,
                "status": "ok",
            }
        except Exception:
            return self._unavailable_snapshot(normalized)
        finally:
            self._safe_shutdown()

    async def fetch_bars(self, symbol: str, timeframe: str, limit: int = 200) -> list[dict[str, Any]]:
        normalized = self._normalize_symbol(symbol)
        if not self._mt5_available():
            return []

        allowed_path = self._resolve_default_mt5_path()
        if allowed_path is None:
            try:
                from trading_bot.app.logic.ohlcv_provider import build_mock_ohlcv
            except Exception:
                return []
            total = max(1, min(int(limit), 500))
            return build_mock_ohlcv(normalized, str(timeframe or "M1").upper(), total)

        total = max(1, min(int(limit), 500))
        try:
            if not MetaTrader5.initialize(path=allowed_path):
                raise RuntimeError("MetaTrader5 initialize failed")
            rates = MetaTrader5.copy_rates_from_pos(normalized, MetaTrader5.TIMEFRAME_M1, 0, total)
            if rates is None or len(rates) == 0:
                return []

            bars: list[dict[str, Any]] = []
            for row in rates:
                bars.append(
                    {
                        "symbol": normalized,
                        "timeframe": timeframe,
                        "open": float(row[1]),
                        "high": float(row[2]),
                        "low": float(row[3]),
                        "close": float(row[4]),
                        "volume": int(row[5] or 0),
                        "timestamp": __import__("datetime").datetime.fromtimestamp(int(row[0])),
                        "source": self.source,
                    }
                )
            return bars
        except Exception:
            return []
        finally:
            self._safe_shutdown()
