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
        assert "auto_trade_risk_mode" in account_columns
        assert "auto_trade_risk_percent" in account_columns
        assert "auto_trade_min_free_margin_pct" in account_columns
        assert "auto_trade_max_margin_usage_pct" in account_columns
        assert "auto_trade_max_spread_points" in account_columns
        assert "auto_trade_min_signal_score" in account_columns
        assert "auto_trade_cooldown_sec" in account_columns
        assert "auto_trade_session_start_hour" in account_columns
        assert "auto_trade_session_end_hour" in account_columns
        assert "auto_trade_use_atr_tpsl" in account_columns
        assert "auto_trade_atr_period" in account_columns
        assert "auto_trade_atr_sl_mult" in account_columns
        assert "auto_trade_atr_tp_mult" in account_columns
        assert "auto_trade_trailing_enabled" in account_columns
        assert "auto_trade_trailing_activation_rr" in account_columns
        assert "auto_trade_trailing_atr_mult" in account_columns
        assert "auto_trade_confidence_model" in account_columns
        assert "auto_trade_confidence_threshold" in account_columns
        assert "auto_trade_tf_weight_m1" in account_columns
        assert "auto_trade_tf_weight_m5" in account_columns
        assert "auto_trade_tf_weight_m15" in account_columns
        assert "auto_trade_tf_weight_m30" in account_columns
        assert "auto_trade_partial_tp_enabled" in account_columns
        assert "auto_trade_partial_tp_rr1" in account_columns
        assert "auto_trade_partial_tp_close_pct1" in account_columns
        assert "auto_trade_partial_tp_rr2" in account_columns
        assert "auto_trade_partial_tp_close_pct2" in account_columns
        assert "auto_trade_break_even_enabled" in account_columns
        assert "auto_trade_break_even_rr" in account_columns
        assert "auto_trade_break_even_offset_atr_mult" in account_columns
        assert "auto_trade_trailing_mode" in account_columns
        assert "auto_trade_stateful_trail_buffer_atr_mult" in account_columns

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


def test_save_account_state_persists_advanced_auto_trade_strategy_settings(tmp_path):
    db.DB_PATH = str(tmp_path / "test.db")
    db.init_db()

    state = db.get_account_state()
    state["auto_trade_risk_mode"] = "risk_percent"
    state["auto_trade_risk_percent"] = 2.5
    state["auto_trade_use_account_balance"] = True
    state["auto_trade_use_available_margin"] = True
    state["auto_trade_min_free_margin_pct"] = 35
    state["auto_trade_max_margin_usage_pct"] = 60
    state["auto_trade_max_spread_points"] = 85
    state["auto_trade_min_signal_score"] = 0.62
    state["auto_trade_allow_sell"] = False
    state["auto_trade_cooldown_sec"] = 45
    state["auto_trade_session_start_hour"] = 7
    state["auto_trade_session_end_hour"] = 22
    state["auto_trade_use_atr_tpsl"] = True
    state["auto_trade_atr_period"] = 20
    state["auto_trade_atr_sl_mult"] = 1.8
    state["auto_trade_atr_tp_mult"] = 3.1
    state["auto_trade_trailing_enabled"] = True
    state["auto_trade_trailing_activation_rr"] = 1.2
    state["auto_trade_trailing_atr_mult"] = 0.9
    state["auto_trade_confidence_model"] = "weighted"
    state["auto_trade_confidence_threshold"] = 0.67
    state["auto_trade_tf_weight_m1"] = 0.4
    state["auto_trade_tf_weight_m5"] = 0.3
    state["auto_trade_tf_weight_m15"] = 0.2
    state["auto_trade_tf_weight_m30"] = 0.1
    state["auto_trade_partial_tp_enabled"] = True
    state["auto_trade_partial_tp_rr1"] = 1.1
    state["auto_trade_partial_tp_close_pct1"] = 45
    state["auto_trade_partial_tp_rr2"] = 2.2
    state["auto_trade_partial_tp_close_pct2"] = 30
    state["auto_trade_break_even_enabled"] = True
    state["auto_trade_break_even_rr"] = 1.3
    state["auto_trade_break_even_offset_atr_mult"] = 0.2
    state["auto_trade_trailing_mode"] = "stateful_hl"
    state["auto_trade_stateful_trail_buffer_atr_mult"] = 0.8
    db.save_account_state(state)

    updated = db.get_account_state()
    assert updated["auto_trade_risk_mode"] == "risk_percent"
    assert updated["auto_trade_risk_percent"] == 2.5
    assert updated["auto_trade_use_account_balance"] is True
    assert updated["auto_trade_use_available_margin"] is True
    assert updated["auto_trade_min_free_margin_pct"] == 35
    assert updated["auto_trade_max_margin_usage_pct"] == 60
    assert updated["auto_trade_max_spread_points"] == 85
    assert updated["auto_trade_min_signal_score"] == 0.62
    assert updated["auto_trade_allow_sell"] is False
    assert updated["auto_trade_cooldown_sec"] == 45
    assert updated["auto_trade_session_start_hour"] == 7
    assert updated["auto_trade_session_end_hour"] == 22
    assert updated["auto_trade_use_atr_tpsl"] is True
    assert updated["auto_trade_atr_period"] == 20
    assert updated["auto_trade_atr_sl_mult"] == 1.8
    assert updated["auto_trade_atr_tp_mult"] == 3.1
    assert updated["auto_trade_trailing_enabled"] is True
    assert updated["auto_trade_trailing_activation_rr"] == 1.2
    assert updated["auto_trade_trailing_atr_mult"] == 0.9
    assert updated["auto_trade_confidence_model"] == "weighted"
    assert updated["auto_trade_confidence_threshold"] == 0.67
    assert updated["auto_trade_tf_weight_m1"] == 0.4
    assert updated["auto_trade_tf_weight_m5"] == 0.3
    assert updated["auto_trade_tf_weight_m15"] == 0.2
    assert updated["auto_trade_tf_weight_m30"] == 0.1
    assert updated["auto_trade_partial_tp_enabled"] is True
    assert updated["auto_trade_partial_tp_rr1"] == 1.1
    assert updated["auto_trade_partial_tp_close_pct1"] == 45
    assert updated["auto_trade_partial_tp_rr2"] == 2.2
    assert updated["auto_trade_partial_tp_close_pct2"] == 30
    assert updated["auto_trade_break_even_enabled"] is True
    assert updated["auto_trade_break_even_rr"] == 1.3
    assert updated["auto_trade_break_even_offset_atr_mult"] == 0.2
    assert updated["auto_trade_trailing_mode"] == "stateful_hl"
    assert updated["auto_trade_stateful_trail_buffer_atr_mult"] == 0.8


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
