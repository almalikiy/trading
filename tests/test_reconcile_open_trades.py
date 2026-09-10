import importlib.util
import sqlite3
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_open_trade_reconcile.py"
SPEC = importlib.util.spec_from_file_location("check_open_trade_reconcile", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_reconcile_marks_missing_db_open_trade_closed(tmp_path):
    db_path = tmp_path / "trading_data.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE trade_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT,
                status TEXT,
                type TEXT,
                symbol TEXT,
                lot REAL,
                ticket INTEGER,
                entry REAL,
                exit REAL,
                profit REAL,
                entryTime INTEGER,
                exitTime INTEGER,
                reason TEXT,
                tpValue REAL,
                slValue REAL,
                broker_id INTEGER,
                broker_name TEXT,
                account_id INTEGER,
                platform TEXT,
                execution_mode TEXT,
                terminal_path TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO trade_history (
                trade_id, status, type, symbol, lot, ticket, entry, exit, profit,
                entryTime, exitTime, reason, tpValue, slValue, broker_id, broker_name,
                account_id, platform, execution_mode, terminal_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "trade-1",
                "open",
                "BUY",
                "XAUUSD",
                0.01,
                21547729,
                4350.0,
                None,
                None,
                1700000000,
                None,
                "terminal_sync_open",
                None,
                None,
                1,
                "Default Broker",
                1,
                "mt5",
                "mouse",
                None,
            ),
        )
        conn.commit()

    result = MODULE.reconcile_open_db_trades(db_path, positions=[], apply=True)

    assert result["stale_or_closed_in_db"]
    assert result["status"] == "mismatch_detected"

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT status, reason, exit, profit FROM trade_history WHERE trade_id = ?",
            ("trade-1",),
        ).fetchone()
        assert row[0] == "closed"
        assert row[1] == "reconciled_closed_no_live_mt5"
        assert row[2] == 4350.0
        assert row[3] == 0.0
