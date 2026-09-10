from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ACCOUNT_STATE_PATH = ROOT / "account_state.json"


def _default_account_state() -> dict[str, Any]:
    return {
        "auto_trade_enabled": False,
        "enable_real_trade": False,
        "auto_trade_symbol": "XAUUSD",
        "max_open_trades": 1,
        "lot": 0.01,
        "auto_trade_risk_percent": 1.0,
        "data_feed_broker_id": 1,
    }


def get_account_state() -> dict[str, Any]:
    if not ACCOUNT_STATE_PATH.exists():
        state = _default_account_state()
        save_account_state(state)
        return state

    try:
        with ACCOUNT_STATE_PATH.open("r", encoding="utf-8") as fh:
            loaded = json.load(fh)
        if isinstance(loaded, dict):
            merged = _default_account_state()
            merged.update(loaded)
            return merged
    except (json.JSONDecodeError, OSError):
        pass

    state = _default_account_state()
    save_account_state(state)
    return state


def save_account_state(state: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(state or {})
    ACCOUNT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ACCOUNT_STATE_PATH.open("w", encoding="utf-8") as fh:
        json.dump(cleaned, fh, indent=2, sort_keys=True)
    return cleaned


def list_brokers(include_inactive: bool = False) -> list[dict[str, object]]:
    brokers = [
        {
            "id": 1,
            "name": "MT5 Demo",
            "platform": "mt5",
            "terminal_path": None,
            "execution_mode": "mouse",
            "default_symbol": "XAUUSD",
            "is_default": True,
            "is_active": True,
            "available": True,
        },
        {
            "id": 2,
            "name": "Binance Demo",
            "platform": "binance",
            "terminal_path": None,
            "execution_mode": "api",
            "default_symbol": "BTCUSDT",
            "is_default": False,
            "is_active": True,
            "available": True,
        },
    ]
    return [broker for broker in brokers if include_inactive or bool(broker.get("is_active"))]


def get_broker(broker_id: int | str | None) -> dict[str, object] | None:
    if broker_id is None:
        return None
    for broker in list_brokers(include_inactive=True):
        if str(broker.get("id")) == str(broker_id):
            return broker
    return None


def get_default_broker() -> dict[str, object] | None:
    for broker in list_brokers(include_inactive=True):
        if bool(broker.get("is_default")):
            return broker
    brokers = list_brokers(include_inactive=True)
    return brokers[0] if brokers else None


def get_mt5_error_log() -> list[dict[str, object]]:
    return []


def get_open_trades_count() -> int:
    return 0


def list_open_trades() -> list[dict[str, object]]:
    return []


def get_trade_history() -> list[dict[str, object]]:
    return []


def get_broker_by_name(name: str) -> dict[str, object] | None:
    for broker in list_brokers(include_inactive=True):
        if str(broker.get("name", "")).lower() == str(name).lower():
            return broker
    return None
