import json
import os
import sqlite3
import time
from contextlib import contextmanager

DB_PATH = "trading_data.db"

AUTO_TRADE_PROFILE_KEYS = [
    "auto_trade_symbol",
    "auto_trade_interval_sec",
    "auto_analytic_tpsl",
    "tp_value",
    "sl_value",
    "lot",
    "max_open_trades",
    "auto_trade_risk_mode",
    "auto_trade_risk_percent",
    "auto_trade_use_account_balance",
    "auto_trade_use_available_margin",
    "auto_trade_min_free_margin_pct",
    "auto_trade_max_margin_usage_pct",
    "auto_trade_max_spread_points",
    "auto_trade_min_signal_score",
    "auto_trade_allow_sell",
    "auto_trade_cooldown_sec",
    "auto_trade_session_start_hour",
    "auto_trade_session_end_hour",
    "auto_trade_use_atr_tpsl",
    "auto_trade_atr_period",
    "auto_trade_atr_sl_mult",
    "auto_trade_atr_tp_mult",
    "auto_trade_trailing_enabled",
    "auto_trade_trailing_activation_rr",
    "auto_trade_trailing_atr_mult",
    "auto_trade_confidence_model",
    "auto_trade_confidence_threshold",
    "auto_trade_tf_weight_m1",
    "auto_trade_tf_weight_m5",
    "auto_trade_tf_weight_m15",
    "auto_trade_tf_weight_m30",
    "auto_trade_partial_tp_enabled",
    "auto_trade_partial_tp_rr1",
    "auto_trade_partial_tp_close_pct1",
    "auto_trade_partial_tp_rr2",
    "auto_trade_partial_tp_close_pct2",
    "auto_trade_break_even_enabled",
    "auto_trade_break_even_rr",
    "auto_trade_break_even_offset_atr_mult",
    "auto_trade_trailing_mode",
    "auto_trade_stateful_trail_buffer_atr_mult",
]


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.commit()
        conn.close()


def _table_columns(conn, table_name):
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {r[1] for r in rows}


def _add_column_if_missing(conn, table_name, column_name, sql_type):
    cols = _table_columns(conn, table_name)
    if column_name not in cols:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {sql_type}")


