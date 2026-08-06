import csv
import json
import os
import threading
import time
from typing import Dict, List

from .db import get_db, log_mt5_error as db_log_mt5_error, upsert_trade_history_record

try:
    from sklearn.ensemble import RandomForestClassifier

    _SKLEARN_AVAILABLE = True
except Exception:
    RandomForestClassifier = None
    _SKLEARN_AVAILABLE = False


RISK_MODES = ["fixed_lot", "risk_percent", "balance_scaled", "atr_dynamic", "hedge"]
FEATURE_COLUMNS = [
    "atr",
    "spread_points",
    "signal_score",
    "margin_usage_pct",
    "balance",
    "equity",
    "session_time",
    "target_factor",
    "target_hit",
    "overshoot_before_close",
]

_MODEL_LOCK = threading.Lock()
_MODEL = None
_MODEL_META = {
    "trained_trade_count": 0,
    "updated_at": 0,
    "model_type": "none",
}


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return float(default)


def _safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return int(default)


def _session_hour_from_epoch(epoch_seconds):
    ts = _safe_int(epoch_seconds, 0)
    if ts <= 0:
        return 0
    return int(time.localtime(ts).tm_hour)


def _normalize_mode(value):
    mode = str(value or "").strip().lower()
    return mode if mode in RISK_MODES else "fixed_lot"


def _close_reason_family(reason):
    text = str(reason or "").strip().lower()
    if "tp" in text or "take_profit" in text:
        return "tp"
    if "sl" in text or "stop_loss" in text:
        return "sl"
    if "reversal" in text:
        return "reversal"
    if "partial" in text:
        return "partial"
    return "other"


def _feature_vector(features):
    return [
        _safe_float(features.get("atr") or features.get("ATR"), 0.0),
        _safe_float(features.get("spread_points"), 0.0),
        _safe_float(features.get("signal_score"), 0.0),
        _safe_float(features.get("margin_usage_pct"), 0.0),
        _safe_float(features.get("balance"), 0.0),
        _safe_float(features.get("equity"), 0.0),
        _safe_float(features.get("session_time"), 0.0),
        _safe_float(features.get("target_factor"), 1.0),
        _safe_float(features.get("target_hit"), 0.0),
        _safe_float(features.get("overshoot_before_close"), 0.0),
    ]


def log_trade(trade, features=None, result=None):
    payload = dict(trade or {})
    feature_map = dict(features or {})
    result_map = dict(result or {})

    payload["atr_value"] = feature_map.get("atr") if feature_map.get("atr") is not None else feature_map.get("ATR")
    payload["spread_points"] = feature_map.get("spread_points")
    payload["signal_score"] = feature_map.get("signal_score")
    payload["margin_usage_pct"] = feature_map.get("margin_usage_pct")
    payload["balance"] = feature_map.get("balance") if feature_map.get("balance") is not None else result_map.get("balance")
    payload["equity"] = feature_map.get("equity") if feature_map.get("equity") is not None else result_map.get("equity")
    payload["target_factor"] = feature_map.get("target_factor")
    payload["target_hit"] = feature_map.get("target_hit")
    payload["overshoot_before_close"] = feature_map.get("overshoot_before_close")

    session_time = feature_map.get("session_time")
    if session_time is None:
        session_time = _session_hour_from_epoch(payload.get("entryTime") or payload.get("exitTime"))
    payload["session_hour"] = _safe_int(session_time, 0)

    if result_map.get("risk_mode"):
        payload["risk_mode"] = _normalize_mode(result_map.get("risk_mode"))
    else:
        payload["risk_mode"] = _normalize_mode(payload.get("risk_mode"))

    if result_map.get("status"):
        payload["status"] = result_map.get("status")
    if result_map.get("profit") is not None:
        payload["profit"] = result_map.get("profit")

    return upsert_trade_history_record(payload)


def log_mt5_error(message, broker_id=None, account_id=None):
    db_log_mt5_error(message, broker_id=broker_id, account_id=account_id)


