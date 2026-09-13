# Prioritas Produksi Trading Bot

## Status saat ini (as-is, 2026-09-13)
- [x] Functional test suite berstatus hijau (`pytest -q` passing).
- [x] Backend runtime dan dashboard smoke tests berstatus stabil untuk development.
- [x] Startup lifecycle diperbarui ke `lifespan` dan CORS dibatasi ke origin yang eksplisit.
- [x] Startup bootstrap failure sekarang dilog, bukan dibungkus silent failure.
- [x] Legacy compatibility router diaktifkan secara eksplisit melalui env flag `ENABLE_LEGACY_COMPAT_ROUTES` agar tidak rusak kontrak API lama.
- [x] `validate_brokers.py` / environment validation berhasil dijalankan dan keluar dengan status sukses.
- [x] Runbook live MT5 dibuat di [MT5_LIVE_RUNBOOK.md](MT5_LIVE_RUNBOOK.md).
- [x] API runtime dan routing core stabil untuk development/test suite saat ini.
- [x] Dashboard core UI dan panel monitoring utama telah diimplementasikan.
- [ ] Project belum siap untuk release live penuh — masih dibutuhkan validasi MT5 live nyata dan guardrail produksi yang dilakukan di environment target.

## MT5 Live Safety Gate (must-pass before go-live)
- [ ] Login akun MT5 diverifikasi ke terminal yang benar dan akun yang valid; bukan akun demo/lain.
- [ ] Aplikasi startup tanpa stale process dan tanpa port conflict.
- [ ] Saat `keep MT5 alive` dinonaktifkan, MT5 tidak otomatis restart setelah terminal ditutup.
- [ ] `Ctrl+C` pada backend mematikan server dengan bersih dan tidak ada zombie Python/Uvicorn.
- [x] Semua `validate_brokers.py` / environment check / broker discovery lulus untuk target environment.
- [ ] Risiko hard stop aktif: max drawdown, max daily loss, max open trades, max lot, margin threshold, dan broker blocklist semua di-validate.
- [ ] Live order test kecil (BUY/SELL 0.01 atau volume minimal yang aman) selesai tanpa error, dan log order jelas.
- [ ] Close/partial close/position mirroring terbaca tepat di API dan database.
- [ ] EMS / alerting / monitoring untuk disconnect, margin low, order reject, dan broker error sudah aktif.
- [ ] Release owner menandatangani: “MT5 live safety gate passed”, bukan hanya unit test green.

### Exact operational tests required
1. Environment validation
   - Run: `set PYTHONPATH=. ; .\.venv\Scripts\python.exe validate_brokers.py`
   - Expected: semua broker target, symbol, dan account config terdeteksi tanpa error.
   - Stop if: broker environment mismatch, account tidak cocok, atau symbol default tidak valid.

2. Backend startup and shutdown test
   - Run: `cd /d d:\development\trading ; .\.venv\Scripts\python.exe -m uvicorn trading_bot.app.main:app --host 0.0.0.0 --port 8001`
   - Expected: app binds successfully and health endpoints / runtime endpoints respond.
   - Then press `Ctrl+C` once and confirm: process exits cleanly, no orphaned `uvicorn`/`python` remains.
   - Stop if: shutdown hangs, logs indicate unhandled cancellation loop, or process stays alive.

3. MT5 login and terminal ownership test
   - From app runtime, connect to the exact MT5 terminal assigned to this environment.
   - Verify account number, server, and account type match the intended live/demo environment.
   - Expected: adapter reports connected terminal and correct account summary.
   - Stop if: wrong account or terminal discovered, connection unstable, or data from wrong account appears.

4. Symbol readiness test for `XAUUSD`
   - In MT5 terminal, run symbol selection and quote retrieval for `XAUUSD`.
   - Expected: symbol is selected, tick stream available, spread and bid/ask are read without stale values.
   - Stop if: symbol selection fails or spread returns invalid/zero values.

5. Order execution smoke test (smallest safe volume)
   - Execute a BUY market order with minimal safe volume (example: `0.01` or the broker minimum).
   - Immediately verify order status, fill status, open trade count, and PnL update.
   - Then execute a SELL order for the same position/volume and verify close behavior.
   - Expected: order exists, fills correctly, and close updates both backend state and position summary.
   - Stop if: order rejected without clear reason, stale position state, or duplicate trade IDs appear.

6. Risk guardrail test
   - Set a known risk threshold (e.g., max open trades, lot limit, daily loss cap) to a test value.
   - Trigger the guard condition deliberately and verify the system blocks new orders.
   - Expected: backend rejects trade before execution and logs the blocker event clearly.
   - Stop if: risk limit is ignored, trade still executes, or message is silent / ambiguous.

7. MT5 keep-alive off test
   - Confirm `keep MT5 alive` flag is OFF by default.
   - Close the MT5 terminal manually.
   - Wait several minutes and verify the app does not re-open or restart the terminal unexpectedly.
   - Expected: no hidden restart loop while feature is disabled.
   - Stop if: terminal reappears without operator action or process recycles unexpectedly.

8. Disconnect and recovery test
   - Force a temporary broker disconnect or simulate network outage.
   - Expected: app enters degraded mode, logs the incident, stops new orders, and exposes clear health status.
   - Stop if: app silently swallows the error, keeps trading, or appears healthy while disconnected.

