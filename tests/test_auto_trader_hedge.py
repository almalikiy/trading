import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.auto_trader as auto_trader


class _DummyAdapter:
    def __init__(self):
        self.open_calls = []
        self.close_calls = []

    def open_trade(self, symbol, lot, side):
        self.open_calls.append((symbol, lot, side))
        return {"status": "ok", "order": {"ticket": 111, "price": 1234.5}}

    def close_trade(self, symbol, lot, ticket):
        self.close_calls.append((symbol, lot, ticket))
        return {"status": "ok", "order": {"ticket": ticket, "price": 1235.0, "profit": 8.5}}


def _base_state():
    return {
        "hedge_enabled": True,
        "hedge_threshold": -0.05,
        "hedge_slots": 2,
        "lot": 0.1,
    }


def test_trigger_hedge_opens_when_floating_loss_breaches_threshold(monkeypatch):
    adapter = _DummyAdapter()
    open_records = []
    event_records = []

    monkeypatch.setattr(auto_trader, "get_broker_adapter", lambda broker, mode=None: (adapter, "mt5"))
    monkeypatch.setattr(auto_trader, "create_trade_open_record", lambda payload: open_records.append(dict(payload)))
    monkeypatch.setattr(auto_trader, "log_auto_trade_event", lambda payload: event_records.append(dict(payload)))
    monkeypatch.setattr(auto_trader, "log_trade", lambda trade, features=None, result=None: None)

    trade = {
        "state": _base_state(),
        "broker": {"id": "b1", "name": "Broker One", "platform": "mt5"},
        "symbol": "XAUUSD",
        "metrics": {
            "balance": 1000.0,
            "equity": 940.0,
            "margin_free": 500.0,
            "estimated_margin_per_lot": 100.0,
            "spread_points": 15,
            "account_id": "acc-1",
        },
        "constraints": {
            "can_open_order": False,
            "volume_step": None,
        },
        "open_rows": [
            {"trade_id": "n1", "type": "BUY", "lot": 0.2, "risk_mode": "fixed_lot"},
        ],
    }

    features = {"floating_loss_ratio": -0.06, "signal_score": 0.72}

    result = auto_trader.trigger_hedge(trade, features)

    assert result["status"] == "ok"
    assert adapter.open_calls, "expected adapter.open_trade to be called"
    assert open_records, "expected trade open record to be created"
    assert open_records[0]["risk_mode"] == "hedge"
    assert open_records[0]["type"] in ("hedge_buy", "hedge_sell")
    assert any(e.get("event_type") == "hedge_open" for e in event_records)


def test_release_hedge_closes_existing_hedge_trade(monkeypatch):
    adapter = _DummyAdapter()
    closed_records = []
    events = []

    monkeypatch.setattr(
        auto_trader,
        "list_open_trades",
        lambda: [
            {
                "trade_id": "h1",
                "status": "open",
                "type": "hedge_sell",
                "symbol": "XAUUSD",
                "lot": 0.1,
                "ticket": 321,
                "entry": 2000.0,
                "entryTime": int(time.time()) - 60,
                "broker_id": "b1",
                "broker_name": "Broker One",
                "account_id": "acc-1",
                "platform": "mt5",
                "execution_mode": "mt5",
                "risk_mode": "hedge",
                "signal_score": 0.5,
                "spread_points": 12,
                "margin_usage_pct": 10.0,
                "equity": 980.0,
                "balance": 1000.0,
            }
        ],
    )
    monkeypatch.setattr(auto_trader, "get_broker", lambda broker_id: {"id": broker_id, "name": "Broker One", "platform": "mt5"})
    monkeypatch.setattr(auto_trader, "get_default_broker", lambda: None)
    monkeypatch.setattr(auto_trader, "get_broker_adapter", lambda broker, mode=None: (adapter, "mt5"))
    monkeypatch.setattr(
        auto_trader,
        "close_trade_record",
        lambda trade_id, exit_price=None, profit=None, exit_time=None, ticket=None, reason=None: closed_records.append(
            {
                "trade_id": trade_id,
                "exit_price": exit_price,
                "profit": profit,
                "exit_time": exit_time,
                "ticket": ticket,
                "reason": reason,
            }
        ),
    )
    monkeypatch.setattr(auto_trader, "log_auto_trade_event", lambda payload: events.append(dict(payload)))
    monkeypatch.setattr(auto_trader, "log_trade", lambda trade, features=None, result=None: None)

    result = auto_trader.release_hedge("h1")

    assert result["status"] == "ok"
    assert adapter.close_calls == [("XAUUSD", 0.1, 321)]
    assert closed_records, "expected close_trade_record to be called"
    assert closed_records[0]["reason"] == "hedge_close:market_normalized"
    assert any(e.get("event_type") == "hedge_close" for e in events)