def init_db():
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS account_state (
                id INTEGER PRIMARY KEY,
                balance REAL DEFAULT 1000,
                initial_balance REAL DEFAULT 1000,
                enable_real_trade INTEGER DEFAULT 0,
                auto_trade_enabled INTEGER DEFAULT 0,
                keep_terminal_alive INTEGER DEFAULT 1,
                data_feed_broker_id INTEGER,
                auto_analytic_tpsl INTEGER DEFAULT 0,
                tp_value REAL DEFAULT 0.5,
                sl_value REAL,
                lot REAL DEFAULT 0.01,
                max_open_trades INTEGER DEFAULT 1,
                auto_trade_symbol TEXT DEFAULT 'XAUUSD',
                auto_trade_interval_sec INTEGER DEFAULT 2,
                trade_history_sync_days INTEGER DEFAULT 90,
                trade_history_sync_all INTEGER DEFAULT 0,
                auto_trade_risk_mode TEXT DEFAULT 'fixed_lot',
                auto_trade_risk_percent REAL DEFAULT 1.0,
                auto_trade_use_account_balance INTEGER DEFAULT 1,
                auto_trade_use_available_margin INTEGER DEFAULT 1,
                auto_trade_min_free_margin_pct REAL DEFAULT 30,
                auto_trade_max_margin_usage_pct REAL DEFAULT 70,
                auto_trade_max_spread_points INTEGER DEFAULT 120,
                auto_trade_min_signal_score REAL DEFAULT 0.55,
                auto_trade_allow_sell INTEGER DEFAULT 1,
                auto_trade_cooldown_sec INTEGER DEFAULT 30,
                auto_trade_session_start_hour INTEGER DEFAULT 0,
                auto_trade_session_end_hour INTEGER DEFAULT 24,
                auto_trade_use_atr_tpsl INTEGER DEFAULT 1,
                auto_trade_atr_period INTEGER DEFAULT 14,
                auto_trade_atr_sl_mult REAL DEFAULT 1.5,
                auto_trade_atr_tp_mult REAL DEFAULT 2.5,
                auto_trade_trailing_enabled INTEGER DEFAULT 1,
                auto_trade_trailing_activation_rr REAL DEFAULT 1.0,
                auto_trade_trailing_atr_mult REAL DEFAULT 1.0,
                auto_trade_confidence_model TEXT DEFAULT 'weighted',
                auto_trade_confidence_threshold REAL DEFAULT 0.6,
                auto_trade_tf_weight_m1 REAL DEFAULT 0.35,
                auto_trade_tf_weight_m5 REAL DEFAULT 0.30,
                auto_trade_tf_weight_m15 REAL DEFAULT 0.20,
                auto_trade_tf_weight_m30 REAL DEFAULT 0.15,
                auto_trade_partial_tp_enabled INTEGER DEFAULT 1,
                auto_trade_partial_tp_rr1 REAL DEFAULT 1.0,
                auto_trade_partial_tp_close_pct1 REAL DEFAULT 40.0,
                auto_trade_partial_tp_rr2 REAL DEFAULT 2.0,
                auto_trade_partial_tp_close_pct2 REAL DEFAULT 35.0,
                auto_trade_break_even_enabled INTEGER DEFAULT 1,
                auto_trade_break_even_rr REAL DEFAULT 1.0,
                auto_trade_break_even_offset_atr_mult REAL DEFAULT 0.1,
                auto_trade_trailing_mode TEXT DEFAULT 'stateful_hl',
                auto_trade_stateful_trail_buffer_atr_mult REAL DEFAULT 0.5
            )
            """
        )
        _add_column_if_missing(conn, "account_state", "auto_trade_enabled", "INTEGER DEFAULT 0")
        _add_column_if_missing(conn, "account_state", "keep_terminal_alive", "INTEGER DEFAULT 1")
        _add_column_if_missing(conn, "account_state", "data_feed_broker_id", "INTEGER")
        _add_column_if_missing(conn, "account_state", "auto_trade_symbol", "TEXT DEFAULT 'XAUUSD'")
        _add_column_if_missing(conn, "account_state", "auto_trade_interval_sec", "INTEGER DEFAULT 2")
        _add_column_if_missing(conn, "account_state", "trade_history_sync_days", "INTEGER DEFAULT 90")
        _add_column_if_missing(conn, "account_state", "trade_history_sync_all", "INTEGER DEFAULT 0")
        _add_column_if_missing(conn, "account_state", "auto_trade_risk_mode", "TEXT DEFAULT 'fixed_lot'")
        _add_column_if_missing(conn, "account_state", "auto_trade_risk_percent", "REAL DEFAULT 1.0")
        _add_column_if_missing(conn, "account_state", "auto_trade_use_account_balance", "INTEGER DEFAULT 1")
        _add_column_if_missing(conn, "account_state", "auto_trade_use_available_margin", "INTEGER DEFAULT 1")
        _add_column_if_missing(conn, "account_state", "auto_trade_min_free_margin_pct", "REAL DEFAULT 30")
        _add_column_if_missing(conn, "account_state", "auto_trade_max_margin_usage_pct", "REAL DEFAULT 70")
        _add_column_if_missing(conn, "account_state", "auto_trade_max_spread_points", "INTEGER DEFAULT 120")
        _add_column_if_missing(conn, "account_state", "auto_trade_min_signal_score", "REAL DEFAULT 0.55")
        _add_column_if_missing(conn, "account_state", "auto_trade_allow_sell", "INTEGER DEFAULT 1")
        _add_column_if_missing(conn, "account_state", "auto_trade_cooldown_sec", "INTEGER DEFAULT 30")
        _add_column_if_missing(conn, "account_state", "auto_trade_session_start_hour", "INTEGER DEFAULT 0")
        _add_column_if_missing(conn, "account_state", "auto_trade_session_end_hour", "INTEGER DEFAULT 24")
        _add_column_if_missing(conn, "account_state", "auto_trade_use_atr_tpsl", "INTEGER DEFAULT 1")
        _add_column_if_missing(conn, "account_state", "auto_trade_atr_period", "INTEGER DEFAULT 14")
        _add_column_if_missing(conn, "account_state", "auto_trade_atr_sl_mult", "REAL DEFAULT 1.5")
        _add_column_if_missing(conn, "account_state", "auto_trade_atr_tp_mult", "REAL DEFAULT 2.5")
        _add_column_if_missing(conn, "account_state", "auto_trade_trailing_enabled", "INTEGER DEFAULT 1")
        _add_column_if_missing(conn, "account_state", "auto_trade_trailing_activation_rr", "REAL DEFAULT 1.0")
        _add_column_if_missing(conn, "account_state", "auto_trade_trailing_atr_mult", "REAL DEFAULT 1.0")
        _add_column_if_missing(conn, "account_state", "auto_trade_confidence_model", "TEXT DEFAULT 'weighted'")
        _add_column_if_missing(conn, "account_state", "auto_trade_confidence_threshold", "REAL DEFAULT 0.6")
        _add_column_if_missing(conn, "account_state", "auto_trade_tf_weight_m1", "REAL DEFAULT 0.35")
        _add_column_if_missing(conn, "account_state", "auto_trade_tf_weight_m5", "REAL DEFAULT 0.30")
        _add_column_if_missing(conn, "account_state", "auto_trade_tf_weight_m15", "REAL DEFAULT 0.20")
        _add_column_if_missing(conn, "account_state", "auto_trade_tf_weight_m30", "REAL DEFAULT 0.15")
        _add_column_if_missing(conn, "account_state", "auto_trade_partial_tp_enabled", "INTEGER DEFAULT 1")
        _add_column_if_missing(conn, "account_state", "auto_trade_partial_tp_rr1", "REAL DEFAULT 1.0")
        _add_column_if_missing(conn, "account_state", "auto_trade_partial_tp_close_pct1", "REAL DEFAULT 40.0")
        _add_column_if_missing(conn, "account_state", "auto_trade_partial_tp_rr2", "REAL DEFAULT 2.0")
        _add_column_if_missing(conn, "account_state", "auto_trade_partial_tp_close_pct2", "REAL DEFAULT 35.0")
        _add_column_if_missing(conn, "account_state", "auto_trade_break_even_enabled", "INTEGER DEFAULT 1")
        _add_column_if_missing(conn, "account_state", "auto_trade_break_even_rr", "REAL DEFAULT 1.0")
        _add_column_if_missing(conn, "account_state", "auto_trade_break_even_offset_atr_mult", "REAL DEFAULT 0.1")
        _add_column_if_missing(conn, "account_state", "auto_trade_trailing_mode", "TEXT DEFAULT 'stateful_hl'")
        _add_column_if_missing(conn, "account_state", "auto_trade_stateful_trail_buffer_atr_mult", "REAL DEFAULT 0.5")
        conn.execute(
            """
            INSERT INTO account_state (
                id, balance, initial_balance, enable_real_trade, auto_trade_enabled,
                keep_terminal_alive, data_feed_broker_id,
                auto_analytic_tpsl, tp_value, sl_value, lot, max_open_trades,
                auto_trade_symbol, auto_trade_interval_sec,
                trade_history_sync_days, trade_history_sync_all,
                auto_trade_risk_mode, auto_trade_risk_percent,
                auto_trade_use_account_balance, auto_trade_use_available_margin,
                auto_trade_min_free_margin_pct, auto_trade_max_margin_usage_pct,
                auto_trade_max_spread_points, auto_trade_min_signal_score,
                auto_trade_allow_sell, auto_trade_cooldown_sec,
                auto_trade_session_start_hour, auto_trade_session_end_hour,
                auto_trade_use_atr_tpsl, auto_trade_atr_period,
                auto_trade_atr_sl_mult, auto_trade_atr_tp_mult,
                auto_trade_trailing_enabled, auto_trade_trailing_activation_rr,
                auto_trade_trailing_atr_mult, auto_trade_confidence_model,
                auto_trade_confidence_threshold,
                auto_trade_tf_weight_m1, auto_trade_tf_weight_m5,
                auto_trade_tf_weight_m15, auto_trade_tf_weight_m30,
                auto_trade_partial_tp_enabled,
                auto_trade_partial_tp_rr1, auto_trade_partial_tp_close_pct1,
                auto_trade_partial_tp_rr2, auto_trade_partial_tp_close_pct2,
                auto_trade_break_even_enabled,
                auto_trade_break_even_rr, auto_trade_break_even_offset_atr_mult,
                auto_trade_trailing_mode, auto_trade_stateful_trail_buffer_atr_mult
            )
            VALUES (1, 1000, 1000, 0, 0, 1, NULL, 0, 0.5, NULL, 0.01, 1, 'XAUUSD', 2, 90, 0, 'fixed_lot', 1.0, 1, 1, 30, 70, 120, 0.55, 1, 30, 0, 24, 1, 14, 1.5, 2.5, 1, 1.0, 1.0, 'weighted', 0.6, 0.35, 0.30, 0.20, 0.15, 1, 1.0, 40.0, 2.0, 35.0, 1, 1.0, 0.1, 'stateful_hl', 0.5)
            ON CONFLICT(id) DO NOTHING
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trade_history (
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
        _add_column_if_missing(conn, "trade_history", "broker_id", "INTEGER")
        _add_column_if_missing(conn, "trade_history", "broker_name", "TEXT")
        _add_column_if_missing(conn, "trade_history", "account_id", "INTEGER")
        _add_column_if_missing(conn, "trade_history", "platform", "TEXT")
        _add_column_if_missing(conn, "trade_history", "execution_mode", "TEXT")
        _add_column_if_missing(conn, "trade_history", "terminal_path", "TEXT")
        _add_column_if_missing(conn, "trade_history", "trade_id", "TEXT")
        _add_column_if_missing(conn, "trade_history", "status", "TEXT")
        _add_column_if_missing(conn, "trade_history", "symbol", "TEXT")
        _add_column_if_missing(conn, "trade_history", "lot", "REAL")
        _add_column_if_missing(conn, "trade_history", "ticket", "INTEGER")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mt5_error_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER,
                message TEXT,
                broker_id INTEGER,
                broker_name TEXT,
                account_id INTEGER
            )
            """
        )
        _add_column_if_missing(conn, "mt5_error_log", "broker_id", "INTEGER")
        _add_column_if_missing(conn, "mt5_error_log", "broker_name", "TEXT")
        _add_column_if_missing(conn, "mt5_error_log", "account_id", "INTEGER")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS account_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT,
                amount REAL,
                note TEXT,
                timestamp INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS auto_trade_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                broker_id INTEGER NOT NULL,
                account_id INTEGER NOT NULL,
                profile_json TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                UNIQUE (broker_id, account_id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS brokers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                platform TEXT NOT NULL DEFAULT 'mt5',
                terminal_path TEXT,
                execution_mode TEXT NOT NULL DEFAULT 'mouse',
                window_hint TEXT,
                default_symbol TEXT NOT NULL DEFAULT 'XAUUSD',
                is_default INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        _add_column_if_missing(conn, "brokers", "default_symbol", "TEXT NOT NULL DEFAULT 'XAUUSD'")

        now = int(time.time())
        conn.execute(
            """
            INSERT INTO brokers (
                name, platform, terminal_path, execution_mode,
                window_hint, default_symbol, is_default, is_active, created_at, updated_at
            )
            VALUES (?, 'mt5', NULL, 'mouse', 'FinexBisnisSolusi', 'XAUUSD', 1, 1, ?, ?)
            ON CONFLICT(name) DO NOTHING
            """,
            ("Default Broker", now, now),
        )
        conn.execute("UPDATE brokers SET default_symbol = COALESCE(default_symbol, 'XAUUSD') WHERE default_symbol IS NULL OR default_symbol = ''")

        cur = conn.execute("SELECT COUNT(*) AS total FROM brokers WHERE is_default = 1")
        if cur.fetchone()["total"] == 0:
            first = conn.execute("SELECT id FROM brokers ORDER BY id ASC LIMIT 1").fetchone()
            if first:
                conn.execute("UPDATE brokers SET is_default = 1 WHERE id = ?", (first["id"],))

    migrate_legacy_json_to_db()


def migrate_legacy_json_to_db():
    project_root = os.path.dirname(os.path.dirname(__file__))
    legacy_account = os.path.join(project_root, "account_state.json")
    legacy_trade = os.path.join(project_root, "trade_history.json")
    legacy_error = os.path.join(os.path.dirname(__file__), "mt5_error_log.json")

    should_migrate_account = False
    should_migrate_trade = False
    should_migrate_error = False

    with get_db() as conn:
        row = conn.execute("SELECT COUNT(*) AS total FROM trade_history").fetchone()
        should_migrate_trade = (row["total"] == 0)
        row = conn.execute("SELECT COUNT(*) AS total FROM mt5_error_log").fetchone()
        should_migrate_error = (row["total"] == 0)
        row = conn.execute("SELECT balance, initial_balance FROM account_state WHERE id = 1").fetchone()
        if row:
            should_migrate_account = (float(row["balance"] or 0) == 1000.0 and float(row["initial_balance"] or 0) == 1000.0)

    if should_migrate_account and os.path.exists(legacy_account):
        try:
            with open(legacy_account, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                state = get_account_state()
                state.update({
                    "balance": data.get("balance", state.get("balance", 1000)),
                    "initial_balance": data.get("initial_balance", state.get("initial_balance", 1000)),
                    "enable_real_trade": data.get("enable_real_trade", state.get("enable_real_trade", False)),
                    "auto_analytic_tpsl": data.get("auto_analytic_tpsl", state.get("auto_analytic_tpsl", False)),
                    "tp_value": data.get("tp_value", state.get("tp_value", 0.5)),
                    "sl_value": data.get("sl_value", state.get("sl_value", None)),
                    "lot": data.get("lot", state.get("lot", 0.01)),
                    "max_open_trades": data.get("max_open_trades", state.get("max_open_trades", 1)),
                })
                save_account_state(state)
        except Exception:
            pass

    if should_migrate_trade and os.path.exists(legacy_trade):
        try:
            with open(legacy_trade, "r", encoding="utf-8") as f:
                items = json.load(f)
            if isinstance(items, list):
                existing = get_trade_history()
                existing_keys = {
                    (i.get("type"), i.get("entryTime"), i.get("exitTime"), i.get("entry"), i.get("exit"))
                    for i in existing
                }
                for item in items:
                    key = (
                        item.get("type"),
                        item.get("entryTime"),
                        item.get("exitTime"),
                        item.get("entry"),
                        item.get("exit"),
                    )
                    if key in existing_keys:
                        continue
                    append_trade_history(item)
        except Exception:
            pass

    if should_migrate_error and os.path.exists(legacy_error):
        try:
            with open(legacy_error, "r", encoding="utf-8") as f:
                logs = json.load(f)
            if isinstance(logs, list):
                known = {(i.get("timestamp"), i.get("message")) for i in get_mt5_error_log()}
                for row in logs:
                    key = (row.get("timestamp"), row.get("message"))
                    if key in known:
                        continue
                    log_mt5_error(row.get("message", ""), timestamp=row.get("timestamp"))
        except Exception:
            pass


def get_account_state():
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT balance, initial_balance, enable_real_trade, auto_analytic_tpsl,
                     auto_trade_enabled, keep_terminal_alive, data_feed_broker_id,
                     tp_value, sl_value, lot, max_open_trades,
                     auto_trade_symbol, auto_trade_interval_sec,
                     trade_history_sync_days, trade_history_sync_all,
                     auto_trade_risk_mode, auto_trade_risk_percent,
                     auto_trade_use_account_balance, auto_trade_use_available_margin,
                     auto_trade_min_free_margin_pct, auto_trade_max_margin_usage_pct,
                     auto_trade_max_spread_points, auto_trade_min_signal_score,
                     auto_trade_allow_sell, auto_trade_cooldown_sec,
                     auto_trade_session_start_hour, auto_trade_session_end_hour,
                     auto_trade_use_atr_tpsl, auto_trade_atr_period,
                     auto_trade_atr_sl_mult, auto_trade_atr_tp_mult,
                     auto_trade_trailing_enabled, auto_trade_trailing_activation_rr,
                     auto_trade_trailing_atr_mult, auto_trade_confidence_model,
                     auto_trade_confidence_threshold,
                     auto_trade_tf_weight_m1, auto_trade_tf_weight_m5,
                     auto_trade_tf_weight_m15, auto_trade_tf_weight_m30,
                     auto_trade_partial_tp_enabled,
                     auto_trade_partial_tp_rr1, auto_trade_partial_tp_close_pct1,
                     auto_trade_partial_tp_rr2, auto_trade_partial_tp_close_pct2,
                     auto_trade_break_even_enabled,
                     auto_trade_break_even_rr, auto_trade_break_even_offset_atr_mult,
                     auto_trade_trailing_mode, auto_trade_stateful_trail_buffer_atr_mult
            FROM account_state
            WHERE id = 1
            """
        ).fetchone()
        if not row:
            return {
                "balance": 1000,
                "initial_balance": 1000,
                "enable_real_trade": False,
                "auto_trade_enabled": False,
                "keep_terminal_alive": True,
                "data_feed_broker_id": None,
                "auto_analytic_tpsl": False,
                "tp_value": 0.5,
                "sl_value": None,
                "lot": 0.01,
                "max_open_trades": 1,
                "auto_trade_symbol": "XAUUSD",
                "auto_trade_interval_sec": 2,
                "trade_history_sync_days": 90,
                "trade_history_sync_all": False,
                "auto_trade_risk_mode": "fixed_lot",
                "auto_trade_risk_percent": 1.0,
                "auto_trade_use_account_balance": True,
                "auto_trade_use_available_margin": True,
                "auto_trade_min_free_margin_pct": 30.0,
                "auto_trade_max_margin_usage_pct": 70.0,
                "auto_trade_max_spread_points": 120,
                "auto_trade_min_signal_score": 0.55,
                "auto_trade_allow_sell": True,
                "auto_trade_cooldown_sec": 30,
                "auto_trade_session_start_hour": 0,
                "auto_trade_session_end_hour": 24,
                "auto_trade_use_atr_tpsl": True,
                "auto_trade_atr_period": 14,
                "auto_trade_atr_sl_mult": 1.5,
                "auto_trade_atr_tp_mult": 2.5,
                "auto_trade_trailing_enabled": True,
                "auto_trade_trailing_activation_rr": 1.0,
                "auto_trade_trailing_atr_mult": 1.0,
                "auto_trade_confidence_model": "weighted",
                "auto_trade_confidence_threshold": 0.6,
                "auto_trade_tf_weight_m1": 0.35,
                "auto_trade_tf_weight_m5": 0.30,
                "auto_trade_tf_weight_m15": 0.20,
                "auto_trade_tf_weight_m30": 0.15,
                "auto_trade_partial_tp_enabled": True,
                "auto_trade_partial_tp_rr1": 1.0,
                "auto_trade_partial_tp_close_pct1": 40.0,
                "auto_trade_partial_tp_rr2": 2.0,
                "auto_trade_partial_tp_close_pct2": 35.0,
                "auto_trade_break_even_enabled": True,
                "auto_trade_break_even_rr": 1.0,
                "auto_trade_break_even_offset_atr_mult": 0.1,
                "auto_trade_trailing_mode": "stateful_hl",
                "auto_trade_stateful_trail_buffer_atr_mult": 0.5,
                "history": [],
            }
        transactions = get_account_transactions(limit=200)
        return {
            "balance": row["balance"],
            "initial_balance": row["initial_balance"],
            "enable_real_trade": bool(row["enable_real_trade"]),
            "auto_trade_enabled": bool(row["auto_trade_enabled"]),
            "keep_terminal_alive": bool(row["keep_terminal_alive"]),
            "data_feed_broker_id": row["data_feed_broker_id"],
            "auto_analytic_tpsl": bool(row["auto_analytic_tpsl"]),
            "tp_value": row["tp_value"],
            "sl_value": row["sl_value"],
            "lot": row["lot"],
            "max_open_trades": row["max_open_trades"],
            "auto_trade_symbol": (row["auto_trade_symbol"] or "XAUUSD"),
            "auto_trade_interval_sec": row["auto_trade_interval_sec"] if row["auto_trade_interval_sec"] is not None else 2,
            "trade_history_sync_days": row["trade_history_sync_days"] if row["trade_history_sync_days"] is not None else 90,
            "trade_history_sync_all": bool(row["trade_history_sync_all"]),
            "auto_trade_risk_mode": (row["auto_trade_risk_mode"] or "fixed_lot"),
            "auto_trade_risk_percent": float(row["auto_trade_risk_percent"] if row["auto_trade_risk_percent"] is not None else 1.0),
            "auto_trade_use_account_balance": bool(row["auto_trade_use_account_balance"]),
            "auto_trade_use_available_margin": bool(row["auto_trade_use_available_margin"]),
            "auto_trade_min_free_margin_pct": float(row["auto_trade_min_free_margin_pct"] if row["auto_trade_min_free_margin_pct"] is not None else 30.0),
            "auto_trade_max_margin_usage_pct": float(row["auto_trade_max_margin_usage_pct"] if row["auto_trade_max_margin_usage_pct"] is not None else 70.0),
            "auto_trade_max_spread_points": int(row["auto_trade_max_spread_points"] if row["auto_trade_max_spread_points"] is not None else 120),
            "auto_trade_min_signal_score": float(row["auto_trade_min_signal_score"] if row["auto_trade_min_signal_score"] is not None else 0.55),
            "auto_trade_allow_sell": bool(row["auto_trade_allow_sell"]),
            "auto_trade_cooldown_sec": int(row["auto_trade_cooldown_sec"] if row["auto_trade_cooldown_sec"] is not None else 30),
            "auto_trade_session_start_hour": int(row["auto_trade_session_start_hour"] if row["auto_trade_session_start_hour"] is not None else 0),
            "auto_trade_session_end_hour": int(row["auto_trade_session_end_hour"] if row["auto_trade_session_end_hour"] is not None else 24),
            "auto_trade_use_atr_tpsl": bool(row["auto_trade_use_atr_tpsl"]),
            "auto_trade_atr_period": int(row["auto_trade_atr_period"] if row["auto_trade_atr_period"] is not None else 14),
            "auto_trade_atr_sl_mult": float(row["auto_trade_atr_sl_mult"] if row["auto_trade_atr_sl_mult"] is not None else 1.5),
            "auto_trade_atr_tp_mult": float(row["auto_trade_atr_tp_mult"] if row["auto_trade_atr_tp_mult"] is not None else 2.5),
            "auto_trade_trailing_enabled": bool(row["auto_trade_trailing_enabled"]),
            "auto_trade_trailing_activation_rr": float(row["auto_trade_trailing_activation_rr"] if row["auto_trade_trailing_activation_rr"] is not None else 1.0),
            "auto_trade_trailing_atr_mult": float(row["auto_trade_trailing_atr_mult"] if row["auto_trade_trailing_atr_mult"] is not None else 1.0),
            "auto_trade_confidence_model": (row["auto_trade_confidence_model"] or "weighted"),
            "auto_trade_confidence_threshold": float(row["auto_trade_confidence_threshold"] if row["auto_trade_confidence_threshold"] is not None else 0.6),
            "auto_trade_tf_weight_m1": float(row["auto_trade_tf_weight_m1"] if row["auto_trade_tf_weight_m1"] is not None else 0.35),
            "auto_trade_tf_weight_m5": float(row["auto_trade_tf_weight_m5"] if row["auto_trade_tf_weight_m5"] is not None else 0.30),
            "auto_trade_tf_weight_m15": float(row["auto_trade_tf_weight_m15"] if row["auto_trade_tf_weight_m15"] is not None else 0.20),
            "auto_trade_tf_weight_m30": float(row["auto_trade_tf_weight_m30"] if row["auto_trade_tf_weight_m30"] is not None else 0.15),
            "auto_trade_partial_tp_enabled": bool(row["auto_trade_partial_tp_enabled"]),
            "auto_trade_partial_tp_rr1": float(row["auto_trade_partial_tp_rr1"] if row["auto_trade_partial_tp_rr1"] is not None else 1.0),
            "auto_trade_partial_tp_close_pct1": float(row["auto_trade_partial_tp_close_pct1"] if row["auto_trade_partial_tp_close_pct1"] is not None else 40.0),
            "auto_trade_partial_tp_rr2": float(row["auto_trade_partial_tp_rr2"] if row["auto_trade_partial_tp_rr2"] is not None else 2.0),
            "auto_trade_partial_tp_close_pct2": float(row["auto_trade_partial_tp_close_pct2"] if row["auto_trade_partial_tp_close_pct2"] is not None else 35.0),
            "auto_trade_break_even_enabled": bool(row["auto_trade_break_even_enabled"]),
            "auto_trade_break_even_rr": float(row["auto_trade_break_even_rr"] if row["auto_trade_break_even_rr"] is not None else 1.0),
            "auto_trade_break_even_offset_atr_mult": float(row["auto_trade_break_even_offset_atr_mult"] if row["auto_trade_break_even_offset_atr_mult"] is not None else 0.1),
            "auto_trade_trailing_mode": (row["auto_trade_trailing_mode"] or "stateful_hl"),
            "auto_trade_stateful_trail_buffer_atr_mult": float(row["auto_trade_stateful_trail_buffer_atr_mult"] if row["auto_trade_stateful_trail_buffer_atr_mult"] is not None else 0.5),
            "history": transactions,
        }


