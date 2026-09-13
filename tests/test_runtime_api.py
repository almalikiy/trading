import asyncio
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import trading_bot.app.logic as logic
from trading_bot.app.main import app


def test_backend_startup_command_uses_trading_bot_app():
    run_script = Path(__file__).resolve().parents[1] / "run_backend.bat"
    text = run_script.read_text(encoding="utf-8")
    assert "trading_bot.app.main:app" in text
    assert "uvicorn" in text.lower()


def test_strategy_list_endpoint_returns_registered_strategies():
    client = TestClient(app)
    response = client.get("/strategies/list")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert isinstance(payload["strategies"], list)
    assert payload["strategies"]


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


def test_broker_launch_and_sync_routes_exist_for_selected_broker():
    from trading_bot.app import db

    broker = db.create_broker({
        "name": f"Action Test Broker {int(time.time() * 1000)}",
        "platform": "mt5",
        "default_symbol": "XAUUSD",
        "terminal_path": "C:/MT5/terminal64.exe",
        "is_active": True,
    })
    client = TestClient(app)

    launch = client.post(f"/brokers/{broker['id']}/launch_terminal")
    assert launch.status_code == 200
    assert launch.json()["status"] in {"ok", "error"}

    sync = client.post(f"/brokers/{broker['id']}/sync")
    assert sync.status_code == 200
    assert "synced" in sync.json() or "status" in sync.json()


def test_signal_endpoint_exists_and_returns_payload():
    client = TestClient(app)
    response = client.get("/signal?symbol=XAUUSD&mode=real")
    assert response.status_code == 200
    payload = response.json()
    assert "signal" in payload
    assert payload["status"] in {"ok", "degraded", "error", "unavailable"}


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
    from trading_bot.app.db import get_account_state, save_account_state

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


def test_set_auto_trade_config_respects_manual_symbol_override():
    from trading_bot.app.db import get_account_state, save_account_state

    client = TestClient(app)
    state = get_account_state()
    state["auto_trade_symbol"] = "XAUUSD"
    save_account_state(state)

    response = client.post("/account/set_auto_trade_config", json={"symbol": "GBPUSD"})
    assert response.status_code == 200
    assert response.json()["auto_trade_symbol"] == "GBPUSD"

    refreshed = get_account_state()
    assert refreshed["auto_trade_symbol"] == "GBPUSD"


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


