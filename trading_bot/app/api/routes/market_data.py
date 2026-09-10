from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

from trading_bot.adapters.market_data.binance_market_data import BinanceMarketDataAdapter
from trading_bot.adapters.market_data.mt5_market_data import MT5MarketDataAdapter

router = APIRouter(tags=["market-data"])


def _resolve_market_adapter(symbol: str):
    normalized = (symbol or "XAUUSD").upper()
    if normalized.startswith("BTC") or normalized.endswith("USDT"):
        return BinanceMarketDataAdapter()
    return MT5MarketDataAdapter()


@router.get("/signal")
async def get_signal(symbol: str = "XAUUSD", mode: str = "real") -> dict[str, object]:
    adapter = _resolve_market_adapter(symbol)
    snapshot = await adapter.fetch_snapshot(symbol)
    return {
        "signal": "wait",
        "indicators": {
            "source": snapshot.get("source", "market-data"),
            "last": float(snapshot.get("last", 0.0)),
            "bid": float(snapshot.get("bid", 0.0)),
            "ask": float(snapshot.get("ask", 0.0)),
        },
        "simulator": {},
        "cached": False,
        "refreshing": False,
        "symbol": symbol,
        "mode": mode,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/ohlcv")
async def get_ohlcv(symbol: str = "XAUUSD", timeframe: str = "M1", bars: int = 100) -> list[dict[str, object]]:
    adapter = _resolve_market_adapter(symbol)
    candles = await adapter.fetch_bars(symbol, timeframe, limit=max(1, int(bars)))
    return [
        {
            "time": int(item["timestamp"].timestamp()) if item.get("timestamp") else int(datetime.utcnow().timestamp()),
            "open": float(item.get("open", 0.0)),
            "high": float(item.get("high", 0.0)),
            "low": float(item.get("low", 0.0)),
            "close": float(item.get("close", 0.0)),
            "tick_volume": int(item.get("volume", 0) or 0),
            "symbol": symbol,
            "timeframe": timeframe,
        }
        for item in candles
    ]