def save_account_state(state):
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO account_state (
                id, balance, initial_balance, enable_real_trade, auto_trade_enabled,
                keep_terminal_alive, data_feed_broker_id,
                auto_analytic_tpsl, tp_value, sl_value, lot, max_open_trades,
                auto_trade_symbol, auto_trade_interval_sec,
                trade_history_sync_days, trade_history_sync_all,
                auto_trade_risk_mode, auto_trade_risk_percent,
                auto_trade_use_account_balance, auto_trade_use_available_margin,
                auto_trade_min_free_margin_pct, auto_trade_max_margin_usage_pct,
                auto_trade_max_spread_points, auto_trade_min_signal_score,
                auto_trade_allow_sell, auto_trade_cooldown_sec,
                auto_trade_session_start_hour, auto_trade_session_end_hour,
                auto_trade_use_atr_tpsl, auto_trade_atr_period,
                auto_trade_atr_sl_mult, auto_trade_atr_tp_mult,
                auto_trade_trailing_enabled, auto_trade_trailing_activation_rr,
                auto_trade_trailing_atr_mult, auto_trade_confidence_model,
                auto_trade_confidence_threshold,
                auto_trade_tf_weight_m1, auto_trade_tf_weight_m5,
                auto_trade_tf_weight_m15, auto_trade_tf_weight_m30,
                auto_trade_partial_tp_enabled,
                auto_trade_partial_tp_rr1, auto_trade_partial_tp_close_pct1,
                auto_trade_partial_tp_rr2, auto_trade_partial_tp_close_pct2,
                auto_trade_break_even_enabled,
                auto_trade_break_even_rr, auto_trade_break_even_offset_atr_mult,
                auto_trade_trailing_mode, auto_trade_stateful_trail_buffer_atr_mult
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                balance = excluded.balance,
                initial_balance = excluded.initial_balance,
                enable_real_trade = excluded.enable_real_trade,
                auto_trade_enabled = excluded.auto_trade_enabled,
                keep_terminal_alive = excluded.keep_terminal_alive,
                data_feed_broker_id = excluded.data_feed_broker_id,
                auto_analytic_tpsl = excluded.auto_analytic_tpsl,
                tp_value = excluded.tp_value,
                sl_value = excluded.sl_value,
                lot = excluded.lot,
                max_open_trades = excluded.max_open_trades,
                auto_trade_symbol = excluded.auto_trade_symbol,
                auto_trade_interval_sec = excluded.auto_trade_interval_sec,
                trade_history_sync_days = excluded.trade_history_sync_days,
                trade_history_sync_all = excluded.trade_history_sync_all,
                auto_trade_risk_mode = excluded.auto_trade_risk_mode,
                auto_trade_risk_percent = excluded.auto_trade_risk_percent,
                auto_trade_use_account_balance = excluded.auto_trade_use_account_balance,
                auto_trade_use_available_margin = excluded.auto_trade_use_available_margin,
                auto_trade_min_free_margin_pct = excluded.auto_trade_min_free_margin_pct,
                auto_trade_max_margin_usage_pct = excluded.auto_trade_max_margin_usage_pct,
                auto_trade_max_spread_points = excluded.auto_trade_max_spread_points,
                auto_trade_min_signal_score = excluded.auto_trade_min_signal_score,
                auto_trade_allow_sell = excluded.auto_trade_allow_sell,
                auto_trade_cooldown_sec = excluded.auto_trade_cooldown_sec,
                auto_trade_session_start_hour = excluded.auto_trade_session_start_hour,
                auto_trade_session_end_hour = excluded.auto_trade_session_end_hour,
                auto_trade_use_atr_tpsl = excluded.auto_trade_use_atr_tpsl,
                auto_trade_atr_period = excluded.auto_trade_atr_period,
                auto_trade_atr_sl_mult = excluded.auto_trade_atr_sl_mult,
                auto_trade_atr_tp_mult = excluded.auto_trade_atr_tp_mult,
                auto_trade_trailing_enabled = excluded.auto_trade_trailing_enabled,
                auto_trade_trailing_activation_rr = excluded.auto_trade_trailing_activation_rr,
                auto_trade_trailing_atr_mult = excluded.auto_trade_trailing_atr_mult,
                auto_trade_confidence_model = excluded.auto_trade_confidence_model,
                auto_trade_confidence_threshold = excluded.auto_trade_confidence_threshold,
                auto_trade_tf_weight_m1 = excluded.auto_trade_tf_weight_m1,
                auto_trade_tf_weight_m5 = excluded.auto_trade_tf_weight_m5,
                auto_trade_tf_weight_m15 = excluded.auto_trade_tf_weight_m15,
                auto_trade_tf_weight_m30 = excluded.auto_trade_tf_weight_m30,
                auto_trade_partial_tp_enabled = excluded.auto_trade_partial_tp_enabled,
                auto_trade_partial_tp_rr1 = excluded.auto_trade_partial_tp_rr1,
                auto_trade_partial_tp_close_pct1 = excluded.auto_trade_partial_tp_close_pct1,
                auto_trade_partial_tp_rr2 = excluded.auto_trade_partial_tp_rr2,
                auto_trade_partial_tp_close_pct2 = excluded.auto_trade_partial_tp_close_pct2,
                auto_trade_break_even_enabled = excluded.auto_trade_break_even_enabled,
                auto_trade_break_even_rr = excluded.auto_trade_break_even_rr,
                auto_trade_break_even_offset_atr_mult = excluded.auto_trade_break_even_offset_atr_mult,
                auto_trade_trailing_mode = excluded.auto_trade_trailing_mode,
                auto_trade_stateful_trail_buffer_atr_mult = excluded.auto_trade_stateful_trail_buffer_atr_mult
            """,
            (
                state.get("balance", 1000),
                state.get("initial_balance", state.get("balance", 1000)),
                int(bool(state.get("enable_real_trade", False))),
                int(bool(state.get("auto_trade_enabled", False))),
                int(bool(state.get("keep_terminal_alive", True))),
                state.get("data_feed_broker_id", None),
                int(bool(state.get("auto_analytic_tpsl", False))),
                state.get("tp_value", 0.5),
                state.get("sl_value", None),
                state.get("lot", 0.01),
                state.get("max_open_trades", 1),
                state.get("auto_trade_symbol", "XAUUSD"),
                state.get("auto_trade_interval_sec", 2),
                state.get("trade_history_sync_days", 90),
                int(bool(state.get("trade_history_sync_all", False))),
                state.get("auto_trade_risk_mode", "fixed_lot"),
                state.get("auto_trade_risk_percent", 1.0),
                int(bool(state.get("auto_trade_use_account_balance", True))),
                int(bool(state.get("auto_trade_use_available_margin", True))),
                state.get("auto_trade_min_free_margin_pct", 30.0),
                state.get("auto_trade_max_margin_usage_pct", 70.0),
                state.get("auto_trade_max_spread_points", 120),
                state.get("auto_trade_min_signal_score", 0.55),
                int(bool(state.get("auto_trade_allow_sell", True))),
                state.get("auto_trade_cooldown_sec", 30),
                state.get("auto_trade_session_start_hour", 0),
                state.get("auto_trade_session_end_hour", 24),
                int(bool(state.get("auto_trade_use_atr_tpsl", True))),
                state.get("auto_trade_atr_period", 14),
                state.get("auto_trade_atr_sl_mult", 1.5),
                state.get("auto_trade_atr_tp_mult", 2.5),
                int(bool(state.get("auto_trade_trailing_enabled", True))),
                state.get("auto_trade_trailing_activation_rr", 1.0),
                state.get("auto_trade_trailing_atr_mult", 1.0),
                state.get("auto_trade_confidence_model", "weighted"),
                state.get("auto_trade_confidence_threshold", 0.6),
                state.get("auto_trade_tf_weight_m1", 0.35),
                state.get("auto_trade_tf_weight_m5", 0.30),
                state.get("auto_trade_tf_weight_m15", 0.20),
                state.get("auto_trade_tf_weight_m30", 0.15),
                int(bool(state.get("auto_trade_partial_tp_enabled", True))),
                state.get("auto_trade_partial_tp_rr1", 1.0),
                state.get("auto_trade_partial_tp_close_pct1", 40.0),
                state.get("auto_trade_partial_tp_rr2", 2.0),
                state.get("auto_trade_partial_tp_close_pct2", 35.0),
                int(bool(state.get("auto_trade_break_even_enabled", True))),
                state.get("auto_trade_break_even_rr", 1.0),
                state.get("auto_trade_break_even_offset_atr_mult", 0.1),
                state.get("auto_trade_trailing_mode", "stateful_hl"),
                state.get("auto_trade_stateful_trail_buffer_atr_mult", 0.5),
            ),
        )


def add_account_transaction(tx_type, amount, note=""):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO account_transactions (type, amount, note, timestamp) VALUES (?, ?, ?, ?)",
            (tx_type, float(amount), note, int(time.time())),
        )


def get_account_transactions(limit=200):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT type, amount, note, timestamp FROM account_transactions ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
        return [
            {
                "type": row["type"],
                "amount": row["amount"],
                "note": row["note"],
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]


def append_trade_history(trade):
    status = trade.get("status") or ("open" if trade.get("exitTime") is None and trade.get("exit") is None else "closed")
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO trade_history (
                trade_id, status, type, symbol, lot, ticket,
                entry, exit, profit, entryTime, exitTime, reason,
                tpValue, slValue, broker_id, broker_name, account_id,
                platform, execution_mode, terminal_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade.get("trade_id"),
                status,
                trade.get("type"),
                trade.get("symbol"),
                trade.get("lot"),
                trade.get("ticket"),
                trade.get("entry"),
                trade.get("exit"),
                trade.get("profit"),
                trade.get("entryTime"),
                trade.get("exitTime"),
                trade.get("reason"),
                trade.get("tpValue"),
                trade.get("slValue"),
                trade.get("broker_id"),
                trade.get("broker_name"),
                trade.get("account_id"),
                trade.get("platform"),
                trade.get("execution_mode"),
                trade.get("terminal_path"),
            ),
        )


def get_trade_history():
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT type, entry, exit, profit, entryTime, exitTime, reason,
                                         tpValue, slValue, broker_id, broker_name, account_id, platform,
                     trade_id, status, symbol, lot, ticket,
                   execution_mode, terminal_path
            FROM trade_history
            ORDER BY entryTime ASC, id ASC
            """
        ).fetchall()
        return [
            {
                "type": row["type"],
                "entry": row["entry"],
                "exit": row["exit"],
                "profit": row["profit"],
                "entryTime": row["entryTime"],
                "exitTime": row["exitTime"],
                "reason": row["reason"],
                "tpValue": row["tpValue"],
                "slValue": row["slValue"],
                "broker_id": row["broker_id"],
                "broker_name": row["broker_name"],
                "account_id": row["account_id"],
                "platform": row["platform"],
                "trade_id": row["trade_id"],
                "status": row["status"],
                "symbol": row["symbol"],
                "lot": row["lot"],
                "ticket": row["ticket"],
                "execution_mode": row["execution_mode"],
                "terminal_path": row["terminal_path"],
            }
            for row in rows
        ]


