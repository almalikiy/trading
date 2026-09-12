import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import trading_bot.app.auto_trader as auto_trader
import trading_bot.app.terminal_adapters as terminal_adapters


def test_mt5_access_has_global_lock():
    assert hasattr(terminal_adapters, "_MT5_LOCK")
    assert isinstance(terminal_adapters._MT5_LOCK, type(threading.Lock()))


def test_mt5_auto_start_defaults_are_disabled():
    assert terminal_adapters.probe_broker_order_status.__defaults__[-1] is False
    assert terminal_adapters.get_broker_symbol_constraints.__defaults__[-1] is False
    assert terminal_adapters.get_broker_account_metrics.__defaults__[-1] is False
    assert terminal_adapters.get_broker_symbol_tick.__defaults__[-1] is False


def test_normalize_lot_with_constraints_snaps_to_step_and_bounds():
    constraints = {
        "volume_min": 0.01,
        "volume_max": 1.0,
        "volume_step": 0.05,
    }

    assert terminal_adapters.normalize_lot_with_constraints(0.001, constraints) == 0.01
    assert terminal_adapters.normalize_lot_with_constraints(1.8, constraints) == 1.0
    assert terminal_adapters.normalize_lot_with_constraints(0.17, constraints) == 0.16


def test_broker_order_status_snapshot_non_mt5_is_ready_without_terminal():
    broker = {
        "id": 9,
        "name": "Binance Test",
        "platform": "binance",
        "execution_mode": "direct",
        "terminal_path": None,
    }

    payload = terminal_adapters.get_broker_order_status_snapshot(broker, symbol="BTCUSDT")

    assert payload["broker_id"] == 9
    assert payload["can_open_order"] is True
    assert payload["reason"] == "non_mt5_platform"


def test_auto_trader_wrapper_uses_canonical_terminal_adapter_resolution(monkeypatch):
    broker = {"platform": "mt4", "window_hint": "Legacy Window", "execution_mode": "direct"}

    adapter, method = auto_trader.get_broker_adapter(broker, mode="direct")

    assert method == "mouse"
    assert getattr(adapter, "terminal_type", None) == "mouse"
