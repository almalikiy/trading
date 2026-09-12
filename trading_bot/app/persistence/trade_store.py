from __future__ import annotations

from typing import Any

from trading_bot.app import db


def get_open_trades_count() -> int:
    return db.get_open_trades_count()


def get_trade_history() -> list[dict[str, Any]]:
    return db.get_trade_history()
