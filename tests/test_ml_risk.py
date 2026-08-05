import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.db as db
import app.ml_risk as ml_risk


def test_ml_risk_log_trade_and_dataset(tmp_path):
    db.DB_PATH = str(tmp_path / "test.db")
    db.init_db()

    ml_risk.log_trade(
        trade={
            "trade_id": "ml-1",
            "status": "closed",
            "type": "BUY",
            "symbol": "XAUUSD",
            "lot": 0.1,
            "ticket": 101,
            "entry": 2300.0,
            "exit": 2310.0,
            "profit": 50.0,
            "entryTime": 1725000000,
            "exitTime": 1725000300,
            "broker_id": 1,
            "broker_name": "Default Broker",
            "account_id": 999001,
            "platform": "mt5",
            "execution_mode": "direct",
            "terminal_path": "C:/Terminal/terminal64.exe",
        },
        features={
            "atr": 12.5,
            "spread_points": 55,
            "signal_score": 0.72,
            "margin_usage_pct": 38.0,
            "balance": 1200.0,
            "equity": 1230.0,
            "session_time": 10,
        },
        result={"risk_mode": "risk_percent", "status": "closed", "profit": 50.0},
    )

    rows = ml_risk.get_dataset(limit=10)
    assert len(rows) == 1
    assert rows[0]["risk_mode"] == "risk_percent"
    assert rows[0]["features"]["atr"] == 12.5


def test_ml_risk_train_and_predict(tmp_path):
    db.DB_PATH = str(tmp_path / "test.db")
    db.init_db()

    for i in range(30):
        mode = "risk_percent" if i % 2 == 0 else "balance_scaled"
        profit = 40.0 if i % 2 == 0 else 20.0
        ml_risk.log_trade(
            trade={
                "trade_id": f"ml-train-{i}",
                "status": "closed",
                "type": "BUY",
                "symbol": "XAUUSD",
                "lot": 0.1,
                "ticket": 200 + i,
                "entry": 2300.0,
                "exit": 2305.0,
                "profit": profit,
                "entryTime": 1725000000 + i,
                "exitTime": 1725000400 + i,
                "broker_id": 1,
                "broker_name": "Default Broker",
                "account_id": 999002,
                "platform": "mt5",
                "execution_mode": "direct",
                "terminal_path": "C:/Terminal/terminal64.exe",
            },
            features={
                "atr": 10.0 + (i % 5),
                "spread_points": 40 + (i % 10),
                "signal_score": 0.60 + ((i % 5) * 0.03),
                "margin_usage_pct": 30 + (i % 10),
                "balance": 1000 + i,
                "equity": 1020 + i,
                "session_time": i % 24,
            },
            result={"risk_mode": mode, "status": "closed", "profit": profit},
        )

    ds = ml_risk.get_dataset(limit=100)
    train_result = ml_risk.train_risk_mode_model(ds)
    assert train_result.get("trained") is True

    prediction = ml_risk.predict_risk_mode(
        {
            "atr": 14.0,
            "spread_points": 45,
            "signal_score": 0.74,
            "margin_usage_pct": 35,
            "balance": 1500,
            "equity": 1510,
            "session_time": 11,
        }
    )
    assert prediction.get("risk_mode") in ("fixed_lot", "risk_percent", "balance_scaled", "atr_dynamic")
