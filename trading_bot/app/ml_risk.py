#file: trading_bot/app/ml_risk.py
from __future__ import annotations

import json
import time
from typing import Any

from trading_bot.app import db

MODEL_TYPES = ("fixed_lot", "risk_percent", "balance_scaled", "atr_dynamic")
_MODEL: dict[str, Any] | None = None
_MODEL_META: dict[str, Any] = {
    "trained_trade_count": 0,
    "updated_at": 0,
    "model_type": "none",
}


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_json_loads(value: Any) -> Any:
    if value in (None, ""):
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return None


def _coerce_features(raw: Any) -> dict[str, float | int | str | None]:
    if isinstance(raw, dict):
        features = dict(raw)
    else:
        features = {}
    payload: dict[str, float | int | str | None] = {}
    for key in ("atr", "atr_value", "spread_points", "signal_score", "margin_usage_pct", "balance", "equity", "session_time", "session_hour"):
        if key in features:
            payload[key] = features[key]
    if "atr" not in payload and "atr_value" in features:
        payload["atr"] = features["atr_value"]
    if "session_time" not in payload and "session_hour" in features:
        payload["session_time"] = features["session_hour"]
    return payload


def _normalize_risk_mode(value: Any) -> str:
    mode = str(value or "").strip().lower()
    if mode in MODEL_TYPES:
        return mode
    return "fixed_lot"


def _close_reason_family(reason: Any) -> str:
    text = str(reason or "").lower()
    if "sl" in text or "stop" in text:
        return "sl"
    if "tp" in text or "take" in text or "target" in text:
        return "tp"
    if "hedge" in text:
        return "hedge"
    return "unknown"


