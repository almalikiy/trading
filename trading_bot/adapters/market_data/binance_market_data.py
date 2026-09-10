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
    def _fallback_price(symbol: str) -> Decimal:
        normalized = BinanceMarketDataAdapter._normalized_symbol(symbol)
        if normalized == "BTCUSDT":
            return Decimal("60125.00")
        if normalized == "ETHUSDT":
            return Decimal("3325.40")
        if normalized == "XAUUSDT":
            return Decimal("4370.00")
        if normalized.endswith("USDT"):
            return Decimal("100.00")
        return Decimal("1.0000")

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
            price = Decimal(str(data.get("price", self._fallback_price(normalized))))
            return {
                "symbol": normalized,
                "bid": price - Decimal("0.01"),
                "ask": price + Decimal("0.01"),
                "last": price,
                "timestamp": datetime.utcnow(),
                "source": self.source,
                "connected": True,
            }
        except Exception:
            price = self._fallback_price(normalized)
            return {
                "symbol": normalized,
                "bid": price - Decimal("0.01"),
                "ask": price + Decimal("0.01"),
                "last": price,
                "timestamp": datetime.utcnow(),
                "source": self.source,
                "connected": False,
            }

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
            if isinstance(candles, list) and candles:
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
                if bars:
                    return bars
        except Exception:
            pass

        base = self._fallback_price(normalized)
        current = datetime.utcnow()
        bars: list[dict[str, Any]] = []
        for index in range(total):
            open_price = base + Decimal(index) * Decimal("0.0007")
            drift = Decimal((index % 6) - 2) * Decimal("0.0005")
            close_price = open_price + drift
            high = max(open_price, close_price) + Decimal("0.001")
            low = min(open_price, close_price) - Decimal("0.001")
            bars.append(
                {
                    "symbol": normalized,
                    "timeframe": timeframe,
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close_price,
                    "volume": Decimal(40 + index * 2),
                    "timestamp": current - timedelta(minutes=(total - index)),
                    "source": self.source,
                }
            )
        return bars