def get_dataset(limit: int = 2000):
    safe_limit = max(10, min(int(limit or 2000), 100000))
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT trade_id, symbol, risk_mode, profit, status, entryTime, exitTime,
                   atr_value, spread_points, signal_score, margin_usage_pct,
                     balance, equity, session_hour,
                     target_factor, target_hit, overshoot_before_close,
                                         force_close_after_target_crossed, mfe_price_distance,
                                         mae_price_distance, time_to_close_sec, target_first_crossed_at,
                                         time_to_target_cross_sec
            FROM trade_history
            WHERE risk_mode IS NOT NULL
              AND TRIM(risk_mode) != ''
            ORDER BY COALESCE(exitTime, entryTime, 0) DESC, id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    dataset = []
    for row in rows:
        features = {
            "atr": _safe_float(row["atr_value"], 0.0),
            "spread_points": _safe_float(row["spread_points"], 0.0),
            "signal_score": _safe_float(row["signal_score"], 0.0),
            "margin_usage_pct": _safe_float(row["margin_usage_pct"], 0.0),
            "balance": _safe_float(row["balance"], 0.0),
            "equity": _safe_float(row["equity"], 0.0),
            "session_time": _safe_float(row["session_hour"], _session_hour_from_epoch(row["entryTime"])),
            "target_factor": _safe_float(row["target_factor"], 1.0),
            "target_hit": _safe_float(row["target_hit"], 0.0),
            "overshoot_before_close": _safe_float(row["overshoot_before_close"], 0.0),
        }
        force_cross = _safe_int(row["force_close_after_target_crossed"], 0)
        target_hit = _safe_int(row["target_hit"], 0)
        target_quality = 1.0
        if force_cross == 1:
            target_quality = 0.0
        elif target_hit == 1:
            target_quality = 1.0
        elif row["target_hit"] is not None:
            target_quality = 0.25

        adjusted_profit = _safe_float(row["profit"], 0.0)
        overshoot = _safe_float(row["overshoot_before_close"], 0.0)
        if force_cross == 1:
            adjusted_profit -= abs(overshoot) * 0.5

        result = {
            "profit": adjusted_profit,
            "status": row["status"],
            "win": adjusted_profit > 0,
            "target_quality": target_quality,
            "target_hit": bool(target_hit),
            "force_close_after_target_crossed": bool(force_cross),
            "mfe_price_distance": _safe_float(row["mfe_price_distance"], 0.0),
            "mae_price_distance": _safe_float(row["mae_price_distance"], 0.0),
            "time_to_close_sec": _safe_int(row["time_to_close_sec"], 0),
            "target_first_crossed_at": _safe_int(row["target_first_crossed_at"], 0),
            "time_to_target_cross_sec": _safe_int(row["time_to_target_cross_sec"], 0),
        }
        dataset.append(
            {
                "trade_id": row["trade_id"],
                "symbol": row["symbol"],
                "risk_mode": _normalize_mode(row["risk_mode"]),
                "features": features,
                "result": result,
            }
        )
    return dataset


