from __future__ import annotations

from typing import Any, Callable


def normalize_side(value: Any) -> str:
    side = str(value or "").strip().lower()
    if "sell" in side:
        return "sell"
    return "buy"


def passes_direction_bias_guard(
    direction: str,
    get_recent_closed_trades: Callable[..., list[dict[str, Any]]],
    broker_id: int | None = None,
    account_id: int | None = None,
):
    recent = get_recent_closed_trades(limit=18, broker_id=broker_id, account_id=account_id)
    side = normalize_side(direction)
    consecutive_losses = 0

    for row in recent:
        row_side = normalize_side(row.get("type"))
        if row_side != side:
            break
        profit = float(row.get("profit") or 0.0)
        if profit < 0:
            consecutive_losses += 1
            continue
        break

    if consecutive_losses >= 3:
        return False, {
            "reason": "direction_loss_streak_guard",
            "consecutive_losses_same_side": consecutive_losses,
        }

    return True, {
        "reason": None,
        "consecutive_losses_same_side": consecutive_losses,
    }


def passes_same_direction_open_guard(state: dict[str, Any], open_rows: list[dict[str, Any]], direction: str, max_open_trades: int):
    cap = int(state.get("auto_trade_max_same_direction_trades") or max(1, int(max_open_trades or 1)))
    side = normalize_side(direction)
    same_side_open = sum(1 for row in open_rows if normalize_side(row.get("type")) == side)
    if same_side_open >= cap:
        return False, {
            "reason": "same_direction_open_limit",
            "same_side_open": same_side_open,
            "limit": cap,
        }
    return True, {
        "reason": None,
        "same_side_open": same_side_open,
        "limit": cap,
    }


def build_adaptive_target_snapshot(trade_row: dict[str, Any], recent_closed_rows: list[dict[str, Any]] | None = None):
    recent = list(recent_closed_rows or [])
    side = normalize_side(trade_row.get("type"))
    symbol = str(trade_row.get("symbol") or "")
    same_side = [r for r in recent if normalize_side(r.get("type")) == side and str(r.get("symbol") or "") == symbol]
    sample = same_side[:12]

    wins = sum(1 for r in sample if float(r.get("profit") or 0.0) > 0.0)
    winrate = (wins / len(sample)) if sample else 0.5
    signal_score = float((trade_row.get("signal_context") or {}).get("score") or trade_row.get("signal_score") or 0.5)
    strength_bonus = max(0.0, signal_score - 0.6)

    factor = 1.0 + (0.6 * winrate) + (0.8 * strength_bonus)
    factor = max(0.8, min(2.4, factor))

    entry = float(trade_row.get("entry") or 0.0)
    base_tp = float(trade_row.get("tpValue") or 0.0)
    effective_tp = max(0.0, base_tp * factor)

    if side == "buy":
        target_price = entry + effective_tp
    else:
        target_price = entry - effective_tp

    return {
        "mode": "adaptive",
        "target_factor": factor,
        "target_price": target_price,
        "effective_tp_value": effective_tp,
        "recent_samples": len(sample),
    }


def should_release_hedge(state: dict[str, Any], metrics: dict[str, Any], hedge_rows: list[dict[str, Any]]) -> bool:
    if not hedge_rows:
        return False
    balance = float(metrics.get("balance") or 0.0)
    equity = float(metrics.get("equity") or balance)
    if balance <= 0:
        return False
    floating_loss_ratio = (equity - balance) / balance
    threshold = float(state.get("hedge_threshold") or -0.05)
    return floating_loss_ratio > threshold