9. Final signoff check
   - All above tests logged and archived.
   - One responsible owner signs off: backend owner + ops owner + risk owner for live trading.
   - Only after this signoff should any real-money or materially live deployment proceed.

## Prioritas 0: Safety & control
- [ ] Validasi login broker MT5 benar-benar aktif dan aman
- [ ] Pastikan akun demo/live tidak tertukar dengan terminal yang salah
- [ ] Batasi environment/config hanya dari `.env` atau secret manager
- [ ] Nonaktifkan trade live default saat env belum siap
- [ ] Pastikan logging error broker tidak menyimpan data sensitif

## Prioritas 1: MT5 live execution
- [ ] Uji koneksi MT5 ke terminal yang benar dan akun yang valid
- [ ] Verifikasi `symbol_select("XAUUSD", True)` sukses di terminal
- [ ] Verifikasi account summary balance/equity/margin berfungsi
- [ ] Uji tick real untuk `XAUUSD` dan spread aktual
- [ ] Uji order BUY market dengan volume kecil
- [ ] Uji order SELL market dengan volume kecil
- [ ] Uji pending order limit/stop jika dibutuhkan
- [ ] Verifikasi close / cancel order dan posisi terbaca dengan benar
- [ ] Pastikan order_id dan client_order_id konsisten
- [ ] Simpan hasil live sebagai baseline sebelum trading real penuh

## Prioritas 2: Risk guardrails
- [ ] Tetapkan max daily loss / max drawdown per broker
- [ ] Validasi max lot per order dan per posisi
- [ ] Matikan open trade saat equity turun di bawah threshold aman
- [ ] Sediakan blocklist atau guard jika symbol tidak valid
- [ ] Pastikan stop loss / take profit selalu divalidasi sebelum order
- [ ] Batasi jumlah posisi terbuka secara bersamaan
- [ ] Validasi margin requirement sebelum trade execution

## Prioritas 3: Broker parity & compatibility
- [ ] Verifikasi MT5 + Binance + Stockbit semua mengikuti contract yang sama
- [ ] Pastikan `default_symbol` dan `broker_default` konsisten saat broker berubah
- [ ] Uji fallback logic saat broker offline / tidak tersedia
- [ ] Verifikasi factory dan orchestrator memilih adapter yang benar
- [ ] Pastikan error handling tidak mengekspos stack trace production

## Prioritas 4: Data layer readiness
- [ ] Redis operational dan timeout terdefinisi dengan benar
- [ ] Postgres connection string valid dan migration siap jalan
- [ ] Trade history dan open position persistensi sudah aktual
- [ ] Recovery strategy jika DB / Redis gagal sementara
- [ ] Audit tabel dan kolom legacy yang masih dipakai oleh app lama

## Prioritas 5: API & runtime stability
- [x] API runtime dan routing core berstatus stabil pada test suite saat ini
- [ ] Uji endpoint order live dari API ke adapter
- [ ] Uji endpoint health untuk semua broker
- [ ] Validasi timeout, retry, dan circuit breaker pada network failure
- [ ] Audit status code dan pesan error API agar jelas untuk frontend
- [ ] Verifikasi backend tidak crash saat broker sedang offline

## Prioritas 6: Observability & ops
- [ ] Logging struktur untuk: order, fill, reject, retry, broker error
- [ ] Tracking performance: latency, PnL, margin usage, execution status
- [ ] Alert untuk: broker disconnect, login gagal, margin low, daily loss cap
- [ ] Backup konfigurasi broker dan environment
- [ ] Dokumentasi runbook untuk restart / reconnect broker

## Prioritas 7: Frontend / UX readiness
- [x] Dashboard core UI dan panel monitoring utama selesai implementasi
- [ ] Broker list dan default symbol tampil sesuai data backend
- [ ] Status broker dan posisi ditampilkan dengan benar
- [ ] Error state dan connection lost tampak jelas di UI
- [ ] Dashboard menampilkan data yang sesuai dengan hasil live real

## Prioritas 8: Hardening sebelum live penuh
- [ ] Secret store / env management final
- [ ] CI/CD pipeline untuk test & lint
- [ ] Smoke test production sebelum live trading
- [ ] Runbook rollback / emergency stop
- [ ] Review all TODOs dan stale placeholders pada adapter live

## Gate release produksi
- [ ] Semua prioritas 0-3 telah diselesaikan
- [ ] Minimal satu uji live MT5 sukses dengan volume kecil
- [ ] Risk guardrails aktif
- [ ] Monitoring & alerting aktif
- [ ] Manual kill switch siap dipakai
- [ ] Tim setuju release dimulai

## Urutan eksekusi yang disarankan
1. Safety & control
2. MT5 live execution
3. Risk guardrails
4. Broker parity & compatibility
5. Data layer readiness
6. API & runtime stability
7. Observability & ops
8. Frontend / UX readiness
9. Hardening & release gate

## Catatan penting
- Fokus utama sebelum trading nyata adalah MT5 + safety guard.
- Jangan masuk ke live penuh sebelum semua item Prioritas 0–3 lolos.
- `XAUUSD` adalah pasangan default utama yang harus selalu diverifikasi sebelum order live.
- Status project saat ini: codebase stabil untuk development dan smoke validation, tetapi belum final release-ready tanpa live MT5 validation dan production guardrails.
