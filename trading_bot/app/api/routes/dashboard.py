from __future__ import annotations

import time

from fastapi import APIRouter

from trading_bot.app import db
from trading_bot.app.persistence.account_store import get_account_state
from trading_bot.app.persistence.broker_store import list_brokers
from trading_bot.app.persistence.trade_store import get_open_trades_count
from trading_bot.app.terminal_adapters import sync_trade_state_for_history_flow_in_background


def sync_trade_state_for_history_flow(*args, **kwargs):
    return sync_trade_state_for_history_flow_in_background(*args, **kwargs)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _fallback_brokers() -> list[dict[str, object]]:
    return [
        {
            "id": 1,
            "name": "Default Broker",
            "platform": "mt5",
            "default_symbol": "XAUUSD",
            "is_default": True,
            "is_active": True,
            "available": True,
            "execution_mode": "mouse",
            "terminal_path": None,
        }
    ]


@router.get("/summary")
async def dashboard_summary() -> dict[str, object]:
    brokers = list_brokers(include_inactive=True)
    if not brokers:
        brokers = _fallback_brokers()

    state = get_account_state()
    trade_sync = sync_trade_state_for_history_flow_in_background(state=state, timeout_sec=0.75)
    open_count = max(0, int(get_open_trades_count()))
    stats_30d = db.get_auto_trade_statistics(window_days=30)
    recent_events = db.get_auto_trade_events(limit=10)

    normalized = []
    for broker in brokers:
        normalized.append(
            {
                "id": broker.get("id"),
                "name": broker.get("name"),
                "platform": broker.get("platform"),
                "default_symbol": broker.get("default_symbol"),
                "is_default": bool(broker.get("is_default")),
                "is_active": bool(broker.get("is_active")),
                "available": bool(broker.get("is_active")),
                "execution_mode": broker.get("execution_mode"),
                "terminal_path": broker.get("terminal_path"),
            }
        )

    return {
        "status": "ready",
        "timestamp": int(time.time()),
        "brokers": normalized,
        "trade_sync": trade_sync,
        "accounting": "service_ready",
        "account": {
            "balance": state.get("balance"),
            "equity": state.get("equity"),
            "auto_trade_enabled": bool(state.get("auto_trade_enabled", False)),
            "enable_real_trade": bool(state.get("enable_real_trade", False)),
            "symbol": state.get("auto_trade_symbol") or "XAUUSD",
        },
        "trading": {
            "open_positions": open_count,
            "closed_trades_30d": stats_30d.get("closed_trades", 0),
            "winrate_30d": stats_30d.get("winrate", 0.0),
            "net_profit_30d": stats_30d.get("net_profit", 0.0),
            "profit_factor_30d": stats_30d.get("profit_factor"),
        },
        "events": {
            "recent_count": len(recent_events),
            "recent": recent_events,
        },
    }
