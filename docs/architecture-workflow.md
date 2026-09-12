# Trading Bot Workflow Diagram

```mermaid
flowchart TD
    A[User membuka dashboard / klik tombol / input parameter] --> B[frontend_dash/app.py]
    B --> C[build_layout()]
    C --> D[Dash callbacks registration]
    D --> E[frontend_dash/pages/overview.py / settings.py / strategy.py]

    E --> F[frontend_dash/api/client.py]
    F --> G[api_get() / api_post()]

    G --> H[HTTP request ke backend FastAPI]
    H --> I[trading_bot/app/main.py]
    I --> J[FastAPI app + router]
    J --> K[Endpoint route]

    K --> L{Jenis endpoint}
    L -->|/dashboard/summary| M[trading_bot/app/api/routes/dashboard.py]
    L -->|/account/*| N[trading_bot/app/api/routes/account.py]
    L -->|/mt5/*| O[trading_bot/app/api/routes/mt5.py]
    L -->|/signal / /ohlcv / /trade/*| P[route lain]
    L -->|/strategies/*| Q[trading_bot/app/api/routes/strategies.py]

    M --> R[db.get_account_state() / list_brokers() / get_open_trades_count()]
    N --> S[set_keep_mt5_alive() / get_keep_mt5_alive_status()]
    O --> T[status MT5 + background sync]
    P --> U[logic / services / persistence]
    Q --> V[strategy registry / config]

    R --> W[trading_bot/app/db.py]
    S --> X[trading_bot/app/terminal_adapters.py]
    T --> X
    U --> X
    V --> Y[trading_bot strategies / risk / adapters]

    W --> Z[SQLite / State storage]
    X --> AA[MetaTrader5 / terminal / broker access]
    Y --> AB[Signal / execution / risk logic]

    M --> AC[JSON response]
    N --> AC
    O --> AC
    P --> AC
    Q --> AC

    AC --> AD[frontend_dash/api/client.py parse JSON]
    AD --> AE[Dash callback update]
    AE --> AF[html.Div / dcc.Graph / status label update]
    AF --> AG[Browser UI render]

    AG --> AH[User melihat hasil terbaru]
```

## Penjelasan singkat

1. User berinteraksi dengan dashboard.
2. Frontend Dash menangkap event dan memanggil callback.
3. Frontend mengirim request HTTP ke backend FastAPI.
4. Endpoint backend memproses request dan mengambil data dari DB atau MT5 adapter.
5. Backend mengembalikan JSON ke frontend.
6. Callback Dash memperbarui komponen UI dan browser menampilkan hasil baru.

## Sumber utama

- [frontend_dash/app.py](../frontend_dash/app.py)
- [frontend_dash/api/client.py](../frontend_dash/api/client.py)
- [frontend_dash/callbacks/navigation_callbacks.py](../frontend_dash/callbacks/navigation_callbacks.py)
- [trading_bot/app/main.py](../trading_bot/app/main.py)
- [trading_bot/app/api/routes/dashboard.py](../trading_bot/app/api/routes/dashboard.py)
- [trading_bot/app/terminal_adapters.py](../trading_bot/app/terminal_adapters.py)
