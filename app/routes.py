from fastapi import APIRouter, Request
from .logic import analyze_symbol

router = APIRouter()


@router.get("/signal")
def get_signal(symbol: str = "XAUUSD"):
    return analyze_symbol(symbol)

# Endpoint: OHLCV data for chart
from .logic import fetch_ohlcv
@router.get("/ohlcv")
def get_ohlcv(symbol: str = "XAUUSD", timeframe: str = "M1", bars: int = 100):
    try:
        df = fetch_ohlcv(symbol, timeframe, bars)
        return df.to_dict(orient="records")
    except Exception as e:
        return {"error": str(e)}

@router.post("/set-params")
def set_params(request: Request):
    # Placeholder: implement parameter update logic
    return {"status": "ok"}
