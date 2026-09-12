from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket

from trading_bot.app import db
from trading_bot.app.logic import get_ohlcv_snapshot, get_signal_snapshot

SYMBOL = "XAUUSD"


class SignalStreamService:
    """Safe live-stream adapter for lightweight signal updates.

    Policy:
    - WebSocket is for real-time market snapshot delivery only.
    - Heavy MT5 operational work remains on REST/polling paths.
    - When Keep MT5 alive is off, the stream exposes a graceful "degraded" state instead of forcing MT5 startup.
    """

    def __init__(self, *, refresh_interval_sec: float = 1.0, heartbeat_interval_sec: float = 30.0) -> None:
        self.refresh_interval_sec = max(0.5, float(refresh_interval_sec))
        self.heartbeat_interval_sec = max(10.0, float(heartbeat_interval_sec))

    def resolve_stream_context(self, query_params: Any) -> tuple[str, str, float, str | None, str, int]:
        state = db.get_account_state()
        interval = float(state.get("auto_trade_interval_sec") or self.refresh_interval_sec)
        if interval <= 0:
            interval = self.refresh_interval_sec

        mode = str((query_params.get("mode") if query_params else None) or state.get("mode") or "real").strip().lower()

        feed_broker = db.resolve_feed_broker(state=state, require_terminal_path=True)
        if not feed_broker:
            feed_broker = db.resolve_feed_broker(state=state, require_terminal_path=False)

        symbol = str(
            (query_params.get("symbol") if query_params else None)
            or (feed_broker or {}).get("default_symbol")
            or state.get("auto_trade_symbol")
            or SYMBOL
        ).strip().upper()
        if not symbol:
            symbol = SYMBOL

        timeframe = str((query_params.get("timeframe") if query_params else None) or "M1").strip().upper() or "M1"
        bars = int((query_params.get("bars") if query_params else None) or 100)
        if bars <= 0:
            bars = 100

        terminal_path = (feed_broker or {}).get("terminal_path")
        return symbol, mode, interval, terminal_path, timeframe, bars

    async def _safe_snapshot(self, symbol: str, mode: str, terminal_path: str | None, *, timeframe: str = "M1", bars: int = 100) -> dict[str, Any]:
        try:
            from trading_bot.app import terminal_adapters
        except Exception:
            terminal_adapters = None

        if terminal_adapters is not None and not terminal_adapters._is_keep_terminal_alive_enabled():
            payload = {
                "signal": "wait",
                "status": "degraded",
                "stream": "safe-cache",
                "symbol": symbol,
                "mode": mode,
                "cached": True,
                "refreshing": False,
                "notice": "MT5 Keep Alive is off. Stream is using cached/non-terminal data only.",
                "indicators": {},
                "simulator": {},
                "ohlcv": [],
                "timeframe": timeframe,
                "bars": bars,
            }
            return payload

        snapshot = get_signal_snapshot(symbol, mode=mode, terminal_path=terminal_path)
        snapshot.setdefault("status", "live")
        snapshot.setdefault("stream", "safe-cache")
        try:
            snapshot["ohlcv"] = get_ohlcv_snapshot(symbol, timeframe, bars=bars, terminal_path=terminal_path)
        except Exception:
            snapshot["ohlcv"] = []
        snapshot["timeframe"] = timeframe
        snapshot["bars"] = bars
        return snapshot

    async def stream(self, websocket: WebSocket) -> None:
        await websocket.accept()
        symbol, mode, interval, terminal_path, timeframe, bars = self.resolve_stream_context(websocket.query_params)

        heartbeat_deadline = 0.0
        try:
            while True:
                try:
                    payload = await self._safe_snapshot(symbol, mode, terminal_path, timeframe=timeframe, bars=bars)
                    await websocket.send_json(payload)
                except Exception as exc:
                    try:
                        await websocket.send_json({
                            "signal": "wait",
                            "status": "error",
                            "stream": "safe-cache",
                            "symbol": symbol,
                            "mode": mode,
                            "error": str(exc),
                        })
                    except Exception:
                        break

                heartbeat_deadline += interval
                if heartbeat_deadline >= self.heartbeat_interval_sec:
                    await websocket.send_json({
                        "signal": "heartbeat",
                        "status": "ok",
                        "stream": "safe-cache",
                        "symbol": symbol,
                        "mode": mode,
                        "timestamp": asyncio.get_running_loop().time(),
                    })
                    heartbeat_deadline = 0.0

                await asyncio.sleep(interval)
        except Exception:
            pass
        finally:
            try:
                await websocket.close()
            except Exception:
                pass


_signal_stream_service = SignalStreamService(refresh_interval_sec=1.0, heartbeat_interval_sec=30.0)


def _resolve_stream_context(query_params: Any) -> tuple[str, str, float, str | None, str, int]:
    return _signal_stream_service.resolve_stream_context(query_params)


async def signal_stream(websocket: WebSocket) -> None:
    await _signal_stream_service.stream(websocket)


async def ohlcv_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    symbol, mode, interval, terminal_path, timeframe, bars = _signal_stream_service.resolve_stream_context(websocket.query_params)
    try:
        while True:
            try:
                payload = {
                    "symbol": symbol,
                    "mode": mode,
                    "timeframe": timeframe,
                    "bars": bars,
                    "ohlcv": get_ohlcv_snapshot(symbol, timeframe, bars=bars, terminal_path=terminal_path),
                    "status": "live",
                    "stream": "ohlcv",
                }
                await websocket.send_json(payload)
            except Exception as exc:
                try:
                    await websocket.send_json({"symbol": symbol, "mode": mode, "status": "error", "error": str(exc), "ohlcv": []})
                except Exception:
                    break
            await asyncio.sleep(interval)
    except Exception:
        pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
