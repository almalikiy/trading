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
