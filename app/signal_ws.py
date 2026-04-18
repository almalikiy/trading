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
        await websocket.send_json({"error": "MT5 not connected"})
        await websocket.close()
        return
    try:
        while True:
            try:
                # TODO: handle mode simulasi di logic/analyze_symbol
                result = analyze_symbol(SYMBOL, mode=mode)
                await websocket.send_json(result)
            except Exception as e:
                await websocket.send_json({"error": str(e)})
            await asyncio.sleep(interval)
    finally:
        mt5.shutdown()
