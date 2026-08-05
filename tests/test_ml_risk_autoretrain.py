import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.db as db
import app.ml_risk as ml_risk


def _insert_closed_trades(start_index: int, count: int, account_id: int = 9001):
    for i in range(start_index, start_index + count):
        mode = "risk_percent" if i % 2 == 0 else "balance_scaled"
        ml_risk.log_trade(
            trade={
                "trade_id": f"auto-retrain-{i}",
                "status": "closed",
                "type": "BUY",
                "symbol": "XAUUSD",
                "lot": 0.1,
                "ticket": 10000 + i,
                "entry": 2300.0,
                "exit": 2305.0,
                "profit": 30.0 if i % 2 == 0 else -10.0,
                "entryTime": 1725000000 + i,
                "exitTime": 1725000300 + i,
                "broker_id": 1,
                "broker_name": "Default Broker",
                "account_id": account_id,
                "platform": "mt5",
                "execution_mode": "direct",
                "terminal_path": "C:/Terminal/terminal64.exe",
            },
            features={
                "atr": 8.0 + (i % 6),
                "spread_points": 35 + (i % 9),
                "signal_score": 0.58 + ((i % 8) * 0.03),
                "margin_usage_pct": 22 + (i % 15),
                "balance": 1000 + i,
                "equity": 1010 + i,
                "session_time": i % 24,
            },
            result={"risk_mode": mode, "status": "closed"},
        )


def test_auto_retrain_triggered_at_100_closed_trades_delta(tmp_path):
    db.DB_PATH = str(tmp_path / "test.db")
    db.init_db()

    # Reset in-memory model state for deterministic behavior per test.
    ml_risk._MODEL = None
    ml_risk._MODEL_META["trained_trade_count"] = 0
    ml_risk._MODEL_META["updated_at"] = 0
    ml_risk._MODEL_META["model_type"] = "none"

    _insert_closed_trades(0, 30)
    base_train = ml_risk.train_risk_mode_model(ml_risk.get_dataset(limit=200))
    assert base_train["trained"] is True

    previous_trained_count = int(ml_risk._MODEL_META.get("trained_trade_count") or 0)
    previous_updated_at = int(ml_risk._MODEL_META.get("updated_at") or 0)

    # Add exactly 100 new closed trades to hit auto-retrain threshold.
    _insert_closed_trades(30, 100)

    prediction = ml_risk.predict_risk_mode(
        {
            "atr": 12.0,
            "spread_points": 40,
            "signal_score": 0.71,
            "margin_usage_pct": 30,
            "balance": 1300,
            "equity": 1310,
            "session_time": 11,
        }
    )

    retrain_meta = prediction.get("retrain") or {}
    assert retrain_meta.get("trained") is True
    assert ml_risk._MODEL is not None
    assert int(ml_risk._MODEL_META.get("trained_trade_count") or 0) >= previous_trained_count + 100
    assert int(ml_risk._MODEL_META.get("updated_at") or 0) >= previous_updated_at