def test_should_release_hedge_true_when_loss_recovers(monkeypatch):
    state = {"hedge_threshold": -0.05}
    metrics = {"balance": 1000.0, "equity": 998.0}
    hedge_rows = [{"trade_id": "h1", "risk_mode": "hedge"}]

    assert auto_trader._should_release_hedge(state, metrics, hedge_rows) is True


def test_direction_bias_guard_blocks_consecutive_same_side_losses(monkeypatch):
    monkeypatch.setattr(
        auto_trader,
        "get_recent_closed_trades",
        lambda limit=18, broker_id=None, account_id=None: [
            {"type": "SELL", "profit": -30.0},
            {"type": "SELL", "profit": -22.0},
            {"type": "SELL", "profit": -11.0},
            {"type": "BUY", "profit": 10.0},
        ],
    )

    allowed, meta = auto_trader._passes_direction_bias_guard("sell", broker_id=1, account_id=2)
    assert allowed is False
    assert meta["reason"] == "direction_loss_streak_guard"
    assert meta["consecutive_losses_same_side"] == 3


def test_direction_bias_guard_allows_when_recent_is_healthy(monkeypatch):
    monkeypatch.setattr(
        auto_trader,
        "get_recent_closed_trades",
        lambda limit=18, broker_id=None, account_id=None: [
            {"type": "SELL", "profit": 12.0},
            {"type": "SELL", "profit": -5.0},
            {"type": "BUY", "profit": 8.0},
            {"type": "BUY", "profit": -3.0},
        ],
    )

    allowed, meta = auto_trader._passes_direction_bias_guard("sell", broker_id=1, account_id=2)
    assert allowed is True
    assert meta["reason"] is None


def test_same_direction_open_guard_blocks_when_cap_reached():
    state = {"auto_trade_max_same_direction_trades": 2}
    open_rows = [
        {"type": "SELL", "trade_id": "s1"},
        {"type": "SELL", "trade_id": "s2"},
        {"type": "BUY", "trade_id": "b1"},
    ]

    allowed, meta = auto_trader._passes_same_direction_open_guard(state, open_rows, "sell", max_open_trades=5)
    assert allowed is False
    assert meta["reason"] == "same_direction_open_limit"
    assert meta["same_side_open"] == 2


def test_build_adaptive_target_snapshot_uses_signal_context_and_recent_history(monkeypatch):
    trade_row = {
        "type": "SELL",
        "symbol": "XAUUSD",
        "entry": 2400.0,
        "tpValue": 10.0,
        "slValue": 5.0,
        "signal_score": 0.74,
        "signal_context": {
            "score": 0.74,
            "timeframes": {
                "M1": {"direction": "sell", "atr": 3.0},
                "M5": {"direction": "sell", "atr": 3.2},
                "M15": {"direction": "sell", "atr": 3.1},
                "M30": {"direction": "buy", "atr": 3.3},
            },
        },
    }
    recent = [
        {"type": "SELL", "symbol": "XAUUSD", "profit": 120.0},
        {"type": "SELL", "symbol": "XAUUSD", "profit": 90.0},
        {"type": "SELL", "symbol": "XAUUSD", "profit": -20.0},
        {"type": "BUY", "symbol": "XAUUSD", "profit": 30.0},
    ]

    snapshot = auto_trader.build_adaptive_target_snapshot(trade_row, {}, recent_closed_rows=recent)

    assert snapshot["mode"] == "adaptive"
    assert snapshot["target_price"] is not None
    assert snapshot["target_price"] < trade_row["entry"]
    assert snapshot["effective_tp_value"] > trade_row["tpValue"]
    assert snapshot["recent_samples"] == 3


