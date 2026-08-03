import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.db as db


def test_init_db_adds_default_symbol_column(tmp_path):
    db.DB_PATH = str(tmp_path / "test.db")
    db.init_db()

    with sqlite3.connect(db.DB_PATH) as conn:
        account_columns = {row[1] for row in conn.execute("PRAGMA table_info(account_state)")}
        assert "trade_history_sync_days" in account_columns
        assert "trade_history_sync_all" in account_columns
        assert "auto_trade_symbol" in account_columns
        assert "auto_trade_interval_sec" in account_columns

        columns = {row[1] for row in conn.execute("PRAGMA table_info(brokers)")}
        assert "default_symbol" in columns

        trade_columns = {row[1] for row in conn.execute("PRAGMA table_info(trade_history)")}
        assert "account_id" in trade_columns

        error_columns = {row[1] for row in conn.execute("PRAGMA table_info(mt5_error_log)")}
        assert "account_id" in error_columns

        row = conn.execute(
            "SELECT default_symbol FROM brokers WHERE name = ?",
            ("Default Broker",),
        ).fetchone()
        assert row is not None
        assert row[0] == "XAUUSD"


def test_save_account_state_persists_trade_history_sync_settings(tmp_path):
    db.DB_PATH = str(tmp_path / "test.db")
    db.init_db()

    state = db.get_account_state()
    state["trade_history_sync_days"] = 365
    state["trade_history_sync_all"] = True
    db.save_account_state(state)

    updated = db.get_account_state()
    assert updated["trade_history_sync_days"] == 365
    assert updated["trade_history_sync_all"] is True


def test_save_account_state_persists_auto_trade_detail_settings(tmp_path):
    db.DB_PATH = str(tmp_path / "test.db")
    db.init_db()

    state = db.get_account_state()
    state["auto_trade_symbol"] = "EURUSD"
    state["auto_trade_interval_sec"] = 5
    db.save_account_state(state)

    updated = db.get_account_state()
    assert updated["auto_trade_symbol"] == "EURUSD"
    assert updated["auto_trade_interval_sec"] == 5


def test_upsert_trade_history_record_backfills_open_trade_ticket_and_account(tmp_path):
    db.DB_PATH = str(tmp_path / "test.db")
    db.init_db()

    db.create_trade_open_record(
        {
            "trade_id": "existing-open",
            "type": "BUY",
            "symbol": "XAUUSD",
            "lot": 0.1,
            "ticket": None,
            "entry": 2300.5,
            "entryTime": 1725000000,
            "reason": "open_v2",
            "broker_id": 1,
            "broker_name": "Default Broker",
            "platform": "mt5",
            "execution_mode": "direct",
            "terminal_path": "C:/Terminal/terminal64.exe",
        }
    )

    db.upsert_trade_history_record(
        {
            "trade_id": "terminal-sync:1:998877:445566",
            "status": "open",
            "type": "BUY",
            "symbol": "XAUUSD",
            "lot": 0.1,
            "ticket": 445566,
            "entry": 2300.55,
            "entryTime": 1725000030,
            "reason": "terminal_sync_open",
            "broker_id": 1,
            "broker_name": "Default Broker",
            "account_id": 998877,
            "platform": "mt5",
            "execution_mode": "direct",
            "terminal_path": "C:/Terminal/terminal64.exe",
        }
    )

    open_rows = db.list_open_trades()
    assert len(open_rows) == 1
    assert open_rows[0]["trade_id"] == "existing-open"
    assert open_rows[0]["ticket"] == 445566
    assert open_rows[0]["account_id"] == 998877
