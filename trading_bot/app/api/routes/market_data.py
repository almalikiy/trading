from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, WebSocket

from trading_bot.adapters.market_data.binance_market_data import BinanceMarketDataAdapter
from trading_bot.adapters.market_data.mt5_market_data import MT5MarketDataAdapter
from trading_bot.app.signal_ws import ohlcv_stream, signal_stream

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

    def as_float(value: object, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    return {
        "signal": "wait",
        "indicators": {
            "source": snapshot.get("source", "market-data"),
            "last": as_float(snapshot.get("last"), 0.0),
            "bid": as_float(snapshot.get("bid"), 0.0),
            "ask": as_float(snapshot.get("ask"), 0.0),
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
    if not candles:
        return []
    return [
        {
            "time": int(item["timestamp"].timestamp()) if item.get("timestamp") else int(datetime.utcnow().timestamp()),
            "open": float(item.get("open", 0.0) or 0.0),
            "high": float(item.get("high", 0.0) or 0.0),
            "low": float(item.get("low", 0.0) or 0.0),
            "close": float(item.get("close", 0.0) or 0.0),
            "tick_volume": int(item.get("volume", 0) or 0),
            "symbol": symbol,
            "timeframe": timeframe,
        }
        for item in candles
    ]


@router.websocket("/ws/signal")
async def websocket_signal_stream(websocket: WebSocket) -> None:
    await signal_stream(websocket)


@router.websocket("/signal/ws")
async def websocket_signal_stream_legacy(websocket: WebSocket) -> None:
    await signal_stream(websocket)


@router.websocket("/ws/ohlcv")
async def websocket_ohlcv_stream(websocket: WebSocket) -> None:
    await ohlcv_stream(websocket)
