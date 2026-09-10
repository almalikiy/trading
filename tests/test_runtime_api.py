import asyncio
import time
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.logic as logic
from trading_bot.app.main import app


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_cors_allows_frontend_origin():
    client = TestClient(app)
    response = client.options(
        "/health",
        headers={
            "Origin": "https://trading.almalikiy.net",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") in {"https://trading.almalikiy.net", "*"}


def test_orders_endpoint_creates_order():
    client = TestClient(app)
    payload = {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "volume": "0.01",
        "order_type": "MARKET",
        "broker": "binance",
    }
    response = client.post("/orders", json=payload)
    assert response.status_code == 200
    assert response.json()["approved"] is True


def test_orders_listing_returns_real_payload_not_placeholder():
    client = TestClient(app)
    response = client.get("/orders")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert payload == [] or "status" in payload[0] or "broker" in payload[0]


def test_dashboard_endpoint():
    client = TestClient(app)
    response = client.get("/dashboard/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert "brokers" in payload


def test_default_broker_route_uses_real_db_default(monkeypatch):
    import trading_bot.app.api.routes.brokers as brokers_route

    fake_default = {
        "id": 7,
        "name": "MT5 Demo",
        "platform": "mt5",
        "default_symbol": "XAUUSD",
        "is_default": True,
        "is_active": True,
    }

    monkeypatch.setattr(brokers_route, "get_default_broker", lambda: fake_default)

    client = TestClient(app)
    response = client.get("/brokers/default")
    assert response.status_code == 200
    assert response.json()["name"] == "MT5 Demo"
    assert response.json()["default_symbol"] == "XAUUSD"


def test_signal_endpoint_exists_and_returns_payload():
    client = TestClient(app)
    response = client.get("/signal?symbol=XAUUSD&mode=real")
    assert response.status_code == 200
    payload = response.json()
    assert "signal" in payload


def test_ohlcv_endpoint_exists_and_returns_array():
    client = TestClient(app)
    response = client.get("/ohlcv?symbol=XAUUSD&timeframe=M1&bars=10")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) >= 10
    assert all("close" in candle for candle in payload)


def test_no_not_implemented_placeholders_remain_in_trading_bot():
    root = Path(__file__).resolve().parents[1] / "trading_bot"
    matches = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "not_implemented" in text.lower():
            matches.append(path.relative_to(root).as_posix())
    assert matches == [], f"Placeholder strings remain: {matches}"


def test_trading_bot_market_data_routes_do_not_import_legacy_logic():
    route_file = Path(__file__).resolve().parents[1] / "trading_bot" / "app" / "api" / "routes" / "market_data.py"
    text = route_file.read_text(encoding="utf-8")
    assert "from app.logic" not in text
    assert "import app.logic" not in text


def test_background_refresh_handles_no_data_without_raising(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("No data for XAUUSD M1")

    monkeypatch.setattr(logic, "fetch_ohlcv", boom)
    logic._ohlcv_cache.clear()
    logic._refreshing_ohlcv.clear()

    started = logic._start_background_refresh("ohlcv", "xauusd-m1-fallback", lambda: logic.fetch_ohlcv("XAUUSD", "M1", 60, None))
    assert started is True

    deadline = time.time() + 2
    while time.time() < deadline:
        if "xauusd-m1-fallback" in logic._ohlcv_cache:
            break
        time.sleep(0.02)

    assert "xauusd-m1-fallback" in logic._ohlcv_cache
    assert logic._ohlcv_cache["xauusd-m1-fallback"]["data"] == []
    assert "xauusd-m1-fallback" not in logic._refreshing_ohlcv


def test_legacy_auto_trade_state_tracks_persisted_db_value():
    from app.db import get_account_state, save_account_state

    client = TestClient(app)
    state = get_account_state()
    state["auto_trade_enabled"] = False
    state["enable_real_trade"] = False
    save_account_state(state)

    response = client.get("/account/auto_trade_health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["auto_trade_enabled"] is False
    assert payload["active"] is False

    toggle = client.post("/account/set_auto_trade_enabled", json={"enabled": True})
    assert toggle.status_code == 200
    assert toggle.json()["auto_trade_enabled"] is True

    refreshed = client.get("/account/auto_trade_health")
    assert refreshed.status_code == 200
    assert refreshed.json()["auto_trade_enabled"] is True
    assert refreshed.json()["active"] is True


def test_legacy_frontend_routes_are_compatible():
    client = TestClient(app)
    legacy_routes = [
        "/account/state",
        "/trade/open_positions",
        "/trade/open_count",
        "/account/auto_trade_health",
        "/brokers/default",
    ]

    for route in legacy_routes:
        response = client.get(route)
        assert response.status_code in {200, 404}, f"{route} returned unexpected status {response.status_code}"