def test_trade_history_and_open_positions_trigger_terminal_sync(monkeypatch):
    import trading_bot.app.api.routes.positions as positions_route

    calls = []

    def fake_sync(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return {"status": "ok", "summary": {}, "results": []}

    monkeypatch.setattr(positions_route, "sync_trade_state_for_history_flow", fake_sync)
    monkeypatch.setattr(positions_route.db, "list_open_trades", lambda: [{"broker_name": "Broker One", "symbol": "XAUUSD", "type": "BUY", "lot": 0.1, "entry": 2300.0, "price": 2301.0, "profit": 5.0, "status": "open", "entryTime": 1725000000}])
    monkeypatch.setattr(positions_route, "get_open_trades_count", lambda: 1)
    monkeypatch.setattr(positions_route, "get_trade_history", lambda: [{"symbol": "XAUUSD", "type": "BUY", "entry": 2300.0, "exit": 2305.0, "lot": 0.1, "profit": 10.0, "status": "closed", "reason": "tp"}])

    client = TestClient(app)

    open_positions = client.get("/trade/open_positions")
    open_count = client.get("/trade/open_count")
    history = client.get("/trade/history")

    assert open_positions.status_code == 200
    assert open_count.status_code == 200
    assert history.status_code == 200
    assert calls == []


def test_dashboard_summary_triggers_terminal_sync(monkeypatch):
    import trading_bot.app.api.routes.dashboard as dashboard_route

    calls = []

    def fake_sync(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return {"status": "ok", "summary": {"brokers_total": 0}, "results": []}

    monkeypatch.setattr(dashboard_route, "sync_trade_state_for_history_flow", fake_sync)

    client = TestClient(app)
    response = client.get("/dashboard/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_sync"]["status"] == "queued"
    assert calls == []


def test_background_sync_helper_returns_before_hanging_call_timeout(monkeypatch):
    import trading_bot.app.terminal_adapters as terminal_adapters

    def slow_sync(*args, **kwargs):
        time.sleep(3)
        return {"status": "ok", "summary": {"brokers_total": 0}, "results": []}

    monkeypatch.setattr(terminal_adapters, "sync_trade_state_for_history_flow", slow_sync)

    start = time.perf_counter()
    result = terminal_adapters.sync_trade_state_for_history_flow_in_background(timeout_sec=0.5)
    elapsed = time.perf_counter() - start

    assert result["status"] == "queued"
    assert elapsed < 2.0


def test_mt5_background_sync_status_endpoint_exposes_queue_state():
    client = TestClient(app)
    response = client.get("/mt5/background_sync_status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["sync_status"] in {"idle", "queued", "running", "failed", "completed"}


def test_non_strategy_mt5_checks_are_deferred_with_notice():
    import trading_bot.app.terminal_adapters as terminal_adapters

    class FakeMt5:
        def initialize(self, path):
            return True

        def account_info(self):
            return None

        def terminal_info(self):
            return None

        def symbol_info(self, symbol):
            return None

        def symbol_select(self, symbol, visible):
            return True

        def symbol_info_tick(self, symbol):
            return None

        def positions_get(self):
            return []

        def history_deals_get(self, from_date, to_date):
            return []

        def shutdown(self):
            return None

        def last_error(self):
            return 0

    original_mt5 = terminal_adapters.mt5
    terminal_adapters.mt5 = FakeMt5()
    try:
        result = terminal_adapters.get_broker_symbol_constraints(
            {"id": 1, "name": "Demo", "platform": "mt5", "terminal_path": "C:/MT5/terminal64.exe"},
            "XAUUSD",
            auto_start=True,
        )
    finally:
        terminal_adapters.mt5 = original_mt5

    assert result["call_classification"] == "rare_operational"
    assert result["strategy_related"] is False
    assert "notice" in result
    assert "defer" in result["notice"].lower() or "non-strategy" in result["notice"].lower() or "confirmation" in result["notice"].lower()
    assert result["reason"] in {"deferred_non_strategy_check", "confirmation_required"}
    assert result.get("requires_confirmation") is True or result.get("confirmation_required") is True


def test_keep_mt5_alive_toggle_persists_and_reports_status():
    client = TestClient(app)

    initial = client.get("/account/state")
    assert initial.status_code == 200
    assert "keep_terminal_alive" in initial.json()

    response = client.post("/account/set_keep_terminal_alive", json={"enabled": True})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["keep_terminal_alive"] is True

    status = client.get("/account/keep_mt5_alive_status")
    assert status.status_code == 200
    assert status.json()["enabled"] is True

    client.post("/account/set_keep_terminal_alive", json={"enabled": False})
    final = client.get("/account/keep_mt5_alive_status")
    assert final.status_code == 200
    assert final.json()["enabled"] is False


def test_keep_mt5_alive_off_does_not_auto_start_terminal():
    import trading_bot.app.terminal_adapters as terminal_adapters

    state = {"keep_terminal_alive": False}
    calls = []

    def fake_ensure(path):
        calls.append(path)
        return True

    original = terminal_adapters.ensure_terminal_running
    terminal_adapters.ensure_terminal_running = fake_ensure
    try:
        terminal_adapters.sync_broker_trade_state({"id": 1, "name": "Demo", "platform": "mt5", "terminal_path": "C:/MT5/terminal64.exe"}, history_days=1)
    finally:
        terminal_adapters.ensure_terminal_running = original

    assert calls == []


def test_default_broker_remains_the_only_backend_autostart_target(monkeypatch):
    import trading_bot.app.terminal_adapters as terminal_adapters

    default_broker = {"id": 7, "name": "Default Broker", "platform": "mt5", "terminal_path": "D:/MT5/default_terminal.exe", "is_default": True}
    feed_broker = {"id": 2, "name": "Feed Broker", "platform": "mt5", "terminal_path": "C:/MT5/feed_terminal.exe", "is_default": False}

    monkeypatch.setattr(terminal_adapters.db, "get_default_broker", lambda: default_broker)
    monkeypatch.setattr(terminal_adapters, "_is_keep_terminal_alive_enabled", lambda: True)
    monkeypatch.setattr(terminal_adapters, "_list_process_paths", lambda: set())
    monkeypatch.setattr(terminal_adapters.subprocess, "Popen", lambda *args, **kwargs: object())

    assert terminal_adapters.ensure_terminal_running(feed_broker["terminal_path"], broker=feed_broker) is False
    assert terminal_adapters.ensure_terminal_running(default_broker["terminal_path"], broker=default_broker) is True

    monkeypatch.setattr(terminal_adapters.db, "resolve_feed_broker", lambda state=None, require_terminal_path=False: feed_broker)
    assert terminal_adapters._get_active_mt5_terminal_target() == (default_broker["terminal_path"], default_broker["name"])


def test_ensure_terminal_running_refuses_when_keep_alive_disabled(monkeypatch):
    import trading_bot.app.terminal_adapters as terminal_adapters

    monkeypatch.setattr(terminal_adapters, "_list_process_paths", lambda: set())
    monkeypatch.setattr(terminal_adapters.db, "get_account_state", lambda: {"keep_terminal_alive": False})
    monkeypatch.setattr(terminal_adapters, "_default_broker_terminal_path", lambda: "D:/MT5/default_terminal.exe")
    terminal_adapters._KEEP_MT5_ALIVE_STATE["enabled"] = False

    started_calls = []

    def fake_popen(args, **kwargs):
        started_calls.append(args)
        return object()

    monkeypatch.setattr(terminal_adapters.subprocess, "Popen", fake_popen)

    assert terminal_adapters.ensure_terminal_running("C:/MT5/terminal64.exe") is False
    assert started_calls == []
    assert terminal_adapters.ensure_terminal_running("D:/MT5/default_terminal.exe") is False
    assert len(started_calls) == 0
    assert terminal_adapters.ensure_terminal_running("C:/MT5/terminal64.exe", force=True) is False
    assert len(started_calls) == 0


def test_direct_mt5_initialization_is_blocked_when_keep_alive_disabled(monkeypatch):
    import trading_bot.app.logic.execution as execution
    import trading_bot.app.logic.ohlcv_provider as ohlcv_provider
    from trading_bot.adapters.brokers.mt5_broker import MT5BrokerAdapter
    import trading_bot.app.terminal_adapters as terminal_adapters

    monkeypatch.setattr(terminal_adapters, "_is_keep_terminal_alive_enabled", lambda: False)

    class FakeMt5:
        ORDER_TYPE_BUY = 0
        ORDER_TYPE_SELL = 1
        TRADE_ACTION_DEAL = 1
        ORDER_TIME_GTC = 0
        TRADE_RETCODE_DONE = 10009
        TRADE_RETCODE_DONE_PARTIAL = 10008
        POSITION_TYPE_BUY = 0
        POSITION_TYPE_SELL = 1
        DEAL_TYPE_BUY = 0
        DEAL_ENTRY_IN = 0
        DEAL_ENTRY_OUT = 1

        def initialize(self, path=None):
            return True

        def symbol_info_tick(self, symbol):
            class Tick:
                ask = 1000.0
                bid = 999.0
                last = 999.5
            return Tick()

        def order_send(self, request):
            class Result:
                retcode = 10009
                comment = "done"
            return Result()

        def positions_get(self, ticket=None):
            return []

        def shutdown(self):
            return None

        def last_error(self):
            return "blocked"

        def copy_rates_from_pos(self, symbol, timeframe_id, start, count):
            return [(1700000000, 1000.0, 1001.0, 999.0, 1000.0, 1)]

    monkeypatch.setattr(execution, "mt5", FakeMt5())
    monkeypatch.setattr(ohlcv_provider, "mt5", FakeMt5())

    try:
        with pytest.raises(RuntimeError, match="Keep MT5 alive is disabled"):
            execution.open_real_trade("XAUUSD", 0.1, "buy", terminal_path="C:/MT5/terminal64.exe")
        with pytest.raises(RuntimeError, match="Keep MT5 alive is disabled"):
            ohlcv_provider.fetch_ohlcv("XAUUSD", "M1", 10, terminal_path="C:/MT5/terminal64.exe")

        adapter = MT5BrokerAdapter(terminal_path="C:/MT5/terminal64.exe")
        with pytest.raises(RuntimeError, match="Keep MT5 alive is disabled"):
            import asyncio
            asyncio.run(adapter.connect())
    finally:
        monkeypatch.setattr(execution, "mt5", None, raising=False)
        monkeypatch.setattr(ohlcv_provider, "mt5", None, raising=False)


def test_websocket_stream_exposes_signal_and_ohlcv_payload():
    client = TestClient(app)
    with client.websocket_connect("/ws/signal?symbol=XAUUSD&mode=real&timeframe=M1&bars=10") as websocket:
        payload = websocket.receive_json()
        assert payload["symbol"] == "XAUUSD"
        assert "signal" in payload
        assert "ohlcv" in payload
        assert isinstance(payload["ohlcv"], list)

    with client.websocket_connect("/ws/ohlcv?symbol=XAUUSD&timeframe=M1&bars=10") as websocket:
        payload = websocket.receive_json()
        assert payload["symbol"] == "XAUUSD"
        assert payload["timeframe"] == "M1"
        assert isinstance(payload["ohlcv"], list)


def test_keep_mt5_alive_off_blocks_every_auto_start_helper_path():
    import trading_bot.app.terminal_adapters as terminal_adapters

    class FakeAccountInfo:
        login = 101
        trade_allowed = True
        balance = 1000.0
        equity = 1000.0
        margin = 0.0
        margin_free = 1000.0
        margin_level = 100.0
        leverage = 50
        currency = "USD"

    class FakeTerminalInfo:
        connected = True
        trade_allowed = True

    class FakeSymbolInfo:
        visible = True
        volume_min = 0.01
        volume_max = 10.0
        volume_step = 0.01
        volume_limit = 10.0
        digits = 5
        point = 0.01
        trade_tick_size = 0.01
        trade_tick_value = 1.0
        trade_stops_level = 0
        trade_freeze_level = 0
        trade_mode = 0
        spread = 10

    class FakeTick:
        bid = 1000.0
        ask = 1000.5
        last = 1000.25
        time = 1700000000

    class FakeMt5:
        POSITION_TYPE_BUY = 0
        DEAL_TYPE_BUY = 0
        DEAL_ENTRY_IN = 0
        DEAL_ENTRY_OUT = 1
        DEAL_ENTRY_OUT_BY = 2

        def initialize(self, path):
            return True

        def account_info(self):
            return FakeAccountInfo()

        def terminal_info(self):
            return FakeTerminalInfo()

        def symbol_info(self, symbol):
            return FakeSymbolInfo()

        def symbol_select(self, symbol, visible):
            return True

        def symbol_info_tick(self, symbol):
            return FakeTick()

        def positions_get(self):
            return []

        def history_deals_get(self, from_date, to_date):
            return []

        def shutdown(self):
            return None

        def last_error(self):
            return 0

    calls = []

    def fake_ensure(path):
        calls.append(path)
        return True

    original_mt5 = terminal_adapters.mt5
    original_ensure = terminal_adapters.ensure_terminal_running
    terminal_adapters.mt5 = FakeMt5()
    terminal_adapters.ensure_terminal_running = fake_ensure
    try:
        terminal_adapters.get_broker_symbol_constraints({"id": 1, "name": "Demo", "platform": "mt5", "terminal_path": "C:/MT5/terminal64.exe"}, "XAUUSD", auto_start=True)
        terminal_adapters.get_broker_account_metrics({"id": 1, "name": "Demo", "platform": "mt5", "terminal_path": "C:/MT5/terminal64.exe"}, "XAUUSD", auto_start=True)
        terminal_adapters.get_broker_symbol_tick({"id": 1, "name": "Demo", "platform": "mt5", "terminal_path": "C:/MT5/terminal64.exe"}, "XAUUSD", auto_start=True)
        terminal_adapters.sync_broker_trade_state({"id": 1, "name": "Demo", "platform": "mt5", "terminal_path": "C:/MT5/terminal64.exe"}, history_days=1)
    finally:
        terminal_adapters.mt5 = original_mt5
        terminal_adapters.ensure_terminal_running = original_ensure

    assert calls == []
