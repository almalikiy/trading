# Trading Frontend Dash

This project is the Python Dash web client for the trading system.

## Run locally

1. Create and activate a virtual environment.
2. Install dependencies:
   pip install -r requirements.txt
3. Start backend FastAPI service on port 8001.
4. Run the Dash app:
   python app.py
5. Open http://localhost:8050

## Environment

Create a `.env` file copied from `.env.example` if you need custom values.

## Features included

- live signal panel
- OHLC candlestick chart
- account summary
- broker list
- open positions table
- refresh timer and status indicators

## Backend endpoints used

- /dashboard/summary
- /account/state
- /trade/open_positions
- /signal
- /ohlcv
- /brokers
- /brokers/default
- /mt5/status
