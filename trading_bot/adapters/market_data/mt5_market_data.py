#file: trading_bot/adapters/market_data/mt5_market_data.py
from __future__ import annotations

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

    def _unavailable_snapshot(self, symbol: str) -> dict[str, Any]:
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
            "reason": "MT5 not connected or library unavailable",
        }

    async def fetch_snapshot(self, symbol: str) -> dict[str, Any]:
        normalized = self._normalize_symbol(symbol)
        if not self._mt5_available():
            return self._unavailable_snapshot(normalized)

        try:
            if not MetaTrader5.initialize():
                raise RuntimeError("MetaTrader5 initialize failed")
            tick = MetaTrader5.symbol_info_tick(normalized)
            if tick is None:
                return self._unavailable_snapshot(normalized)

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

        total = max(1, min(int(limit), 500))
        try:
            if not MetaTrader5.initialize():
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