def create_trade_open_record(trade):
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO trade_history (
                trade_id, status, type, symbol, lot, ticket,
                entry, exit, profit, entryTime, exitTime, reason,
                tpValue, slValue, broker_id, broker_name, account_id, platform,
                execution_mode, terminal_path
            )
            VALUES (?, 'open', ?, ?, ?, ?, ?, NULL, NULL, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade.get("trade_id"),
                trade.get("type"),
                trade.get("symbol"),
                trade.get("lot"),
                trade.get("ticket"),
                trade.get("entry"),
                trade.get("entryTime"),
                trade.get("reason", "open"),
                trade.get("tpValue"),
                trade.get("slValue"),
                trade.get("broker_id"),
                trade.get("broker_name"),
                trade.get("account_id"),
                trade.get("platform"),
                trade.get("execution_mode"),
                trade.get("terminal_path"),
            ),
        )


def upsert_trade_history_record(trade, match_open_window_seconds=300):
    ticket = trade.get("ticket")
    broker_id = trade.get("broker_id")
    account_id = trade.get("account_id")
    trade_id = trade.get("trade_id")
    status = trade.get("status") or "closed"
    entry_time = trade.get("entryTime")
    symbol = trade.get("symbol")
    trade_type = trade.get("type")

    with get_db() as conn:
        row = None

        if trade_id:
            row = conn.execute(
                "SELECT id FROM trade_history WHERE trade_id = ? ORDER BY id DESC LIMIT 1",
                (trade_id,),
            ).fetchone()

        if not row and ticket not in (None, "", 0):
            if account_id is None:
                row = conn.execute(
                    """
                    SELECT id FROM trade_history
                    WHERE ticket = ?
                      AND COALESCE(broker_id, -1) = COALESCE(?, -1)
                    ORDER BY CASE WHEN status = 'open' THEN 0 ELSE 1 END, id DESC
                    LIMIT 1
                    """,
                    (ticket, broker_id),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT id FROM trade_history
                    WHERE ticket = ?
                      AND COALESCE(broker_id, -1) = COALESCE(?, -1)
                      AND COALESCE(account_id, -1) = COALESCE(?, -1)
                    ORDER BY CASE WHEN status = 'open' THEN 0 ELSE 1 END, id DESC
                    LIMIT 1
                    """,
                    (ticket, broker_id, account_id),
                ).fetchone()

        if not row and status == "open" and symbol and trade_type and entry_time:
            row = conn.execute(
                """
                SELECT id FROM trade_history
                WHERE status = 'open'
                  AND (ticket IS NULL OR ticket = 0)
                  AND COALESCE(broker_id, -1) = COALESCE(?, -1)
                  AND symbol = ?
                  AND UPPER(type) = UPPER(?)
                  AND ABS(COALESCE(entryTime, 0) - ?) <= ?
                ORDER BY ABS(COALESCE(entryTime, 0) - ?) ASC, id DESC
                LIMIT 1
                """,
                (broker_id, symbol, trade_type, int(entry_time), int(match_open_window_seconds), int(entry_time)),
            ).fetchone()

        if row:
            conn.execute(
                """
                UPDATE trade_history
                SET trade_id = COALESCE(trade_id, ?),
                    status = ?,
                    type = COALESCE(?, type),
                    symbol = COALESCE(?, symbol),
                    lot = COALESCE(?, lot),
                    ticket = COALESCE(?, ticket),
                    entry = COALESCE(?, entry),
                    exit = CASE WHEN ? IS NULL THEN exit ELSE ? END,
                    profit = CASE WHEN ? IS NULL THEN profit ELSE ? END,
                    entryTime = COALESCE(?, entryTime),
                    exitTime = CASE WHEN ? IS NULL THEN exitTime ELSE ? END,
                    reason = COALESCE(?, reason),
                    tpValue = CASE WHEN ? IS NULL THEN tpValue ELSE ? END,
                    slValue = CASE WHEN ? IS NULL THEN slValue ELSE ? END,
                    broker_id = COALESCE(?, broker_id),
                    broker_name = COALESCE(?, broker_name),
                    account_id = COALESCE(?, account_id),
                    platform = COALESCE(?, platform),
                    execution_mode = COALESCE(?, execution_mode),
                    terminal_path = COALESCE(?, terminal_path)
                WHERE id = ?
                """,
                (
                    trade_id,
                    status,
                    trade_type,
                    symbol,
                    trade.get("lot"),
                    ticket,
                    trade.get("entry"),
                    trade.get("exit"),
                    trade.get("exit"),
                    trade.get("profit"),
                    trade.get("profit"),
                    entry_time,
                    trade.get("exitTime"),
                    trade.get("exitTime"),
                    trade.get("reason"),
                    trade.get("tpValue"),
                    trade.get("tpValue"),
                    trade.get("slValue"),
                    trade.get("slValue"),
                    broker_id,
                    trade.get("broker_name"),
                    account_id,
                    trade.get("platform"),
                    trade.get("execution_mode"),
                    trade.get("terminal_path"),
                    row["id"],
                ),
            )
            return row["id"]

        conn.execute(
            """
            INSERT INTO trade_history (
                trade_id, status, type, symbol, lot, ticket,
                entry, exit, profit, entryTime, exitTime, reason,
                tpValue, slValue, broker_id, broker_name, account_id,
                platform, execution_mode, terminal_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade_id,
                status,
                trade_type,
                symbol,
                trade.get("lot"),
                ticket,
                trade.get("entry"),
                trade.get("exit"),
                trade.get("profit"),
                entry_time,
                trade.get("exitTime"),
                trade.get("reason"),
                trade.get("tpValue"),
                trade.get("slValue"),
                broker_id,
                trade.get("broker_name"),
                account_id,
                trade.get("platform"),
                trade.get("execution_mode"),
                trade.get("terminal_path"),
            ),
        )
        return conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]