def get_close_decision_dataset(limit: int = 2000, broker_id=None, account_id=None):
    safe_limit = max(10, min(int(limit or 2000), 100000))
    with get_db() as conn:
        clauses = ["status = 'closed'"]
        params = []
        if broker_id is not None:
            clauses.append("COALESCE(broker_id, -1) = ?")
            params.append(int(broker_id))
        if account_id is not None:
            clauses.append("COALESCE(account_id, -1) = ?")
            params.append(int(account_id))
        rows = conn.execute(
            f"""
            SELECT trade_id, symbol, risk_mode, profit, status, entryTime, exitTime, reason,
                   broker_id, account_id,
                   atr_value, spread_points, signal_score, margin_usage_pct,
                   balance, equity, session_hour, target_price, target_factor,
                   overshoot_before_close, force_close_after_target_crossed,
                   mfe_price_distance, mae_price_distance, time_to_close_sec,
                   target_first_crossed_at, time_to_target_cross_sec
            FROM trade_history
            WHERE {' AND '.join(clauses)}
            ORDER BY COALESCE(exitTime, entryTime, 0) DESC, id DESC
            LIMIT ?
            """,
            (*params, safe_limit),
        ).fetchall()

    dataset = []
    for row in rows:
        target_crossed_before_close = _safe_int(row["target_first_crossed_at"], 0) > 0
        features = {
            "atr": _safe_float(row["atr_value"], 0.0),
            "spread_points": _safe_float(row["spread_points"], 0.0),
            "signal_score": _safe_float(row["signal_score"], 0.0),
            "margin_usage_pct": _safe_float(row["margin_usage_pct"], 0.0),
            "balance": _safe_float(row["balance"], 0.0),
            "equity": _safe_float(row["equity"], 0.0),
            "session_time": _safe_float(row["session_hour"], _session_hour_from_epoch(row["entryTime"])),
            "target_factor": _safe_float(row["target_factor"], 1.0),
            "target_price": _safe_float(row["target_price"], 0.0),
            "overshoot_before_close": _safe_float(row["overshoot_before_close"], 0.0),
            "mfe_price_distance": _safe_float(row["mfe_price_distance"], 0.0),
            "mae_price_distance": _safe_float(row["mae_price_distance"], 0.0),
            "time_to_close_sec": _safe_int(row["time_to_close_sec"], 0),
            "time_to_target_cross_sec": _safe_int(row["time_to_target_cross_sec"], 0),
            "target_crossed_before_close": 1 if target_crossed_before_close else 0,
        }
        result = {
            "profit": _safe_float(row["profit"], 0.0),
            "status": row["status"],
            "win": _safe_float(row["profit"], 0.0) > 0,
            "close_reason": str(row["reason"] or ""),
            "close_reason_family": _close_reason_family(row["reason"]),
            "force_close_after_target_crossed": bool(_safe_int(row["force_close_after_target_crossed"], 0)),
            "target_crossed_before_close": target_crossed_before_close,
        }
        dataset.append(
            {
                "trade_id": row["trade_id"],
                "symbol": row["symbol"],
                "broker_id": row["broker_id"],
                "account_id": row["account_id"],
                "risk_mode": _normalize_mode(row["risk_mode"]),
                "features": features,
                "result": result,
            }
        )
    return dataset


def export_dataset_json(file_path, limit: int = 10000):
    data = get_dataset(limit=limit)
    folder = os.path.dirname(os.path.abspath(file_path))
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=True)
    return {"path": file_path, "rows": len(data), "format": "json"}


def export_dataset_csv(file_path, limit: int = 10000):
    data = get_dataset(limit=limit)
    folder = os.path.dirname(os.path.abspath(file_path))
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

    with open(file_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "trade_id", "symbol", "risk_mode", *FEATURE_COLUMNS,
            "profit", "status", "win", "target_quality",
            "target_hit", "force_close_after_target_crossed",
            "mfe_price_distance", "mae_price_distance",
            "time_to_close_sec", "target_first_crossed_at", "time_to_target_cross_sec",
        ])
        for row in data:
            features = row["features"]
            result = row["result"]
            writer.writerow(
                [
                    row.get("trade_id"),
                    row.get("symbol"),
                    row.get("risk_mode"),
                    features.get("atr"),
                    features.get("spread_points"),
                    features.get("signal_score"),
                    features.get("margin_usage_pct"),
                    features.get("balance"),
                    features.get("equity"),
                    features.get("session_time"),
                    features.get("target_factor"),
                    features.get("target_hit"),
                    features.get("overshoot_before_close"),
                    result.get("profit"),
                    result.get("status"),
                    int(bool(result.get("win"))),
                    result.get("target_quality"),
                    int(bool(result.get("target_hit"))),
                    int(bool(result.get("force_close_after_target_crossed"))),
                    result.get("mfe_price_distance"),
                    result.get("mae_price_distance"),
                    result.get("time_to_close_sec"),
                    result.get("target_first_crossed_at"),
                    result.get("time_to_target_cross_sec"),
                ]
            )

    return {"path": file_path, "rows": len(data), "format": "csv"}


def _closed_trade_count():
    with get_db() as conn:
        row = conn.execute("SELECT COUNT(*) AS total FROM trade_history WHERE status = 'closed'").fetchone()
    return _safe_int((row or {}).get("total") if isinstance(row, dict) else (row["total"] if row else 0), 0)


