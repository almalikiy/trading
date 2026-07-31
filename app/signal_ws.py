import MetaTrader5 as mt5
from fastapi import WebSocket
from .logic import get_signal_snapshot
import asyncio
from . import config
from .db import get_account_state, resolve_feed_broker

SYMBOL = "XAUUSD"  # default, bisa diubah via API nanti

async def signal_stream(websocket: WebSocket):
    await websocket.accept()
    interval = getattr(config, 'interval_seconds', 1)
    mode = getattr(config, 'mode', 'real')
    state = get_account_state()
    feed_broker = resolve_feed_broker(state=state, require_terminal_path=True)
    if not feed_broker:
        feed_broker = resolve_feed_broker(state=state, require_terminal_path=False)
    terminal_path = feed_broker.get("terminal_path") if feed_broker else None
    try:
        while True:
            try:
                result = get_signal_snapshot(SYMBOL, mode=mode, terminal_path=terminal_path)
                await websocket.send_json(result)
            except Exception as e:
                try:
                    await websocket.send_json({"error": str(e)})
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
