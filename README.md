# Trading Signal Web App

## Deskripsi
Aplikasi web untuk memberikan sinyal trading open/buy pada XAUUSD atau simbol lain, terhubung ke MT5, dengan refresh sinyal tiap detik, tampilan web dinamis (tidak idle), referensi candle chart dan indikator Bollinger Band, RSI, MACD, Stochastic RSI, Moving Average. Konfirmasi indikator selaras di timeframe M1, M5, M15, M30. Metode scalping optimal. Parameter trading dapat diubah di web. Terdapat simulator profit/loss seolah user selalu follow sinyal open/buy.

## Stack
- Backend: Python (FastAPI)
- MT5 integration: MetaTrader5 Python package
- Frontend: React (Vite)
- Charting: TradingView/Chart.js
- Websocket/live update

## Fitur
- Sinyal trading real-time (refresh tiap detik)
- Integrasi MT5 untuk data harga dan eksekusi
- Chart candle dengan indikator teknikal
- Konfirmasi multi-timeframe (M1, M5, M15, M30)
- Parameter trading dapat diubah di web
- Simulator profit/loss mengikuti sinyal

## Instalasi & Menjalankan
1. Pastikan Python 3.10+ dan Node.js terinstal
2. Install dependensi backend: `pip install -r requirements.txt`
3. Install dependensi frontend: `cd frontend && npm install`
4. Jalankan backend: `uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload`
5. Jalankan frontend: `cd frontend && npm run dev`
6. Testing backend CORS respons: 
   curl -i -X OPTIONS http://127.0.0.1:8001/account/state -H "Origin: https://trading.almalikiy.net" -H "Access-Control-Request-Method: GET"


## Frontend
1. Build : 

## Catatan
- Pastikan MT5 berjalan dan dapat diakses dari backend
- Ganti parameter trading sesuai kebutuhan di web
- Simulator hanya ilustrasi, bukan jaminan profit
