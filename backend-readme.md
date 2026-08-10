# How Backend Trading.AlMalikiy.Net works

Di file `main.py` ini, **FastAPI** berjalan terus sebagai server HTTP/WebSocket, melayani request API dan koneksi frontend. Sementara itu, **auto‑trader** dijalankan di thread terpisah, dengan interval sesuai setting akun.

---

## 🔎 Mekanisme yang terjadi

- **FastAPI server**  
  - Dijalankan oleh `uvicorn` atau `gunicorn`.  
  - Menangani endpoint REST (`/account/state`, `/trade/open_v2`, dll.) dan WebSocket (`/ws/signal`).  
  - Server ini **non‑stop**: selalu siap menerima request dari frontend.

- **Auto‑trader thread**  
  - Dipanggil saat event startup:  
    ```python
    @app.on_event("startup")
    def startup_event():
        init_db()
        start_auto_trader_thread()
    ```
  - Fungsi `start_auto_trader_thread()` biasanya membuat thread baru yang menjalankan `_auto_trade_loop()`.  
  - Loop ini jalan terus, tapi **tidur** sesuai interval (`time.sleep(interval)`), default 2 detik, bisa diubah lewat `account_state.auto_trade_interval_sec`.

- **Sinkronisasi**  
  - Auto‑trader thread membaca sinyal, mencoba open/close trade, lalu update DB.  
  - FastAPI server membaca DB saat frontend minta data (misalnya page trade history).  
  - Jadi backend punya dua jalur: **read/write DB dari auto‑trader** dan **read DB untuk API**.

---
✨ Dengan desain ini, frontend bisa terus membaca data dari DB via API, sementara backend auto‑trader tetap bekerja di background sesuai interval.  
---

Baik, mari kita bedah bagaimana **cycle auto trade** bekerja di backend Anda. Dari potongan kode yang sudah terlihat, siklus auto trade adalah loop yang terus berjalan di thread terpisah, dengan interval tertentu, dan setiap siklus melakukan analisis sinyal lalu memutuskan apakah perlu open/close trade.

---

## 🔎 Alur utama cycle auto trade

1. **Loop berjalan terus**  
   Fungsi `_auto_trade_loop()` akan terus berputar (`while True`), tidak berhenti kecuali proses backend dihentikan.

2. **Menjalankan satu siklus**  
   Di dalam loop, dipanggil `_run_auto_trade_cycle()`.  
   - Fungsi ini melakukan analisis sinyal (`analyze_symbol`, `fetch_ohlcv`).  
   - Menghitung indikator (RSI, MACD, ATR, dll).  
   - Menentukan arah sinyal (buy/sell/wait).  
   - Mengecek apakah broker siap menerima order (`probe_broker_order_status`).  
   - Mengecek guard (misalnya **direction bias guard** dan **same direction open guard**) supaya tidak over‑trade.  
   - Jika semua lolos, mencoba open trade dengan lot sesuai constraint broker.  
   - Jika ada trade aktif, memeriksa apakah perlu partial TP atau break‑even lock.

3. **Logging & diagnosis**  
   - Setiap keputusan dicatat dengan `_diag_event`.  
   - Open attempt dicatat dengan `_diag_open_attempt`.  
   - Close attempt dicatat dengan `_diag_close_attempt`.  
   - Semua event masuk ke `_AUTO_TRADE_DIAG` agar bisa dipantau dari API.

4. **Interval antar siklus**  
   Setelah satu siklus selesai, backend membaca `account_state.auto_trade_interval_sec` (default 2 detik).  
   Interval dipaksa minimal 1 detik, maksimal 60 detik.  
   Loop tidur (`time.sleep(interval)`) sebelum lanjut ke siklus berikutnya.

---

## 📌 Komponen penting dalam siklus
- **Signal scoring** → `_signal_strength()` menghitung skor buy/sell dari indikator multi‑timeframe.  
- **ATR value** → `_resolve_atr_value()` dipakai untuk menentukan TP/SL adaptif.  
- **Adaptive TP/SL** → `build_adaptive_target_snapshot()` menghitung target harga berdasarkan ATR, skor sinyal, alignment, dan winrate historis.  
- **Partial TP** → `_apply_partial_take_profit()` menutup sebagian lot jika rasio risk/reward tercapai.  
- **Break‑even lock** → `_apply_break_even_lock()` menggeser SL ke titik aman jika profit sudah cukup.  
- **Guard** → `_passes_direction_bias_guard()` dan `_passes_same_direction_open_guard()` mencegah open trade berulang di arah yang sama saat kondisi tidak sehat.

---

## ✅ Kesimpulan
Cycle auto trade = **analisis sinyal → cek guard → open/close trade → update DB → tidur sesuai interval → ulangi**.  
Dengan desain ini, backend bisa terus berjalan paralel dengan FastAPI: server melayani API, sementara auto‑trader bekerja di background sesuai interval.

