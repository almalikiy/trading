# Trading Signal Web App

## Deskripsi
Aplikasi web untuk memberikan sinyal trading open/buy pada XAUUSD atau simbol lain, terhubung ke MT5, dengan refresh sinyal tiap detik, tampilan web dinamis (tidak idle), referensi candle chart dan indikator Bollinger Band, RSI, MACD, Stochastic RSI, Moving Average. Konfirmasi indikator selaras di timeframe M1, M5, M15, M30. Metode scalping optimal. Parameter trading dapat diubah di web. Terdapat simulator profit/loss seolah user selalu follow sinyal open/buy.

## Stack
- Backend: Python (FastAPI)
- MT5 integration: MetaTrader5 Python package
- Frontend: Dash / Plotly dashboard
- Data layer: SQLite + custom repositories / state stores
- Real-time flow: background workers + polling + websocket-style state refresh

## Custom Classes Yang Dibuat di Project Ini
Project ini tidak hanya memakai framework bawaan, tapi juga memiliki beberapa custom class utama yang mengelola domain trading, broker, state, dan lifecycle MT5 secara modular.

### 1. Broker & adapter layer
- `BaseAdapter` / `BaseBroker`: contract dasar untuk broker dan adapter.
- `BrokerFactory`: memilih adapter broker berdasarkan platform.
- `MT5BrokerAdapter`: integrasi real MT5 untuk connect, health check, quote, dan summary akun.
- `BinanceBrokerAdapter`: adapter trading data dan eksekusi untuk Binance.
- `StockbitBrokerAdapter`: adapter khusus untuk broker tambahan / market data lokal.
- `MT5Adapter` / `MouseAdapter` / `SimulationAdapter`: adapter terminal runtime untuk eksekusi trade.

### 2. Market data & feed
- `MT5DataFeed`: feed data market dari terminal MT5.
- `MT5MarketDataAdapter`: adapter market data yang mengolah data MT5 menjadi model project.
- `BinanceMarketDataAdapter`: adapter untuk market data Binance.
- `BinanceWSFeed`: streaming websocket feed untuk Binance.
- `CacheStore`: penyimpanan cache untuk data market.

### 3. Persistence & state
- `StateRepository`: repository state aplikasi.
- `TradeRepository`: repository data posisi / trade.
- `TradeLogRepository`: log trade history.
- `PostgresRepository`: repositori basis data PostgreSQL jika dipakai.
- `RedisClient` / `RedisStateStore`: store state yang terdistribusi dan cepat.
- `SessionFactory`: factory session DB / persistence.

### 4. App runtime & workers
- `Runtime`: runtime utama aplikasi.
- `ExecutionWorker`: worker eksekusi order / trade.
- `MarketDataWorker`: worker pengambilan data market.
- `MonitoringWorker`: pemantauan status broker / MT5 / sistem.
- `StrategyWorker`: worker strategy dan decision cycle.

### 5. Strategy & signal domain
- `Signal`: representasi sinyal trading.
- `SignalService`: service pembuatan dan validasi sinyal.
- `SignalSimulator`: simulator profit/loss untuk skenario uji.
- `BaseStrategy`: contract strategy dasar.
- `BreakoutStrategy`, `MeanReversionStrategy`, `TrendFollowingStrategy`
- `MultiTimeframeConfirmationStrategy`, `RsiThresholdStrategy`, `MovingAverageCrossStrategy`
- `StrategyManager`: registrasi dan eksekusi strategy.

### 6. Risk & operational guard
- `RiskEngine`: core logika risk management.
- `ExposureLimits`: batas exposure dan sizing.
- `KillSwitch`: fitur stop aktif agar sistem bisa berhenti darurat.
- `PnLGuard`: proteksi PnL.
- `PositionSizer`: pengatur ukuran posisi.
- `ProductionGuardService` / `OperationalAlertService`: guardrail produksi dan alert operasional.

### 7. Domain entities & value objects
- `SymbolQuote`, `Candle`, `Position`, `OrderRequest`, `OrderExecution`, `AccountSummary`
- `Money`, `Price`, `LotSize`, `Symbol`
- `OrderSide`, `OrderType`, `PositionSide`
- `TradingEvent`, `OrderFilled`, `RiskBreached`

### 8. MT5 lifecycle guard
- `TerminalAdapter`: generic contract untuk terminal.
- `MT5Adapter`: adapter MT5 untuk aksi order live.
- `MouseAdapter`: fallback non-MT5 execution path.
- `SimulationAdapter`: mode simulasi untuk testing / dry run.

Class-class di atas adalah custom project classes yang membentuk struktur modular trading bot ini. Mereka dipisahkan per concern agar lebih mudah dikelola, diuji, dan dikembangkan.

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
   `curl -i -X OPTIONS http://127.0.0.1:8001/account/state -H "Origin: https://trading.almalikiy.net" -H "Access-Control-Request-Method: GET"`
7. Memeriksa apakah port sudah dipakai : `netstat -ano | findstr :8001`
8. Task kill jika diperlukan : `taskkill /F /PID 1234`

## Frontend
1. Build :

## Catatan
- Pastikan MT5 berjalan dan dapat diakses dari backend
- Ganti parameter trading sesuai kebutuhan di web
- Simulator hanya ilustrasi, bukan jaminan profit

## Task Scheduler
- Program/Script:
- Add argument

## TODO Best-Practice (Updated)
- [x] Tambahkan mode proteksi eksekusi order: `engine_only`, `broker_sl`, `broker_tpsl`.
- [x] Terapkan fail-safe broker-side proteksi saat open trade (minimum hard SL ketika mode `broker_sl` atau `broker_tpsl`).
- [x] Tambahkan reversal close guard dengan konfirmasi multi-siklus agar tidak mudah whipsaw.
- [x] Tambahkan minimum hold time sebelum close akibat reversal.
- [x] Simpan close reason terklasifikasi (`auto_close_tp`, `auto_close_sl`, `auto_close_reversal_confirmed`) untuk audit/ML.
- [x] Tambahkan MFE/MAE dan time-to-event (`time_to_target_cross`, `time_to_close`) untuk label ML lanjutan.
- [x] Tambahkan dashboard anomali operasional (mis. target crossed tapi force close).
- [x] Pisahkan dataset model open-decision vs close-decision (anti leakage).

## Parameter Auto-Trade Baru
- `auto_trade_protective_mode`: `engine_only` | `broker_sl` | `broker_tpsl`
- `auto_trade_min_hold_sec`: minimum durasi posisi sebelum boleh close reversal
- `auto_trade_reversal_confirm_cycles`: jumlah siklus sinyal berlawanan sebelum close reversal dieksekusi

Rekomendasi default produksi:
- `auto_trade_protective_mode=broker_sl`
- `auto_trade_min_hold_sec=15`
- `auto_trade_reversal_confirm_cycles=2`
