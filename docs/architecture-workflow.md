# Trading Bot Workflow Diagram

```mermaid
flowchart TD
    A[Backend start: uvicorn trading_bot.app.main:app] --> B[trading_bot/app/main.py]
    B --> C[create_app() + include_router()]
    C --> D[startup bootstrap]
    D --> E[trading_bot/app/bootstrap.py]
    E --> F[load settings + default broker + DB state + strategy config]

    F --> G{Auto trade enabled?}
    G -- Yes --> H[trading_bot/app/auto_trader / cycle / hedge]
    G -- No --> I[backend tetap alive untuk API, monitoring, websocket]

    H --> J[analyze_symbol() / generate_signal() / risk evaluation]
    J --> K[trading_bot/app/logic/]
    K --> L[market data + indicators + execution logic]

    L --> M{MT5 terminal available and allowed?}
    M -- Yes --> N[trading_bot/app/terminal_adapters.py]
    M -- No / degraded --> O[degraded mode / cached data / no forced MT5 startup]

    N --> P[MetaTrader5 initialize / terminal check / trade execution]
    P --> Q[open_trade / close_trade / sync trade state]

    Q --> R[PostgreSQL primary store / SQLite compatibility shim during migration]
    R --> S[State persisted]

    I --> T[FastAPI routes]
    H --> T
    Q --> T
    T --> U[/health / /signal / /ohlcv / /account / /trade / /brokers / /strategies]

    U --> V[backend JSON response]
    V --> W[Optional dashboard consumer]
    W --> X[frontend_dash/app.py]
    X --> Y[Dash callbacks + page render]
    Y --> Z[Browser UI update]

    Z --> AA[User monitoring / manual control]

    style A fill:#dbeafe,stroke:#2563eb,stroke-width:2px
    style H fill:#dcfce7,stroke:#16a34a,stroke-width:2px
    style W fill:#fef3c7,stroke:#d97706,stroke-width:2px
```

## Penjelasan singkat

1. Entry point sistem adalah backend, bukan dashboard.
2. Saat backend dinyalakan, app FastAPI langsung bootstrap konfigurasi, broker, state, dan siap menjalankan auto-trade.
3. Dashboard hanya bersifat optional consumer: ia membaca data dari API/backend, tetapi backend tetap bisa bekerja tanpa UI.
4. Auto-trade berjalan melalui pipeline:
   - bootstrap
   - auto trader
   - signal/risk logic
   - MT5 terminal adapter
   - persist state ke database
5. Frontend Dash berfungsi untuk monitoring, kontrol manual, dan visualisasi, bukan sebagai prasyarat utama agar backend bisa menjalankan strategi.

## Arti penting untuk project ini

- Backend adalah owner utama dari lifecycle trading.
- Dashboard tidak boleh menjadi source of truth atau trigger utama.
- MT5/terminal access harus dikendalikan dari backend melalui policy aman, bukan dari UI.
- Auto-trade dan monitoring bisa berjalan terpisah: backend tetap aktif meski dashboard dimatikan.

## Sumber utama

- [trading_bot/app/main.py](../trading_bot/app/main.py)
- [trading_bot/app/bootstrap.py](../trading_bot/app/bootstrap.py)
- [trading_bot/app/auto_trader](../trading_bot/app/auto_trader)
- [trading_bot/app/logic](../trading_bot/app/logic)
- [trading_bot/app/terminal_adapters.py](../trading_bot/app/terminal_adapters.py)
- [frontend_dash/app.py](../frontend_dash/app.py)
