import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.routes as routes


def test_get_trade_details_endpoint_returns_payload(monkeypatch):
    payload = {
        "trade": {"trade_id": "abc-1", "status": "closed"},
        "strategy": {"decision_source": "ML_adaptive"},
        "constraints": {"tp_sl_mode": "broker_tpsl"},
        "signal_snapshots": {"open": {"signal_score": 0.7}, "close": {"signal_score": 0.6}},
        "events": {"open": {"event_type": "open_success"}, "close": {"event_type": "close_success"}},
    }
    monkeypatch.setattr(routes, "get_trade_details", lambda trade_identifier: payload)

    result = routes.get_trade_details_endpoint("abc-1")

    assert result["trade"]["trade_id"] == "abc-1"
    assert result["strategy"]["decision_source"] == "ML_adaptive"


def test_get_trade_details_endpoint_raises_404_when_missing(monkeypatch):
    monkeypatch.setattr(routes, "get_trade_details", lambda trade_identifier: None)

    with pytest.raises(HTTPException) as exc_info:
        routes.get_trade_details_endpoint("missing-trade")

    assert exc_info.value.status_code == 404
    assert "Trade not found" in str(exc_info.value.detail)