def _build_trade_payload(trade: dict[str, Any], features: dict[str, Any] | None = None, result: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(trade or {})
    payload.setdefault("status", payload.get("status") or ("open" if payload.get("exitTime") is None else "closed"))
    payload.setdefault("type", "BUY")
    payload.setdefault("symbol", "XAUUSD")
    payload.setdefault("trade_id", f"ml-risk-{int(time.time() * 1000)}")
    payload.setdefault("entryTime", int(time.time()))
    payload.setdefault("exitTime", int(time.time()))
    payload.setdefault("account_id", payload.get("account_id") or 0)
    payload.setdefault("broker_id", payload.get("broker_id") or 1)
    payload.setdefault("broker_name", payload.get("broker_name") or "Default Broker")
    payload.setdefault("platform", payload.get("platform") or "mt5")
    payload.setdefault("execution_mode", payload.get("execution_mode") or "direct")
    payload.setdefault("terminal_path", payload.get("terminal_path") or "")

    normalized_features = _coerce_features(features)
    if normalized_features:
        payload["signal_context"] = dict(normalized_features)
        payload["signal_context_json"] = json.dumps(normalized_features, ensure_ascii=True)

    if result:
        risk_mode = _normalize_risk_mode(result.get("risk_mode") or payload.get("risk_mode"))
        payload["risk_mode"] = risk_mode
        payload["profit"] = payload.get("profit") if payload.get("profit") is not None else result.get("profit")
    else:
        payload["risk_mode"] = _normalize_risk_mode(payload.get("risk_mode"))

    if features:
        payload["signal_score"] = _safe_float((features or {}).get("signal_score") or (features or {}).get("score"), payload.get("signal_score"))
        payload["spread_points"] = _safe_float((features or {}).get("spread_points"), payload.get("spread_points"))
        payload["margin_usage_pct"] = _safe_float((features or {}).get("margin_usage_pct"), payload.get("margin_usage_pct"))
        payload["atr_value"] = _safe_float((features or {}).get("atr") or (features or {}).get("atr_value"), payload.get("atr_value"))
        payload["session_hour"] = _safe_float((features or {}).get("session_time") or (features or {}).get("session_hour"), payload.get("session_hour"))

    if payload.get("signal_context") is not None and not isinstance(payload.get("signal_context"), dict):
        tmp = _safe_json_loads(payload.get("signal_context"))
        if isinstance(tmp, dict):
            payload["signal_context"] = tmp
            payload["signal_context_json"] = json.dumps(tmp, ensure_ascii=True)

    return payload


def log_trade(trade: dict[str, Any], features: dict[str, Any] | None = None, result: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = _build_trade_payload(trade, features=features, result=result)
    try:
        db.upsert_trade_history_record(payload)
    except Exception:
        try:
            db.append_trade_history(payload)
        except Exception:
            pass
    return payload


def _dataset_from_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dataset: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        payload = dict(row)
        features = {
            "atr": _safe_float(payload.get("atr_value") or payload.get("atr"), 0.0) or 0.0,
            "spread_points": _safe_float(payload.get("spread_points"), 0.0) or 0.0,
            "signal_score": _safe_float(payload.get("signal_score"), 0.0) or 0.0,
            "margin_usage_pct": _safe_float(payload.get("margin_usage_pct"), 0.0) or 0.0,
            "balance": _safe_float(payload.get("balance"), 0.0) or 0.0,
            "equity": _safe_float(payload.get("equity"), 0.0) or 0.0,
            "session_time": _safe_float(payload.get("session_hour") or payload.get("session_time"), 0.0) or 0.0,
        }
        signal_context = _safe_json_loads(payload.get("signal_context") if payload.get("signal_context") is not None else payload.get("signal_context_json"))
        if isinstance(signal_context, dict):
            for key in ("atr", "spread_points", "signal_score", "margin_usage_pct", "balance", "equity", "session_time", "session_hour"):
                if key in signal_context:
                    value = _safe_float(signal_context.get(key), None)
                    if value is not None:
                        features[key] = value
        risk_mode = payload.get("risk_mode") or _normalize_risk_mode((signal_context or {}).get("risk_mode"))
        result = {
            "risk_mode": risk_mode,
            "status": payload.get("status") or "closed",
            "profit": _safe_float(payload.get("profit"), 0.0) or 0.0,
            "close_reason_family": _close_reason_family(payload.get("reason")),
            "target_crossed_before_close": bool(payload.get("target_first_crossed_at") or payload.get("target_hit") or payload.get("force_close_after_target_crossed")),
        }
        dataset.append({
            "timestamp": payload.get("entryTime") or payload.get("exitTime") or int(time.time()),
            "risk_mode": risk_mode,
            "features": features,
            "result": result,
            "trade_id": payload.get("trade_id"),
            "symbol": payload.get("symbol"),
            "broker_id": payload.get("broker_id"),
            "account_id": payload.get("account_id"),
        })
    return dataset


def get_dataset(limit: int = 5000, broker_id: int | None = None, account_id: int | None = None, symbol: str | None = None) -> list[dict[str, Any]]:
    rows = db.get_recent_closed_trades(limit=max(1, min(int(limit or 5000), 50000)), broker_id=broker_id, account_id=account_id, symbol=symbol)
    return _dataset_from_rows(rows)[: max(1, min(int(limit or 5000), 50000))]


def get_close_decision_dataset(limit: int = 5000, broker_id: int | None = None, account_id: int | None = None, symbol: str | None = None) -> list[dict[str, Any]]:
    rows = db.get_recent_closed_trades(limit=max(1, min(int(limit or 5000), 50000)), broker_id=broker_id, account_id=account_id, symbol=symbol)
    dataset: list[dict[str, Any]] = []
    for row in rows:
        reason = str(row.get("reason") or "")
        features = {
            "atr": _safe_float(row.get("atr_value"), 0.0) or 0.0,
            "spread_points": _safe_float(row.get("spread_points"), 0.0) or 0.0,
            "signal_score": _safe_float(row.get("signal_score"), 0.0) or 0.0,
            "margin_usage_pct": _safe_float(row.get("margin_usage_pct"), 0.0) or 0.0,
            "balance": _safe_float(row.get("balance"), 0.0) or 0.0,
            "equity": _safe_float(row.get("equity"), 0.0) or 0.0,
            "mfe_price_distance": _safe_float(row.get("mfe_price_distance"), 0.0) or 0.0,
            "mae_price_distance": _safe_float(row.get("mae_price_distance"), 0.0) or 0.0,
            "time_to_close_sec": _safe_float(row.get("time_to_close_sec"), 0.0) or 0.0,
            "target_first_crossed_at": _safe_float(row.get("target_first_crossed_at"), 0.0) or 0.0,
        }
        dataset.append({
            "trade_id": row.get("trade_id"),
            "features": features,
            "result": {
                "profit": _safe_float(row.get("profit"), 0.0) or 0.0,
                "close_reason_family": _close_reason_family(reason),
                "target_crossed_before_close": bool(row.get("target_first_crossed_at") or row.get("target_hit") or row.get("force_close_after_target_crossed")),
                "risk_mode": row.get("risk_mode") or "fixed_lot",
            },
        })
    return dataset[: max(1, min(int(limit or 5000), 50000))]


def train_risk_mode_model(dataset: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    global _MODEL

    rows = dataset if dataset is not None else get_dataset(limit=5000)
    if not rows:
        return {"trained": False, "reason": "empty_dataset", "rows": 0, "model_type": "heuristic"}

    counts: dict[str, int] = {}
    for row in rows:
        mode = _normalize_risk_mode((row.get("risk_mode") or (row.get("result") or {}).get("risk_mode")))
        counts[mode] = counts.get(mode, 0) + 1

    selected_mode = max(counts.items(), key=lambda item: item[1])[0] if counts else "fixed_lot"
    _MODEL = {"selected_mode": selected_mode, "counts": counts, "dataset_rows": len(rows)}
    _MODEL_META["trained_trade_count"] = len(rows)
    _MODEL_META["updated_at"] = int(time.time())
    _MODEL_META["model_type"] = "heuristic"
    return {
        "trained": True,
        "rows": len(rows),
        "selected_mode": selected_mode,
        "counts": counts,
        "model_type": "heuristic",
    }


def predict_risk_mode(features: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(features or {})
    atr = _safe_float(payload.get("atr") or payload.get("atr_value"), 0.0) or 0.0
    spread = _safe_float(payload.get("spread_points"), 0.0) or 0.0
    signal_score = _safe_float(payload.get("signal_score") or payload.get("score"), 0.0) or 0.0
    margin_usage = _safe_float(payload.get("margin_usage_pct"), 0.0) or 0.0
    session_time = _safe_float(payload.get("session_time") or payload.get("session_hour"), 0.0) or 0.0

    current_rows = get_dataset(limit=200)
    retrain = None
    if not _MODEL or len(current_rows) - int(_MODEL_META.get("trained_trade_count") or 0) >= 100:
        retrain = train_risk_mode_model(current_rows)

    if atr >= 12.0:
        selected = "atr_dynamic"
    elif margin_usage >= 35.0:
        selected = "balance_scaled"
    elif signal_score >= 0.70 and spread <= 60:
        selected = "risk_percent"
    else:
        selected = "fixed_lot"

    return {
        "risk_mode": selected,
        "confidence": min(0.99, max(0.35, 0.45 + (signal_score * 0.6) + (max(0.0, atr - 8.0) * 0.03))),
        "model_type": _MODEL_META.get("model_type") or "heuristic",
        "retrain": retrain,
        "session_time": session_time,
    }


def export_dataset_json(path: str | None = None, limit: int = 10000) -> str:
    rows = get_dataset(limit=limit)
    destination = str(path or "auto_trade_dataset.json")
    with open(destination, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=True, indent=2)
    return destination


def export_dataset_csv(path: str | None = None, limit: int = 10000) -> str:
    rows = get_dataset(limit=limit)
    destination = str(path or "auto_trade_dataset.csv")
    with open(destination, "w", encoding="utf-8", newline="") as fh:
        import csv
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "risk_mode", "profit", "features_json"])
        for row in rows:
            writer.writerow([
                row.get("timestamp"),
                row.get("risk_mode"),
                (row.get("result") or {}).get("profit"),
                json.dumps(row.get("features") or {}, ensure_ascii=True),
            ])
    return destination


__all__ = [
    "MODEL_TYPES",
    "_MODEL",
    "_MODEL_META",
    "log_trade",
    "get_dataset",
    "get_close_decision_dataset",
    "train_risk_mode_model",
    "predict_risk_mode",
    "export_dataset_json",
    "export_dataset_csv",
]
