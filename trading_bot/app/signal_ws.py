from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket

from trading_bot.app import db
from trading_bot.app.logic import get_signal_snapshot

SYMBOL = "XAUUSD"


def _resolve_stream_context(query_params: Any) -> tuple[str, str, float, str | None]:
    state = db.get_account_state()
    interval = float(state.get("auto_trade_interval_sec") or 1.0)
    if interval <= 0:
        interval = 1.0

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

    terminal_path = (feed_broker or {}).get("terminal_path")
    return symbol, mode, interval, terminal_path


async def signal_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    symbol, mode, interval, terminal_path = _resolve_stream_context(websocket.query_params)

    try:
        while True:
            try:
                result = get_signal_snapshot(symbol, mode=mode, terminal_path=terminal_path)
                await websocket.send_json(result)
            except Exception as exc:
                try:
                    await websocket.send_json({"error": str(exc), "symbol": symbol, "mode": mode})
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