def close_trade_record(trade_id, *, exit_price=None, profit=None, exit_time=None, ticket=None, reason="close"):
    with get_db() as conn:
        conn.execute(
            """
            UPDATE trade_history
            SET status = 'closed',
                exit = COALESCE(?, exit),
                profit = COALESCE(?, profit),
                exitTime = COALESCE(?, exitTime),
                ticket = COALESCE(?, ticket),
                reason = ?
            WHERE trade_id = ? AND status = 'open'
            """,
            (exit_price, profit, exit_time or int(time.time()), ticket, reason, trade_id),
        )


def list_open_trades(broker_id=None):
    with get_db() as conn:
        if broker_id is None:
            rows = conn.execute(
                """
                SELECT trade_id, type, symbol, lot, ticket, entry, entryTime,
                      tpValue, slValue, broker_id, broker_name, account_id, platform,
                       execution_mode, terminal_path
                FROM trade_history
                WHERE status = 'open'
                ORDER BY entryTime ASC, id ASC
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT trade_id, type, symbol, lot, ticket, entry, entryTime,
                      tpValue, slValue, broker_id, broker_name, account_id, platform,
                       execution_mode, terminal_path
                FROM trade_history
                WHERE status = 'open' AND broker_id = ?
                ORDER BY entryTime ASC, id ASC
                """,
                (broker_id,),
            ).fetchall()
    return [
        {
            "trade_id": row["trade_id"],
            "type": row["type"],
            "symbol": row["symbol"],
            "lot": row["lot"],
            "ticket": row["ticket"],
            "entry": row["entry"],
            "entryTime": row["entryTime"],
            "tpValue": row["tpValue"],
            "slValue": row["slValue"],
            "broker_id": row["broker_id"],
            "broker_name": row["broker_name"],
            "account_id": row["account_id"],
            "platform": row["platform"],
            "execution_mode": row["execution_mode"],
            "terminal_path": row["terminal_path"],
        }
        for row in rows
    ]


