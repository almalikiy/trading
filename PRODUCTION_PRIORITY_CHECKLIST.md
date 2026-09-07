# Prioritas Produksi Trading Bot

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
- [ ] Trade history dan open position persistensi sudah aktul
- [ ] Recovery strategy jika DB / Redis gagal sementara
- [ ] Audit tabel dan kolom legacy yang masih dipakai oleh app lama

## Prioritas 5: API & runtime stability
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
