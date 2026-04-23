import MetaTrader5 as mt5
from fastapi import WebSocket
from .logic import analyze_symbol
import asyncio
from . import config

SYMBOL = "XAUUSD"  # default, bisa diubah via API nanti

async def signal_stream(websocket: WebSocket):
    await websocket.accept()
    interval = getattr(config, 'interval_seconds', 1)
    mode = getattr(config, 'mode', 'real')
    if not mt5.initialize():
        try:
            await websocket.send_json({"error": "MT5 not connected"})
        except Exception:
            pass
        await websocket.close()
        return
    try:
        while True:
            try:
                result = analyze_symbol(SYMBOL, mode=mode)
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
        mt5.shutdown()