def update_open_trade_tpsl(trade_id, tp_value=None, sl_value=None):
    with get_db() as conn:
        cur = conn.execute(
            """
            UPDATE trade_history
            SET tpValue = ?,
                slValue = ?
            WHERE trade_id = ? AND status = 'open'
            """,
            (tp_value, sl_value, trade_id),
        )
    return cur.rowcount > 0


def apply_partial_close_record(trade_id, *, closed_lot, exit_price=None, profit=None, exit_time=None, reason="partial_take_profit"):
    ts = int(exit_time or time.time())
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT trade_id, type, symbol, lot, ticket, entry, entryTime,
                   tpValue, slValue, broker_id, broker_name, account_id,
                   platform, execution_mode, terminal_path
            FROM trade_history
            WHERE trade_id = ? AND status = 'open'
            ORDER BY id DESC
            LIMIT 1
            """,
            (trade_id,),
        ).fetchone()
        if not row:
            return False

        current_lot = float(row["lot"] or 0)
        lot_to_close = max(0.0, min(float(closed_lot or 0), current_lot))
        if lot_to_close <= 0:
            return False

        remaining_lot = max(0.0, current_lot - lot_to_close)

        conn.execute(
            """
            INSERT INTO trade_history (
                trade_id, status, type, symbol, lot, ticket,
                entry, exit, profit, entryTime, exitTime, reason,
                tpValue, slValue, broker_id, broker_name, account_id,
                platform, execution_mode, terminal_path
            )
            VALUES (?, 'closed', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"{trade_id}:partial:{ts}",
                row["type"],
                row["symbol"],
                lot_to_close,
                row["ticket"],
                row["entry"],
                exit_price,
                profit,
                row["entryTime"],
                ts,
                reason,
                row["tpValue"],
                row["slValue"],
                row["broker_id"],
                row["broker_name"],
                row["account_id"],
                row["platform"],
                row["execution_mode"],
                row["terminal_path"],
            ),
        )

        if remaining_lot <= 1e-9:
            conn.execute(
                """
                UPDATE trade_history
                SET status = 'closed',
                    exit = COALESCE(?, exit),
                    profit = COALESCE(?, profit),
                    exitTime = ?,
                    reason = ?
                WHERE trade_id = ? AND status = 'open'
                """,
                (exit_price, profit, ts, reason, trade_id),
            )
        else:
            conn.execute(
                """
                UPDATE trade_history
                SET lot = ?,
                    reason = ?
                WHERE trade_id = ? AND status = 'open'
                """,
                (remaining_lot, reason, trade_id),
            )

        return True


