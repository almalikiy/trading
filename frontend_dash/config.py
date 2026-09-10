from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8001")
REFRESH_MS = int(os.getenv("REFRESH_MS", "5000"))
DEFAULT_SYMBOL = "XAUUSD"
DEFAULT_TIMEFRAME = "M1"
DEFAULT_BARS = 60

TIMEFRAME_OPTIONS = ["M1", "M5", "M15", "M30", "H1"]
PAGE_OPTIONS = [
    {"label": "Overview", "value": "overview"},
    {"label": "Strategy", "value": "strategy"},
    {"label": "Transactions", "value": "transactions"},
    {"label": "Settings", "value": "settings"},
]
