from __future__ import annotations

import time
from typing import Any

import app.db as db

_DATASET: list[dict[str, Any]] = []
_MODEL: dict[str, Any] | None = None
_MODEL_META: dict[str, Any] = {
    "trained_trade_count": 0,
    "updated_at": 0,
    "model_type": "none",
}


def log_trade(trade: dict[str, Any], features: dict[str, Any] | None = None, result: dict[str, Any] | None = None) -> None:
    payload = {
        "trade": dict(trade or {}),
        "features": dict(features or {}),
        "result": dict(result or {}),
        "risk_mode": (result or {}).get("risk_mode") or (trade or {}).get("risk_mode") or "fixed_lot",
        "timestamp": int(time.time()),
    }
    _DATASET.append(payload)

    if trade:
        try:
            db.upsert_trade_history_record(dict(trade))
        except Exception:
            pass


def get_dataset(limit: int = 1000) -> list[dict[str, Any]]:
    safe_limit = max(1, int(limit or 1))
    return list(_DATASET[-safe_limit:])


def train_risk_mode_model(dataset: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    global _MODEL
    rows = list(dataset if dataset is not None else _DATASET)
    if len(rows) < 2:
        return {"trained": False, "reason": "insufficient_data", "rows": len(rows)}

    buckets: dict[str, dict[str, float]] = {}
    for row in rows:
        mode = str(row.get("risk_mode") or (row.get("result") or {}).get("risk_mode") or "fixed_lot")
        profit = float((row.get("result") or {}).get("profit") or (row.get("trade") or {}).get("profit") or 0.0)
        item = buckets.setdefault(mode, {"sum": 0.0, "count": 0.0})
        item["sum"] += profit
        item["count"] += 1.0

    mode_scores = {
        mode: (vals["sum"] / vals["count"]) if vals["count"] > 0 else 0.0
        for mode, vals in buckets.items()
    }
    best_mode = max(mode_scores.items(), key=lambda x: x[1])[0]

    _MODEL = {
        "mode_scores": mode_scores,
        "best_mode": best_mode,
    }
    _MODEL_META["trained_trade_count"] = len(_DATASET)
    _MODEL_META["updated_at"] = int(time.time())
    _MODEL_META["model_type"] = "heuristic_avg_profit"

    return {
        "trained": True,
        "rows": len(rows),
        "model_type": _MODEL_META["model_type"],
        "best_mode": best_mode,
    }


def predict_risk_mode(features: dict[str, Any]) -> dict[str, Any]:
    global _MODEL
    retrain = None
    if _MODEL is None:
        retrain = train_risk_mode_model(get_dataset(limit=50000))

    new_closed_since_train = len(_DATASET) - int(_MODEL_META.get("trained_trade_count") or 0)
    if new_closed_since_train >= 100:
        retrain = train_risk_mode_model(get_dataset(limit=50000))

    if _MODEL is None:
        return {"risk_mode": "fixed_lot", "confidence": 0.0, "retrain": retrain}

    mode_scores = dict(_MODEL.get("mode_scores") or {})
    if not mode_scores:
        return {"risk_mode": "fixed_lot", "confidence": 0.0, "retrain": retrain}

    best_mode = str(_MODEL.get("best_mode") or max(mode_scores.items(), key=lambda x: x[1])[0])
    values = list(mode_scores.values())
    confidence = 1.0 if len(values) <= 1 else min(1.0, max(0.0, (max(values) - min(values)) / (abs(max(values)) + 1e-9)))
    return {
        "risk_mode": best_mode,
        "confidence": confidence,
        "retrain": retrain,
    }


def log_mt5_error(message: Any, **kwargs: Any) -> None:
    try:
        db.log_mt5_error(message=message, **kwargs)
    except Exception:
        pass


def get_close_decision_dataset(limit: int = 200, broker_id: int | None = None, account_id: int | None = None) -> list[dict[str, Any]]:
    rows = db.get_recent_closed_trades(limit=limit, broker_id=broker_id, account_id=account_id)
    dataset = []
    for row in rows:
        reason = str(row.get("reason") or "").lower()
        if "stop" in reason or "sl" in reason:
            family = "sl"
        elif "tp" in reason or "take_profit" in reason:
            family = "tp"
        elif "hedge" in reason:
            family = "hedge"
        else:
            family = "other"

        dataset.append(
            {
                "features": {
                    "signal_score": row.get("signal_score"),
                    "spread_points": row.get("spread_points"),
                    "margin_usage_pct": row.get("margin_usage_pct"),
                    "atr_value": row.get("atr_value"),
                    "mfe_price_distance": row.get("mfe_price_distance"),
                    "mae_price_distance": row.get("mae_price_distance"),
                },
                "result": {
                    "close_reason_family": family,
                    "profit": row.get("profit"),
                    "target_crossed_before_close": bool(row.get("target_first_crossed_at")),
                },
                "meta": {
                    "trade_id": row.get("trade_id"),
                    "symbol": row.get("symbol"),
                    "type": row.get("type"),
                },
            }
        )
    return dataset