def get_open_trades_count():
    with get_db() as conn:
        row = conn.execute("SELECT COUNT(*) AS total FROM trade_history WHERE status = 'open'").fetchone()
    return int(row["total"]) if row else 0


def clear_trade_history():
    with get_db() as conn:
        conn.execute("DELETE FROM trade_history")


def log_mt5_error(message, broker_id=None, broker_name=None, account_id=None, timestamp=None):
    if message is None:
        safe_message = ""
    elif isinstance(message, str):
        safe_message = message
    else:
        try:
            safe_message = json.dumps(message, ensure_ascii=True, default=str)
        except Exception:
            safe_message = str(message)

    with get_db() as conn:
        conn.execute(
            "INSERT INTO mt5_error_log (timestamp, message, broker_id, broker_name, account_id) VALUES (?, ?, ?, ?, ?)",
            (int(timestamp or time.time()), safe_message, broker_id, broker_name, account_id),
        )


def get_mt5_error_log(limit=500):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT timestamp, message, broker_id, broker_name, account_id FROM mt5_error_log ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
        return [
            {
                "timestamp": row["timestamp"],
                "message": row["message"],
                "broker_id": row["broker_id"],
                "broker_name": row["broker_name"],
                "account_id": row["account_id"],
            }
            for row in rows
        ]


