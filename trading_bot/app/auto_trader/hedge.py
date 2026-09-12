from __future__ import annotations

import time
from typing import Any, Callable

from trading_bot.risk.guards import normalize_side


def trigger_hedge(
    trade: dict[str, Any],
    features: dict[str, Any] | None,
    *,
    get_broker_adapter: Callable[..., Any],
    create_trade_open_record: Callable[..., Any],
    log_auto_trade_event: Callable[..., Any],
    log_trade: Callable[..., Any],
):
    payload = dict(trade or {})
    state = dict(payload.get("state") or {})
    if not bool(state.get("hedge_enabled", False)):
        return {"status": "skip", "reason": "hedge_disabled"}

    floating_loss_ratio = float((features or {}).get("floating_loss_ratio") or 0.0)
    threshold = float(state.get("hedge_threshold") or -0.05)
    if floating_loss_ratio > threshold:
        return {"status": "skip", "reason": "threshold_not_breached"}

    broker = dict(payload.get("broker") or {})
    adapter, adapter_mode = get_broker_adapter(broker, mode=broker.get("execution_mode"))
    if adapter is None:
        return {"status": "error", "reason": "adapter_unavailable"}

    open_rows = list(payload.get("open_rows") or [])
    dominant_side = normalize_side(open_rows[0].get("type") if open_rows else "buy")
    hedge_type = "hedge_sell" if dominant_side == "buy" else "hedge_buy"
    order_side = "SELL" if hedge_type == "hedge_sell" else "BUY"

    symbol = payload.get("symbol") or state.get("auto_trade_symbol") or "XAUUSD"
    lot = float(state.get("lot") or 0.01)

    response = adapter.open_trade(symbol, lot, order_side)
    if not isinstance(response, dict) or str(response.get("status", "")).lower() != "ok":
        return {"status": "error", "reason": "open_failed", "response": response}

    order = dict(response.get("order") or {})
    open_trade_payload = {
        "trade_id": f"hedge:{int(time.time())}",
        "status": "open",
        "type": hedge_type,
        "symbol": symbol,
        "lot": lot,
        "ticket": order.get("ticket"),
        "entry": order.get("price"),
        "entryTime": int(time.time()),
        "reason": "hedge_open",
        "broker_id": (payload.get("broker") or {}).get("id"),
        "broker_name": (payload.get("broker") or {}).get("name"),
        "account_id": (payload.get("metrics") or {}).get("account_id"),
        "platform": (payload.get("broker") or {}).get("platform"),
        "execution_mode": adapter_mode,
        "risk_mode": "hedge",
        "signal_score": (features or {}).get("signal_score"),
    }
    create_trade_open_record(open_trade_payload)

    event_payload = {
        "timestamp": int(time.time()),
        "event_type": "hedge_open",
        "broker_id": open_trade_payload.get("broker_id"),
        "broker_name": open_trade_payload.get("broker_name"),
        "account_id": open_trade_payload.get("account_id"),
        "trade_id": open_trade_payload.get("trade_id"),
        "symbol": symbol,
        "decision": order_side.lower(),
        "reason": "floating_loss_threshold",
        "risk_mode": "hedge",
        "signal_score": (features or {}).get("signal_score"),
    }
    log_auto_trade_event(event_payload)
    log_trade(open_trade_payload, features=features or {}, result={"risk_mode": "hedge", "status": "open"})
    return {"status": "ok", "trade": open_trade_payload}


def release_hedge(
    trade_id: str,
    *,
    list_open_trades: Callable[..., list[dict[str, Any]]],
    get_broker: Callable[..., Any],
    get_default_broker: Callable[..., Any],
    get_broker_adapter: Callable[..., Any],
    close_trade_record: Callable[..., Any],
    log_auto_trade_event: Callable[..., Any],
    log_trade: Callable[..., Any],
):
    rows = list_open_trades()
    target = next((r for r in rows if str(r.get("trade_id")) == str(trade_id)), None)
    if not target:
        return {"status": "error", "reason": "trade_not_found"}

    broker = get_broker(target.get("broker_id")) or get_default_broker() or {}
    adapter, _mode = get_broker_adapter(broker, mode=target.get("execution_mode"))
    if adapter is None:
        return {"status": "error", "reason": "adapter_unavailable"}

    result = adapter.close_trade(target.get("symbol"), float(target.get("lot") or 0.0), target.get("ticket"))
    order = dict((result or {}).get("order") or {})
    close_trade_record(
        target.get("trade_id"),
        exit_price=order.get("price"),
        profit=order.get("profit"),
        exit_time=int(time.time()),
        ticket=order.get("ticket", target.get("ticket")),
        reason="hedge_close:market_normalized",
    )
    log_auto_trade_event(
        {
            "timestamp": int(time.time()),
            "event_type": "hedge_close",
            "trade_id": target.get("trade_id"),
            "symbol": target.get("symbol"),
            "broker_id": target.get("broker_id"),
            "broker_name": target.get("broker_name"),
            "account_id": target.get("account_id"),
            "reason": "market_normalized",
            "risk_mode": "hedge",
            "profit": order.get("profit"),
        }
    )
    log_trade(target, features={}, result={"risk_mode": "hedge", "status": "closed", "profit": order.get("profit")})
    return {"status": "ok", "trade_id": target.get("trade_id")}
