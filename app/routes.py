# =============================================
# Penjelasan singkat keyword, API, dan library (FastAPI):
#
# - FastAPI: Framework Python modern untuk membuat REST API/web backend dengan cepat dan mudah.
# - APIRouter: Fitur FastAPI untuk mengelompokkan endpoint (route) dalam modul terpisah.
# - @router.get/@router.post: Dekorator untuk mendefinisikan endpoint HTTP GET/POST.
# - Request: Objek permintaan HTTP, bisa digunakan untuk akses data request.
#
# Keyword penting Python/FastAPI:
# - def: Mendefinisikan fungsi endpoint.
# - return: Mengembalikan response ke client (frontend).
# - try/except: Penanganan error agar API tetap stabil.
#
# Endpoint utama file ini:
# - /signal: Mengambil sinyal trading dan indikator (multi-timeframe).
# - /ohlcv: Mengambil data harga OHLCV untuk chart.
# - /set-params: (Placeholder) Untuk update parameter dari frontend.
# =============================================
from fastapi import APIRouter, Request
from .logic import analyze_symbol

router = APIRouter()


@router.get("/signal")
def get_signal(symbol: str = "XAUUSD", mode: str = "real"):
    return analyze_symbol(symbol, mode=mode)

# Endpoint: OHLCV data for chart
from .logic import fetch_ohlcv
@router.get("/ohlcv")
def get_ohlcv(symbol: str = "XAUUSD", timeframe: str = "M1", bars: int = 100):
    try:
        df = fetch_ohlcv(symbol, timeframe, bars)
        # Kurangi 3 jam (10800 detik) dari epoch time untuk semua candle
        df["time"] = df["time"] - 3 * 3600
        # Hanya kirim kolom time hasil modifikasi
        df = df[["time", "open", "high", "low", "close", "tick_volume"]]
        return df.to_dict(orient="records")
    except Exception as e:
        return {"error": str(e)}

@router.post("/set-params")
def set_params(request: Request):
    # Placeholder: implement parameter update logic
    return {"status": "ok"}
