#file: trading_bot/adapters/market_data/binance_market_data.py
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import requests

from trading_bot.adapters.market_data.base_market_data import BaseMarketDataAdapter


class BinanceMarketDataAdapter(BaseMarketDataAdapter):
    source = "binance"
    base_url = "https://api.binance.com"

    @staticmethod
    def _normalized_symbol(symbol: str) -> str:
        normalized = (symbol or "BTCUSDT").upper().replace(" ", "")
        if normalized == "XAUUSD":
            return "XAUUSDT"
        return normalized

    @staticmethod
    def _interval_for_timeframe(timeframe: str) -> str:
        mapping = {
            "M1": "1m",
            "M5": "5m",
            "M15": "15m",
            "M30": "30m",
            "H1": "1h",
        }
        return mapping.get(str(timeframe).upper(), "1m")

    @staticmethod
    def _unavailable_snapshot(symbol: str) -> dict[str, Any]:
        normalized = BinanceMarketDataAdapter._normalized_symbol(symbol)
        return {
            "symbol": normalized,
            "bid": None,
            "ask": None,
            "last": None,
            "timestamp": datetime.utcnow(),
            "source": "binance",
            "connected": False,
            "status": "unavailable",
            "reason": "Binance market data is unavailable or the exchange is unreachable",
        }

    async def fetch_snapshot(self, symbol: str) -> dict[str, Any]:
        normalized = self._normalized_symbol(symbol)
        try:
            payload = await asyncio.to_thread(
                requests.get,
                f"{self.base_url}/api/v3/ticker/price",
                params={"symbol": normalized},
                timeout=10,
            )
            payload.raise_for_status()
            data = payload.json()
            price = Decimal(str(data["price"]))
            return {
                "symbol": normalized,
                "bid": price - Decimal("0.01"),
                "ask": price + Decimal("0.01"),
                "last": price,
                "timestamp": datetime.utcnow(),
                "source": self.source,
                "connected": True,
                "status": "ok",
            }
        except Exception:
            return self._unavailable_snapshot(normalized)

    async def fetch_bars(self, symbol: str, timeframe: str, limit: int = 200) -> list[dict[str, Any]]:
        normalized = self._normalized_symbol(symbol)
        interval = self._interval_for_timeframe(timeframe)
        total = max(1, min(int(limit), 1000))
        try:
            payload = await asyncio.to_thread(
                requests.get,
                f"{self.base_url}/api/v3/klines",
                params={"symbol": normalized, "interval": interval, "limit": total},
                timeout=10,
            )
            payload.raise_for_status()
            candles = payload.json()
            if not isinstance(candles, list) or not candles:
                return []

            bars = []
            for row in candles:
                if not isinstance(row, list) or len(row) < 6:
                    continue
                ts = int(row[0]) / 1000
                bars.append(
                    {
                        "symbol": normalized,
                        "timeframe": timeframe,
                        "open": Decimal(str(row[1])),
                        "high": Decimal(str(row[2])),
                        "low": Decimal(str(row[3])),
                        "close": Decimal(str(row[4])),
                        "volume": Decimal(str(row[5])) if row[5] is not None else Decimal("0"),
                        "timestamp": datetime.fromtimestamp(ts),
                        "source": self.source,
                    }
                )
            return bars
        except Exception:
            return []