def clear_mt5_error_log():
    with get_db() as conn:
        conn.execute("DELETE FROM mt5_error_log")


def get_auto_trade_profile(broker_id, account_id):
    if broker_id is None or account_id is None:
        return None
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT profile_json
            FROM auto_trade_profiles
            WHERE broker_id = ? AND account_id = ?
            LIMIT 1
            """,
            (int(broker_id), int(account_id)),
        ).fetchone()
    if not row:
        return None
    try:
        data = json.loads(row["profile_json"] or "{}")
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def has_auto_trade_profile(broker_id, account_id):
    if broker_id is None or account_id is None:
        return False
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM auto_trade_profiles
            WHERE broker_id = ? AND account_id = ?
            LIMIT 1
            """,
            (int(broker_id), int(account_id)),
        ).fetchone()
    return bool(row)


def save_auto_trade_profile(broker_id, account_id, profile_dict):
    if broker_id is None or account_id is None:
        return False
    now = int(time.time())
    payload = {k: profile_dict.get(k) for k in AUTO_TRADE_PROFILE_KEYS if k in profile_dict}
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO auto_trade_profiles (broker_id, account_id, profile_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(broker_id, account_id) DO UPDATE SET
                profile_json = excluded.profile_json,
                updated_at = excluded.updated_at
            """,
            (int(broker_id), int(account_id), json.dumps(payload, ensure_ascii=True), now, now),
        )
    return True


def apply_auto_trade_profile_to_state(base_state, broker_id, account_id):
    state = dict(base_state or {})
    profile = get_auto_trade_profile(broker_id, account_id)
    if not profile:
        return state
    for key in AUTO_TRADE_PROFILE_KEYS:
        if key in profile:
            state[key] = profile[key]
    return state


def _normalize_broker_execution_mode(platform, execution_mode):
    if str(platform or "").lower() == "mt4":
        return "mouse"
    mode = str(execution_mode or "mouse").lower()
    return "direct" if mode == "direct" else "mouse"


def list_brokers(include_inactive=False):
    with get_db() as conn:
        if include_inactive:
            rows = conn.execute(
                """
                SELECT id, name, platform, terminal_path, execution_mode, window_hint,
                       default_symbol, is_default, is_active, created_at, updated_at
                FROM brokers
                ORDER BY is_default DESC, name ASC
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, name, platform, terminal_path, execution_mode, window_hint,
                       default_symbol, is_default, is_active, created_at, updated_at
                FROM brokers
                WHERE is_active = 1
                ORDER BY is_default DESC, name ASC
                """
            ).fetchall()
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "platform": row["platform"],
                "terminal_path": row["terminal_path"],
                "execution_mode": _normalize_broker_execution_mode(row["platform"], row["execution_mode"]),
                "window_hint": row["window_hint"],
                "default_symbol": row["default_symbol"],
                "is_default": bool(row["is_default"]),
                "is_active": bool(row["is_active"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]


def get_broker(broker_id):
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT id, name, platform, terminal_path, execution_mode, window_hint,
                   default_symbol, is_default, is_active, created_at, updated_at
            FROM brokers
            WHERE id = ?
            """,
            (broker_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "name": row["name"],
            "platform": row["platform"],
            "terminal_path": row["terminal_path"],
            "execution_mode": _normalize_broker_execution_mode(row["platform"], row["execution_mode"]),
            "window_hint": row["window_hint"],
            "default_symbol": row["default_symbol"],
            "is_default": bool(row["is_default"]),
            "is_active": bool(row["is_active"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


def get_default_broker():
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT id FROM brokers
            WHERE is_default = 1 AND is_active = 1
            ORDER BY id ASC
            LIMIT 1
            """
        ).fetchone()
    if not row:
        brokers = list_brokers(include_inactive=False)
        if not brokers:
            return None
        set_default_broker(brokers[0]["id"])
        return get_broker(brokers[0]["id"])
    return get_broker(row["id"])


def resolve_feed_broker(state=None, require_terminal_path=False):
    if state is None:
        state = get_account_state()

    seen_ids = set()
    candidates = []

    configured = get_broker(state.get("data_feed_broker_id")) if state.get("data_feed_broker_id") else None
    if configured and configured.get("is_active", True):
        candidates.append(configured)

    default_broker = get_default_broker()
    if default_broker and default_broker.get("is_active", True):
        candidates.append(default_broker)

    for broker in list_brokers(include_inactive=False):
        candidates.append(broker)

    for broker in candidates:
        if not broker:
            continue
        broker_id = broker.get("id")
        if broker_id in seen_ids:
            continue
        seen_ids.add(broker_id)

        if not require_terminal_path:
            return broker

        terminal_path = broker.get("terminal_path")
        if terminal_path and os.path.exists(terminal_path):
            return broker

    return None


def create_broker(payload):
    now = int(time.time())
    platform = payload.get("platform", "mt5")
    execution_mode = _normalize_broker_execution_mode(platform, payload.get("execution_mode", "mouse"))
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO brokers (
                name, platform, terminal_path, execution_mode, window_hint, default_symbol,
                is_default, is_active, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 0, 1, ?, ?)
            """,
            (
                payload["name"],
                platform,
                payload.get("terminal_path"),
                execution_mode,
                payload.get("window_hint"),
                payload.get("default_symbol") or "XAUUSD",
                now,
                now,
            ),
        )
        new_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    return get_broker(new_id)


def update_broker(broker_id, payload):
    current = get_broker(broker_id)
    if not current:
        return None
    updated = {
        "name": payload.get("name", current["name"]),
        "platform": payload.get("platform", current["platform"]),
        "terminal_path": payload.get("terminal_path", current["terminal_path"]),
        "execution_mode": payload.get("execution_mode", current["execution_mode"]),
        "window_hint": payload.get("window_hint", current["window_hint"]),
        "default_symbol": payload.get("default_symbol", current.get("default_symbol", "XAUUSD")),
        "is_active": int(bool(payload.get("is_active", current["is_active"]))),
        "updated_at": int(time.time()),
    }
    updated["execution_mode"] = _normalize_broker_execution_mode(updated["platform"], updated["execution_mode"])
    with get_db() as conn:
        conn.execute(
            """
            UPDATE brokers
            SET name = ?, platform = ?, terminal_path = ?, execution_mode = ?,
                window_hint = ?, default_symbol = ?, is_active = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                updated["name"],
                updated["platform"],
                updated["terminal_path"],
                updated["execution_mode"],
                updated["window_hint"],
                updated["default_symbol"],
                updated["is_active"],
                updated["updated_at"],
                broker_id,
            ),
        )
    if current["is_default"] and not bool(updated["is_active"]):
        replacement = next((b for b in list_brokers(False) if b["id"] != broker_id), None)
        if replacement:
            set_default_broker(replacement["id"])
    return get_broker(broker_id)


def set_default_broker(broker_id):
    with get_db() as conn:
        conn.execute("UPDATE brokers SET is_default = 0")
        conn.execute("UPDATE brokers SET is_default = 1, is_active = 1, updated_at = ? WHERE id = ?", (int(time.time()), broker_id))
    return get_broker(broker_id)


def delete_broker(broker_id):
    current = get_broker(broker_id)
    if not current:
        return False
    with get_db() as conn:
        conn.execute("DELETE FROM brokers WHERE id = ?", (broker_id,))
    if current["is_default"]:
        brokers = list_brokers(False)
        if brokers:
            set_default_broker(brokers[0]["id"])
    return True


def insert_trade(trade):
    append_trade_history(trade)
