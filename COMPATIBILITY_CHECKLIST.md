# Checklist Kompatibilitas Refactor Trading Bot

## Status umum
- [x] Arsitektur refactor terstruktur dalam `trading_bot/`
- [x] Broker adapters konsisten melalui contract umum
- [x] MT5 live adapter telah dibuat untuk XAUUSD
- [x] Test suite utama berjalan sukses
- [x] Data default broker dan simbol lama masih kompatibel dengan schema lama

## 1. Broker list dan default pair lama
- [x] `brokers.default_symbol` tetap dipertahankan di schema legacy
- [x] `XAUUSD` tetap terjaga sebagai default symbol utama
- [x] nilai default broker aktif tetap diizinkan untuk dipindahkan ke refactor
- [x] list broker lama masih dapat dimigrasi tanpa kehilangan identitas broker

## 2. Integrasi MT5
- [x] `MT5BrokerAdapter` menggunakan MetaTrader5 API entry points yang benar
- [x] koneksi terminal, login, health check, account summary, symbol info, tick, OHLCV, order, status, posisi ter-cover
- [x] fallback aman bila package atau terminal tidak tersedia
- [x] validasi order menggunakan request object domain

## 3. Struktur refactor yang baru
- [x] `core/` memisahkan domain, services, orchestrator, risk, execution
- [x] `adapters/` memisahkan broker-specific logic
- [x] `infrastructure/` memisahkan config, database, redis, resilience
- [x] `app/` masih dapat dipakai untuk API dan legacy integration sementara

## 4. Kompatibilitas data lama
- [x] migrasi data JSON legacy ke SQLite/DB tetap dipertahankan
- [x] nilai `auto_trade_symbol` dan `default_symbol` tetap konsisten
- [x] fitur account state dan trade history tetap dapat dibaca dan dikelola
- [x] perubahan struktur tidak menghapus tabel/data lama secara langsung

## 5. Fitur yang tetap dipertahankan
- [x] default broker aktif
- [x] default symbol `XAUUSD`
- [x] pilihan broker MT5/Binance/Stockbit dalam factory
- [x] posisi, order execution, account summary
- [x] API surface basic untuk runtime/orchestrator
- [x] resolusi simbol default berdasarkan broker aktif

## 6. Fitur yang perlu validasi lanjutan
- [ ] real execution di MT5 dengan terminal aktif dan akun nyata
- [ ] koneksi Binance live API dan order handling penuh
- [ ] koneksi Redis/Postgres production
- [ ] API route legacy full parity dengan sistem lama
- [ ] keamanan env/config untuk production
- [ ] monitoring, alerting, and retry policy production tuning

## 7. Evidence / verification
- [x] `python -m pytest -q`
- [x] status: 39 passed in 14.18s

## 8. Kesimpulan
Refactor sudah berada pada tahap yang layak lanjut ke hardening produksi: struktur bersih sudah ada, semua test utama lulus, dan data broker/default symbol lama tetap kompatibel. Fokus berikutnya adalah validasi live broker engine di MT5 dan final parity terhadap fitur operasional legacy yang belum sepenuhnya dipindahkan ke arsitektur baru.
