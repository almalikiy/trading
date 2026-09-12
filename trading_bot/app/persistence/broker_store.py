from __future__ import annotations

from typing import Any

from trading_bot.app import db


def list_brokers(include_inactive: bool = False) -> list[dict[str, Any]]:
    return db.list_brokers(include_inactive=include_inactive)


def get_default_broker() -> dict[str, Any] | None:
    return db.get_default_broker()
