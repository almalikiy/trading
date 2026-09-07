import asyncio

from fastapi.testclient import TestClient

from trading_bot.app.main import app


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


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


def test_dashboard_endpoint():
    client = TestClient(app)
    response = client.get("/dashboard/summary")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