---

Baris kode yang Anda tunjukkan:

```python
atr_period = max(5, min(100, _coerce_int(state.get("auto_trade_atr_period"), 14)))
```

adalah cara backend menentukan **periode ATR (Average True Range)** yang akan dipakai dalam perhitungan risk management dan TP/SL adaptif. Mari kita uraikan:

---

## 🔎 Penjelasan langkah demi langkah

- **`state.get("auto_trade_atr_period")`**  
  Mengambil nilai konfigurasi dari `account_state`. User bisa mengatur berapa periode ATR yang digunakan (misalnya 14, 20, dll).

- **`_coerce_int(..., 14)`**  
  Fungsi helper internal yang mencoba mengubah nilai ke integer.  
  Jika gagal (misalnya nilainya kosong atau bukan angka), akan fallback ke default `14`.  
  Jadi default ATR period = 14 bar.

- **`min(100, _coerce_int(...))`**  
  Membatasi nilai maksimum ATR period = 100.  
  Supaya tidak ada konfigurasi ekstrem (misalnya 5000) yang bikin perhitungan ATR terlalu berat.

- **`max(5, ...)`**  
  Membatasi nilai minimum ATR period = 5.  
  Supaya ATR tidak terlalu pendek (misalnya 1–2 bar) yang membuat hasilnya terlalu volatile.

---

## 📌 Hasil
- ATR period akan selalu berada di **range 5–100**.  
- Default = 14 jika user tidak mengatur.  
- Nilai ini dipakai untuk menghitung **volatilitas harga** (ATR), yang kemudian digunakan untuk menentukan TP/SL adaptif, partial TP, dan break‑even lock.

---

## ✅ Kesimpulan
Baris ini adalah **guardrail konfigurasi**: memastikan ATR period yang dipakai auto‑trader selalu valid, tidak terlalu kecil atau terlalu besar, dengan default aman di 14 bar.

---

Nilai `atr_period` yang Anda tunjukkan tadi dipakai langsung di fungsi **`build_adaptive_target_snapshot`** untuk menghitung **TP/SL adaptif** berdasarkan volatilitas harga. Mari saya jelaskan alurnya:

---

## 🔎 Hubungan ATR period dengan TP/SL adaptif

1. **Menghitung ATR (Average True Range)**  
   - ATR adalah indikator volatilitas: semakin besar ATR, semakin lebar range harga.  
   - `atr_period` menentukan berapa banyak bar/candle yang dipakai untuk menghitung rata‑rata range.  
   - Default 14 bar, tapi bisa diubah lewat `account_state.auto_trade_atr_period`.  
   - Range valid: 5–100 bar.

2. **Resolve ATR value**  
   - Fungsi `_resolve_trade_atr_value(trade_row, fallback_atr)` akan mengambil nilai ATR dari `signal_context` atau indikator multi‑timeframe.  
   - Kalau tidak ada, fallback ke ATR default.  
   - Nilai ini dipakai sebagai dasar risk management.

3. **Menentukan TP/SL adaptif**  
   Di `build_adaptive_target_snapshot`:
   - **Base TP value**: kalau user tidak set TP manual, maka TP dihitung dari ATR × multiplier.  
     ```python
     tp_mult = state.get("auto_trade_atr_tp_mult", 2.5)
     base_tp_value = atr_value * tp_mult
     ```
   - **Stop Loss (SL)**: dihitung dari ATR × multiplier SL.  
     ```python
     sl_mult = state.get("auto_trade_atr_sl_mult", 1.5)
     stop_distance = atr_value * sl_mult
     ```
   - Dengan cara ini, TP/SL otomatis menyesuaikan volatilitas pasar.

4. **Adaptive factor**  
   - Setelah base TP dihitung, ada faktor adaptif tambahan:  
     - **Signal score** (seberapa kuat sinyal buy/sell).  
     - **Alignment ratio** (berapa banyak timeframe mendukung arah yang sama).  
     - **Recent winrate** (kinerja historis arah trade).  
   - Semua faktor ini menambah/mengurangi multiplier, sehingga TP lebih konservatif atau lebih agresif.

5. **Target price & Stop price**  
   - Untuk **BUY**:  
     ```python
     target_price = entry + effective_tp_value
     stop_price = entry - stop_distance
     ```
   - Untuk **SELL**:  
     ```python
     target_price = entry - effective_tp_value
     stop_price = entry + stop_distance
     ```

---

## ✅ Kesimpulan
- `atr_period` → menentukan seberapa panjang data yang dipakai untuk menghitung ATR.  
- ATR → dipakai sebagai dasar menghitung TP/SL adaptif.  
- TP/SL adaptif → menyesuaikan volatilitas, kekuatan sinyal, alignment timeframe, dan winrate historis.  
- Hasilnya: auto‑trader punya TP/SL yang **dinamis**, tidak statis, sehingga lebih sesuai kondisi pasar.

---