def train_risk_mode_model(dataset):
    filtered = [
        row
        for row in (dataset or [])
        if _normalize_mode(row.get("risk_mode")) in RISK_MODES
    ]
    if len(filtered) < 20:
        return {"trained": False, "reason": "not_enough_data", "rows": len(filtered)}

    winners = [row for row in filtered if bool((row.get("result") or {}).get("win"))]
    train_rows = winners if len(winners) >= 20 else filtered

    x_data = [_feature_vector(row.get("features") or {}) for row in train_rows]
    y_data = [_normalize_mode(row.get("risk_mode")) for row in train_rows]

    model_obj = None
    model_type = "majority"
    meta = {}

    if _SKLEARN_AVAILABLE and len(set(y_data)) >= 2:
        try:
            model_obj = RandomForestClassifier(
                n_estimators=160,
                random_state=42,
                min_samples_leaf=3,
                class_weight="balanced",
            )
            model_obj.fit(x_data, y_data)
            model_type = "random_forest"
            meta["classes"] = list(model_obj.classes_)
        except Exception as exc:
            db_log_mt5_error(f"ML train fallback to majority: {exc}")
            model_obj = None

    if model_obj is None:
        counts = {}
        for mode in y_data:
            counts[mode] = counts.get(mode, 0) + 1
        majority_mode = sorted(counts.items(), key=lambda item: item[1], reverse=True)[0][0]
        model_obj = {"majority_mode": majority_mode, "counts": counts}
        model_type = "majority"

    with _MODEL_LOCK:
        _MODEL_META["trained_trade_count"] = _closed_trade_count()
        _MODEL_META["updated_at"] = int(time.time())
        _MODEL_META["model_type"] = model_type
        _MODEL_META["rows"] = len(train_rows)
        _MODEL_META.update(meta)
        global _MODEL
        _MODEL = model_obj

    return {
        "trained": True,
        "model_type": model_type,
        "rows": len(train_rows),
        "trained_trade_count": _MODEL_META["trained_trade_count"],
        "updated_at": _MODEL_META["updated_at"],
    }


def _auto_retrain_if_needed(force=False):
    with _MODEL_LOCK:
        trained_count = _safe_int(_MODEL_META.get("trained_trade_count"), 0)
        model_ready = _MODEL is not None

    current_count = _closed_trade_count()
    if force or (not model_ready) or (current_count - trained_count >= 100):
        dataset = get_dataset(limit=5000)
        return train_risk_mode_model(dataset)
    return {"trained": False, "reason": "no_retrain_needed", "trained_trade_count": trained_count, "current_trade_count": current_count}


def predict_risk_mode(features):
    retrain_meta = _auto_retrain_if_needed(force=False)
    vector = _feature_vector(features or {})

    with _MODEL_LOCK:
        model_obj = _MODEL
        meta = dict(_MODEL_META)

    if model_obj is None:
        return {
            "risk_mode": "fixed_lot",
            "confidence": 0.0,
            "model_type": "none",
            "retrain": retrain_meta,
        }

    if isinstance(model_obj, dict):
        return {
            "risk_mode": _normalize_mode(model_obj.get("majority_mode")),
            "confidence": 0.5,
            "model_type": "majority",
            "retrain": retrain_meta,
            "meta": meta,
        }

    try:
        mode = _normalize_mode(model_obj.predict([vector])[0])
        confidence = 0.6
        if hasattr(model_obj, "predict_proba"):
            proba = model_obj.predict_proba([vector])[0]
            confidence = float(max(proba)) if len(proba) > 0 else 0.6
        return {
            "risk_mode": mode,
            "confidence": confidence,
            "model_type": "random_forest",
            "retrain": retrain_meta,
            "meta": meta,
        }
    except Exception as exc:
        db_log_mt5_error(f"ML predict fallback fixed_lot: {exc}")
        return {
            "risk_mode": "fixed_lot",
            "confidence": 0.0,
            "model_type": "predict_error",
            "retrain": retrain_meta,
            "meta": meta,
        }
