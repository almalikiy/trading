from __future__ import annotations

from typing import Any

from trading_bot.app import db as _db

# Keep legacy imports working while delegating implementation to db.py.
_db.init_db()

get_account_state = _db.get_account_state
save_account_state = _db.save_account_state

list_brokers = _db.list_brokers
get_broker = _db.get_broker
get_default_broker = _db.get_default_broker
resolve_feed_broker = _db.resolve_feed_broker

get_mt5_error_log = _db.get_mt5_error_log
log_mt5_error = _db.log_mt5_error

get_open_trades_count = _db.get_open_trades_count
list_open_trades = _db.list_open_trades
get_trade_history = _db.get_trade_history


def get_broker_by_name(name: str) -> dict[str, Any] | None:
    for broker in list_brokers(include_inactive=True):
        if str(broker.get("name", "")).lower() == str(name).lower():
            return broker
    return None
