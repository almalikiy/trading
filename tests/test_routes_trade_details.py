import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import trading_bot.app.api.routes.positions as routes


def test_get_trade_details_endpoint_returns_payload(monkeypatch):
    payload = {"status": "ok", "trade": {"trade_id": "abc-1", "status": "closed"}, "details": {"trade_id": "abc-1"}}
    monkeypatch.setattr(routes.db, "get_trade_details", lambda trade_identifier: payload["trade"])

    result = asyncio.run(routes.trade_details_compat("abc-1"))

    assert result["status"] == "ok"
    assert result["trade"]["trade_id"] == "abc-1"


def test_get_trade_details_endpoint_raises_404_when_missing(monkeypatch):
    monkeypatch.setattr(routes.db, "get_trade_details", lambda trade_identifier: None)

    result = asyncio.run(routes.trade_details_compat("missing-trade"))

    assert result["status"] == "error"
    assert result["message"] == "Trade not found"
