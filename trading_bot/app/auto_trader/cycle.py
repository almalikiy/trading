from __future__ import annotations

import time
from typing import Any, Callable

from trading_bot.app.auto_trader.guards import normalize_side


def run_auto_trade_cycle(
    *,
    get_account_state: Callable[..., dict[str, Any]],
    get_feed_broker: Callable[..., dict[str, Any] | None],
    list_open_trades: Callable[..., list[dict[str, Any]]],
    get_broker: Callable[..., Any],
    get_default_broker: Callable[..., Any],
    get_broker_adapter: Callable[..., Any],
    get_broker_symbol_tick: Callable[..., dict[str, Any]],
    close_trade_record: Callable[..., Any],
    analyze_symbol: Callable[..., dict[str, Any]],
    signal_strength: Callable[..., dict[str, Any]],
    diag_event: Callable[..., Any],
    diag_close_attempt: Callable[..., Any],
) -> None:
    diag_event("cycle", "start")
    state = get_account_state()
    if not bool(state.get("auto_trade_enabled", False)):
        diag_event("skip", "auto_trade_disabled")
        return

    feed_broker = get_feed_broker(state)
    symbol = state.get("auto_trade_symbol") or "XAUUSD"
    if feed_broker and feed_broker.get("default_symbol"):
        symbol = feed_broker.get("default_symbol")
    symbol = str(symbol)

    open_rows = list_open_trades()
    now_ts = int(time.time())

    score_payload = signal_strength(analyze_symbol(symbol=symbol, mode="real"), state)
    diag_event(
        "analysis",
        "signal_ready",
        symbol=symbol,
        signal=str(score_payload.get("direction") or "wait"),
        signal_score=float(score_payload.get("score") or 0.0),
    )

    for row in open_rows:
        row_symbol = row.get("symbol") or state.get("auto_trade_symbol") or "XAUUSD"
        broker = get_broker(row.get("broker_id")) or get_default_broker() or {}
        adapter, _mode = get_broker_adapter(broker, mode=row.get("execution_mode"))
        if adapter is None:
            continue

        tick = get_broker_symbol_tick(broker, row_symbol)
        if not tick or not tick.get("ready"):
            continue

        side = normalize_side(row.get("type"))
        entry = float(row.get("entry") or 0.0)
        tp_value = float(row.get("tpValue") or 0.0)
        sl_value = float(row.get("slValue") or 0.0)
        close_price = float(tick.get("close_buy_price") if side == "buy" else tick.get("close_sell_price") or 0.0)

        hit_tp = False
        hit_sl = False
        if side == "buy":
            hit_tp = tp_value > 0 and close_price >= (entry + tp_value)
            hit_sl = sl_value > 0 and close_price <= (entry - sl_value)
        else:
            hit_tp = tp_value > 0 and close_price <= (entry - tp_value)
            hit_sl = sl_value > 0 and close_price >= (entry + sl_value)

        if not hit_tp and not hit_sl:
            continue

        diag_close_attempt("attempt", trade_id=row.get("trade_id"), symbol=row_symbol, ticket=row.get("ticket"))
        response = adapter.close_trade(row_symbol, float(row.get("lot") or 0.0), row.get("ticket"))
        order = dict((response or {}).get("order") or {})
        close_trade_record(
            row.get("trade_id"),
            exit_price=order.get("price", close_price),
            profit=order.get("profit"),
            exit_time=now_ts,
            ticket=order.get("ticket", row.get("ticket")),
            reason="auto_close_tp" if hit_tp else "auto_close_sl",
            runtime_metrics={},
        )
        diag_close_attempt("ok", trade_id=row.get("trade_id"), symbol=row_symbol, ticket=order.get("ticket", row.get("ticket")))
        diag_event("action", "auto_close_done", symbol=row_symbol)