def test_run_auto_trade_cycle_closes_sell_using_trade_direction_tick_side(monkeypatch):
    adapter = _DummyAdapter()
    closed_records = []
    broker = {"id": 1, "name": "Broker One", "platform": "mt5", "terminal_path": "C:/terminal64.exe", "execution_mode": "direct", "default_symbol": "XAUUSD"}
    open_trade = {
        "trade_id": "open-sell-1",
        "status": "open",
        "type": "SELL",
        "symbol": "XAUUSD",
        "lot": 0.1,
        "ticket": 99,
        "entry": 4280.0,
        "entryTime": int(time.time()) - 60,
        "tpValue": 5.0,
        "slValue": 8.0,
        "broker_id": 1,
        "broker_name": "Broker One",
        "account_id": 123,
        "platform": "mt5",
        "execution_mode": "direct",
        "terminal_path": "C:/terminal64.exe",
        "signal_score": 0.68,
        "risk_mode": "fixed_lot",
        "signal_context": {
            "score": 0.68,
            "timeframes": {
                "M1": {"direction": "sell", "atr": 3.0},
                "M5": {"direction": "sell", "atr": 3.1},
            },
        },
    }
    state = {
        "auto_trade_enabled": True,
        "enable_real_trade": True,
        "auto_trade_session_start_hour": 0,
        "auto_trade_session_end_hour": 24,
        "auto_trade_cooldown_sec": 0,
        "auto_trade_atr_period": 14,
        "auto_trade_min_signal_score": 0.0,
        "auto_trade_confidence_threshold": 0.0,
        "max_open_trades": 1,
        "auto_trade_allow_sell": True,
        "keep_terminal_alive": False,
        "auto_trade_use_atr_tpsl": False,
        "auto_trade_partial_tp_enabled": False,
        "auto_trade_break_even_enabled": False,
        "auto_trade_trailing_enabled": False,
        "auto_trade_symbol": "XAUUSD",
    }

    monkeypatch.setattr(auto_trader, "get_account_state", lambda: dict(state))
    monkeypatch.setattr(auto_trader, "_get_feed_broker", lambda current_state: broker)
    monkeypatch.setattr(auto_trader, "get_broker_account_metrics", lambda *args, **kwargs: {"account_id": 123, "balance": 1000.0, "equity": 1000.0, "margin_free": 1000.0, "estimated_margin_per_lot": 10.0, "spread_points": 10, "can_trade": True})
    monkeypatch.setattr(auto_trader, "apply_auto_trade_profile_to_state", lambda base_state, broker_id, account_id: base_state)
    monkeypatch.setattr(auto_trader, "_resolve_auto_open_broker", lambda current_state, symbol: (broker, {"can_open_order": True}))
    monkeypatch.setattr(auto_trader, "analyze_symbol", lambda *args, **kwargs: {"signal": "buy", "indicators": {"M1": {"atr": 3.0}}})
    monkeypatch.setattr(auto_trader, "_signal_strength", lambda payload, current_state: {"buy": 0.7, "sell": 0.3, "direction": "buy", "score": 0.7, "per_timeframe": {}})
    monkeypatch.setattr(auto_trader, "log_auto_trade_event", lambda payload: None)
    monkeypatch.setattr(auto_trader, "log_trade", lambda trade, features=None, result=None: None)
    monkeypatch.setattr(auto_trader, "list_open_trades", lambda broker_id=None: [dict(open_trade)])
    monkeypatch.setattr(auto_trader, "get_broker", lambda broker_id: broker)
    monkeypatch.setattr(auto_trader, "get_default_broker", lambda: broker)
    monkeypatch.setattr(auto_trader, "get_broker_adapter", lambda broker_payload, mode=None: (adapter, "direct"))
    monkeypatch.setattr(auto_trader, "get_broker_symbol_tick", lambda *args, **kwargs: {"ready": True, "close_buy_price": 4305.0, "close_sell_price": 4270.0, "mid": 4287.5})
    monkeypatch.setattr(auto_trader, "get_broker_symbol_constraints", lambda *args, **kwargs: {})
    monkeypatch.setattr(auto_trader, "_apply_partial_take_profit", lambda *args, **kwargs: False)
    monkeypatch.setattr(auto_trader, "_apply_break_even_lock", lambda *args, **kwargs: None)
    monkeypatch.setattr(auto_trader, "_apply_trailing_policy", lambda *args, **kwargs: None)
    monkeypatch.setattr(auto_trader, "_passes_direction_bias_guard", lambda *args, **kwargs: (True, {"reason": None}))
    monkeypatch.setattr(auto_trader, "_passes_same_direction_open_guard", lambda *args, **kwargs: (True, {"reason": None}))
    monkeypatch.setattr(auto_trader, "trigger_hedge", lambda *args, **kwargs: None)
    monkeypatch.setattr(auto_trader, "_should_release_hedge", lambda *args, **kwargs: False)
    monkeypatch.setattr(auto_trader, "close_trade_record", lambda trade_id, exit_price=None, profit=None, exit_time=None, ticket=None, reason=None, runtime_metrics=None: closed_records.append({"trade_id": trade_id, "exit_price": exit_price, "profit": profit, "ticket": ticket, "reason": reason, "runtime_metrics": runtime_metrics}))

    auto_trader._run_auto_trade_cycle()

    assert adapter.close_calls == [("XAUUSD", 0.1, 99)]
    assert closed_records
    assert closed_records[0]["trade_id"] == "open-sell-1"
    assert closed_records[0]["reason"] == "auto_close_tp"
