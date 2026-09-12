from __future__ import annotations

from typing import Any

from trading_bot.app import db


def get_account_state() -> dict[str, Any]:
    return db.get_account_state()


def save_account_state(state: dict[str, Any]) -> None:
    db.save_account_state(state)
