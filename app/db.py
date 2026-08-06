import json
import os
import sqlite3
import time
from contextlib import contextmanager

DB_PATH = "trading_data.db"

AUTO_TRADE_PROFILE_KEYS = [
    "auto_trade_strategy_name",
    "auto_trade_strategy_revision",
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
    "auto_trade_timeframes",
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
    "auto_trade_risk_selector_strategy",
    "auto_trade_risk_atr_threshold",
    "auto_trade_risk_balance_fixed_threshold",
    "auto_trade_risk_confidence_threshold",
    "auto_trade_risk_spread_fixed_threshold",
    "auto_trade_risk_spread_low_threshold",
    "auto_trade_risk_hybrid_addon_rr_threshold",
    "auto_trade_risk_hybrid_entry_mode",
    "auto_trade_risk_hybrid_addon_mode",
    "auto_trade_risk_adaptive_window_days",
    "auto_trade_risk_adaptive_min_trades",
    "auto_trade_protective_mode",
    "auto_trade_min_hold_sec",
    "auto_trade_reversal_confirm_cycles",
    "hedge_enabled",
    "hedge_threshold",
    "hedge_slots",
]


AUTO_TRADE_RISK_POLICY_DEFAULTS = {
    "auto_trade_risk_selector_strategy": "manual",
    "auto_trade_risk_atr_threshold": 12.0,
    "auto_trade_risk_balance_fixed_threshold": 500.0,
    "auto_trade_risk_confidence_threshold": 0.70,
    "auto_trade_risk_spread_fixed_threshold": 120,
    "auto_trade_risk_spread_low_threshold": 60,
    "auto_trade_risk_hybrid_addon_rr_threshold": 2.0,
    "auto_trade_risk_hybrid_entry_mode": "risk_percent",
    "auto_trade_risk_hybrid_addon_mode": "balance_scaled",
    "auto_trade_risk_adaptive_window_days": 90,
    "auto_trade_risk_adaptive_min_trades": 12,
    "hedge_enabled": True,
    "hedge_threshold": -0.05,
    "hedge_slots": 2,
}


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


def _serialize_profile_payload(profile_dict):
    return {k: profile_dict.get(k) for k in AUTO_TRADE_PROFILE_KEYS if k in profile_dict}


def _safe_json_dumps(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=True)
    except Exception:
        return None


def _safe_json_loads(value):
    if value in (None, ""):
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return None


def _safe_float(value, default=None):
    try:
        return float(value)
    except Exception:
        return default


def _normalize_trade_direction(trade_type):
    value = str(trade_type or "").strip().lower()
    if value in ("buy", "hedge_buy"):
        return "buy"
    if value in ("sell", "hedge_sell"):
        return "sell"
    return None


def _derive_target_learning_fields(row, *, exit_price=None, reason=None):
    direction = _normalize_trade_direction((row or {}).get("type"))
    entry = _safe_float((row or {}).get("entry"), None)
    if direction not in ("buy", "sell") or entry is None:
        return {
            "target_price": None,
            "target_factor": None,
            "target_hit": None,
            "overshoot_before_close": None,
            "force_close_after_target_crossed": None,
        }

    context = _safe_json_loads((row or {}).get("signal_context_json")) or {}
    target_plan = context.get("target_plan") if isinstance(context, dict) else {}
    if not isinstance(target_plan, dict):
        target_plan = {}

    tp_distance = _safe_float((row or {}).get("tpValue"), None)
    target_price = _safe_float((row or {}).get("target_price"), None)
    if target_price is None:
        target_price = _safe_float(target_plan.get("target_price"), None)
    if target_price is None and tp_distance is not None:
        if direction == "buy":
            target_price = entry + tp_distance
        elif direction == "sell":
            target_price = entry - tp_distance

    target_factor = _safe_float((row or {}).get("target_factor"), None)
    if target_factor is None:
        target_factor = _safe_float(target_plan.get("adaptive_factor"), None)

    price_exit = _safe_float(exit_price, _safe_float((row or {}).get("exit"), None))
    if target_price is None or price_exit is None:
        return {
            "target_price": target_price,
            "target_factor": target_factor,
            "target_hit": None,
            "overshoot_before_close": None,
            "force_close_after_target_crossed": None,
        }

    crossed = price_exit >= target_price if direction == "buy" else price_exit <= target_price
    overshoot = (price_exit - target_price) if direction == "buy" else (target_price - price_exit)
    reason_text = str(reason if reason is not None else (row or {}).get("reason") or "").strip().lower()
    force_close_crossed = 1 if ("force_close" in reason_text and crossed) else 0
    target_hit = 1 if (crossed and force_close_crossed == 0) else 0

    return {
        "target_price": target_price,
        "target_factor": target_factor,
        "target_hit": target_hit,
        "overshoot_before_close": overshoot,
        "force_close_after_target_crossed": force_close_crossed,
    }


def get_auto_trade_risk_policy():
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT policy_json
            FROM auto_trade_risk_policy
            WHERE id = 1
            LIMIT 1
            """
        ).fetchone()
    if not row:
        return dict(AUTO_TRADE_RISK_POLICY_DEFAULTS)
    try:
        loaded = json.loads(row["policy_json"] or "{}")
    except Exception:
        loaded = {}
    if not isinstance(loaded, dict):
        loaded = {}
    policy = dict(AUTO_TRADE_RISK_POLICY_DEFAULTS)
    for key in AUTO_TRADE_RISK_POLICY_DEFAULTS.keys():
        if key in loaded:
            policy[key] = loaded[key]
    return policy


def save_auto_trade_risk_policy(policy_dict):
    current = get_auto_trade_risk_policy()
    incoming = dict(policy_dict or {})
    for key in AUTO_TRADE_RISK_POLICY_DEFAULTS.keys():
        if key in incoming:
            current[key] = incoming[key]
    now = int(time.time())
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO auto_trade_risk_policy (id, policy_json, updated_at)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                policy_json = excluded.policy_json,
                updated_at = excluded.updated_at
            """,
            (json.dumps(current, ensure_ascii=True), now),
        )
    return current


def init_db():
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS account_state (
                id INTEGER PRIMARY KEY,
                balance REAL DEFAULT 1000,
                initial_balance REAL DEFAULT 1000,
                auto_trade_strategy_name TEXT DEFAULT 'default',
                auto_trade_strategy_revision INTEGER DEFAULT 1,
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
                auto_trade_timeframes TEXT DEFAULT 'M1,M5,M15,M30',
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
                auto_trade_stateful_trail_buffer_atr_mult REAL DEFAULT 0.5,
                auto_trade_protective_mode TEXT DEFAULT 'broker_sl',
                auto_trade_min_hold_sec INTEGER DEFAULT 15,
                auto_trade_reversal_confirm_cycles INTEGER DEFAULT 2
            )
            """
        )
        _add_column_if_missing(conn, "account_state", "auto_trade_enabled", "INTEGER DEFAULT 0")
        _add_column_if_missing(conn, "account_state", "auto_trade_strategy_name", "TEXT DEFAULT 'default'")
        _add_column_if_missing(conn, "account_state", "auto_trade_strategy_revision", "INTEGER DEFAULT 1")
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
        _add_column_if_missing(conn, "account_state", "auto_trade_timeframes", "TEXT DEFAULT 'M1,M5,M15,M30'")
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
        _add_column_if_missing(conn, "account_state", "auto_trade_protective_mode", "TEXT DEFAULT 'broker_sl'")
        _add_column_if_missing(conn, "account_state", "auto_trade_min_hold_sec", "INTEGER DEFAULT 15")
        _add_column_if_missing(conn, "account_state", "auto_trade_reversal_confirm_cycles", "INTEGER DEFAULT 2")
        conn.execute(
            """
            INSERT INTO account_state (
                id, balance, initial_balance, enable_real_trade, auto_trade_enabled,
                auto_trade_strategy_name, auto_trade_strategy_revision,
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
                auto_trade_confidence_threshold, auto_trade_timeframes,
                auto_trade_tf_weight_m1, auto_trade_tf_weight_m5,
                auto_trade_tf_weight_m15, auto_trade_tf_weight_m30,
                auto_trade_partial_tp_enabled,
                auto_trade_partial_tp_rr1, auto_trade_partial_tp_close_pct1,
                auto_trade_partial_tp_rr2, auto_trade_partial_tp_close_pct2,
                auto_trade_break_even_enabled,
                auto_trade_break_even_rr, auto_trade_break_even_offset_atr_mult,
                auto_trade_trailing_mode, auto_trade_stateful_trail_buffer_atr_mult
            )
            VALUES (1, 1000, 1000, 0, 0, 'default', 1, 1, NULL, 0, 0.5, NULL, 0.01, 1, 'XAUUSD', 2, 90, 0, 'fixed_lot', 1.0, 1, 1, 30, 70, 120, 0.55, 1, 30, 0, 24, 1, 14, 1.5, 2.5, 1, 1.0, 1.0, 'weighted', 0.6, 'M1,M5,M15,M30', 0.35, 0.30, 0.20, 0.15, 1, 1.0, 40.0, 2.0, 35.0, 1, 1.0, 0.1, 'stateful_hl', 0.5)
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
            CREATE TABLE IF NOT EXISTS auto_trade_profile_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                broker_id INTEGER NOT NULL,
                account_id INTEGER NOT NULL,
                profile_json TEXT NOT NULL,
                note TEXT,
                source TEXT,
                created_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS auto_trade_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                broker_id INTEGER,
                broker_name TEXT,
                account_id INTEGER,
                symbol TEXT,
                trade_id TEXT,
                event_type TEXT NOT NULL,
                decision TEXT,
                reason TEXT,
                signal TEXT,
                signal_score REAL,
                spread_points INTEGER,
                max_spread_points INTEGER,
                margin_free REAL,
                equity REAL,
                balance REAL,
                margin_usage_pct REAL,
                atr_value REAL,
                trailing_mode TEXT,
                risk_mode TEXT,
                lot_mode TEXT,
                lot REAL,
                profit REAL,
                rr REAL,
                session_hour INTEGER,
                strategy_name TEXT,
                strategy_revision INTEGER,
                payload_json TEXT
            )
            """
        )
        _add_column_if_missing(conn, "auto_trade_events", "strategy_name", "TEXT")
        _add_column_if_missing(conn, "auto_trade_events", "strategy_revision", "INTEGER")
        _add_column_if_missing(conn, "auto_trade_events", "decision_source", "TEXT")
        _add_column_if_missing(conn, "auto_trade_events", "strategy_meta_json", "TEXT")
        _add_column_if_missing(conn, "auto_trade_events", "constraints_json", "TEXT")
        _add_column_if_missing(conn, "auto_trade_events", "signal_snapshot_json", "TEXT")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS auto_trade_strategy_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT NOT NULL,
                revision INTEGER NOT NULL,
                broker_id INTEGER,
                account_id INTEGER,
                config_json TEXT NOT NULL,
                note TEXT,
                source TEXT,
                created_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_auto_trade_strategy_versions_name_scope
            ON auto_trade_strategy_versions(strategy_name, broker_id, account_id, revision)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS auto_trade_risk_policy (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                policy_json TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO auto_trade_risk_policy (id, policy_json, updated_at)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO NOTHING
            """,
            (json.dumps(AUTO_TRADE_RISK_POLICY_DEFAULTS, ensure_ascii=True), int(time.time())),
        )
        _add_column_if_missing(conn, "trade_history", "trailing_mode", "TEXT")
        _add_column_if_missing(conn, "trade_history", "risk_mode", "TEXT")
        _add_column_if_missing(conn, "trade_history", "signal_score", "REAL")
        _add_column_if_missing(conn, "trade_history", "spread_points", "INTEGER")
        _add_column_if_missing(conn, "trade_history", "margin_usage_pct", "REAL")
        _add_column_if_missing(conn, "trade_history", "equity", "REAL")
        _add_column_if_missing(conn, "trade_history", "balance", "REAL")
        _add_column_if_missing(conn, "trade_history", "atr_value", "REAL")
        _add_column_if_missing(conn, "trade_history", "session_hour", "INTEGER")
        _add_column_if_missing(conn, "trade_history", "signal_context_json", "TEXT")
        _add_column_if_missing(conn, "trade_history", "strategy_name", "TEXT")
        _add_column_if_missing(conn, "trade_history", "strategy_revision", "INTEGER")
        _add_column_if_missing(conn, "trade_history", "target_price", "REAL")
        _add_column_if_missing(conn, "trade_history", "target_factor", "REAL")
        _add_column_if_missing(conn, "trade_history", "target_hit", "INTEGER")
        _add_column_if_missing(conn, "trade_history", "overshoot_before_close", "REAL")
        _add_column_if_missing(conn, "trade_history", "force_close_after_target_crossed", "INTEGER")
        _add_column_if_missing(conn, "trade_history", "mfe_price_distance", "REAL")
        _add_column_if_missing(conn, "trade_history", "mae_price_distance", "REAL")
        _add_column_if_missing(conn, "trade_history", "time_to_close_sec", "INTEGER")
        _add_column_if_missing(conn, "trade_history", "target_first_crossed_at", "INTEGER")
        _add_column_if_missing(conn, "trade_history", "time_to_target_cross_sec", "INTEGER")
        _add_column_if_missing(conn, "trade_history", "open_event_id", "INTEGER")
        _add_column_if_missing(conn, "trade_history", "close_event_id", "INTEGER")
        _add_column_if_missing(conn, "trade_history", "tp_sl_mode", "TEXT")

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
                     auto_trade_confidence_threshold, auto_trade_timeframes,
                     auto_trade_tf_weight_m1, auto_trade_tf_weight_m5,
                     auto_trade_tf_weight_m15, auto_trade_tf_weight_m30,
                     auto_trade_partial_tp_enabled,
                     auto_trade_partial_tp_rr1, auto_trade_partial_tp_close_pct1,
                     auto_trade_partial_tp_rr2, auto_trade_partial_tp_close_pct2,
                     auto_trade_break_even_enabled,
                     auto_trade_break_even_rr, auto_trade_break_even_offset_atr_mult,
                     auto_trade_trailing_mode, auto_trade_stateful_trail_buffer_atr_mult,
                     auto_trade_protective_mode, auto_trade_min_hold_sec,
                     auto_trade_reversal_confirm_cycles
            FROM account_state
            WHERE id = 1
            """
        ).fetchone()
        if not row:
            state = {
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
                "auto_trade_timeframes": "M1,M5,M15,M30",
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
                "auto_trade_protective_mode": "broker_sl",
                "auto_trade_min_hold_sec": 15,
                "auto_trade_reversal_confirm_cycles": 2,
                "history": [],
            }
            state.update(get_auto_trade_risk_policy())
            return state
        transactions = get_account_transactions(limit=200)
        state = {
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
            "auto_trade_timeframes": str(row["auto_trade_timeframes"] or "M1,M5,M15,M30"),
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
            "auto_trade_protective_mode": (row["auto_trade_protective_mode"] or "broker_sl"),
            "auto_trade_min_hold_sec": int(row["auto_trade_min_hold_sec"] if row["auto_trade_min_hold_sec"] is not None else 15),
            "auto_trade_reversal_confirm_cycles": int(row["auto_trade_reversal_confirm_cycles"] if row["auto_trade_reversal_confirm_cycles"] is not None else 2),
            "history": transactions,
        }
        state.update(get_auto_trade_risk_policy())
        return state


def save_account_state(state):
    save_auto_trade_risk_policy(state)
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
                auto_trade_confidence_threshold, auto_trade_timeframes,
                auto_trade_tf_weight_m1, auto_trade_tf_weight_m5,
                auto_trade_tf_weight_m15, auto_trade_tf_weight_m30,
                auto_trade_partial_tp_enabled,
                auto_trade_partial_tp_rr1, auto_trade_partial_tp_close_pct1,
                auto_trade_partial_tp_rr2, auto_trade_partial_tp_close_pct2,
                auto_trade_break_even_enabled,
                auto_trade_break_even_rr, auto_trade_break_even_offset_atr_mult,
                auto_trade_trailing_mode, auto_trade_stateful_trail_buffer_atr_mult
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                auto_trade_timeframes = excluded.auto_trade_timeframes,
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
                state.get("auto_trade_timeframes", "M1,M5,M15,M30"),
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
        conn.execute(
            """
            UPDATE account_state
            SET auto_trade_protective_mode = ?,
                auto_trade_min_hold_sec = ?,
                auto_trade_reversal_confirm_cycles = ?
            WHERE id = 1
            """,
            (
                str(state.get("auto_trade_protective_mode", "broker_sl") or "broker_sl").strip().lower(),
                max(0, int(state.get("auto_trade_min_hold_sec", 15) or 15)),
                max(1, int(state.get("auto_trade_reversal_confirm_cycles", 2) or 2)),
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
                platform, execution_mode, terminal_path,
                trailing_mode, risk_mode, signal_score, spread_points,
                margin_usage_pct, equity, balance, atr_value, session_hour,
                signal_context_json, strategy_name, strategy_revision,
                target_price, target_factor, target_hit, overshoot_before_close,
                force_close_after_target_crossed, mfe_price_distance, mae_price_distance,
                time_to_close_sec, target_first_crossed_at, time_to_target_cross_sec,
                tp_sl_mode
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                trade.get("trailing_mode"),
                trade.get("risk_mode"),
                trade.get("signal_score"),
                trade.get("spread_points"),
                trade.get("margin_usage_pct"),
                trade.get("equity"),
                trade.get("balance"),
                trade.get("atr_value"),
                trade.get("session_hour"),
                _safe_json_dumps(trade.get("signal_context") if trade.get("signal_context") is not None else trade.get("signal_context_json")),
                trade.get("strategy_name"),
                trade.get("strategy_revision"),
                trade.get("target_price"),
                trade.get("target_factor"),
                trade.get("target_hit"),
                trade.get("overshoot_before_close"),
                trade.get("force_close_after_target_crossed"),
                trade.get("mfe_price_distance"),
                trade.get("mae_price_distance"),
                trade.get("time_to_close_sec"),
                trade.get("target_first_crossed_at"),
                trade.get("time_to_target_cross_sec"),
                trade.get("tp_sl_mode"),
            ),
        )


def get_trade_history():
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT type, entry, exit, profit, entryTime, exitTime, reason,
                                         tpValue, slValue, broker_id, broker_name, account_id, platform,
                     trade_id, status, symbol, lot, ticket,
                   execution_mode, terminal_path,
                   trailing_mode, risk_mode, signal_score, spread_points,
                     margin_usage_pct, equity, balance, atr_value, session_hour,
                                         signal_context_json, strategy_name, strategy_revision,
                                         target_price, target_factor, target_hit, overshoot_before_close,
                                         force_close_after_target_crossed, mfe_price_distance,
                                         mae_price_distance, time_to_close_sec, target_first_crossed_at,
                                         time_to_target_cross_sec, tp_sl_mode
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
                "trailing_mode": row["trailing_mode"],
                "risk_mode": row["risk_mode"],
                "signal_score": row["signal_score"],
                "spread_points": row["spread_points"],
                "margin_usage_pct": row["margin_usage_pct"],
                "equity": row["equity"],
                "balance": row["balance"],
                "atr_value": row["atr_value"],
                "session_hour": row["session_hour"],
                "signal_context": _safe_json_loads(row["signal_context_json"]),
                "strategy_name": row["strategy_name"],
                "strategy_revision": row["strategy_revision"],
                "target_price": row["target_price"],
                "target_factor": row["target_factor"],
                "target_hit": row["target_hit"],
                "overshoot_before_close": row["overshoot_before_close"],
                "force_close_after_target_crossed": row["force_close_after_target_crossed"],
                "mfe_price_distance": row["mfe_price_distance"],
                "mae_price_distance": row["mae_price_distance"],
                "time_to_close_sec": row["time_to_close_sec"],
                "target_first_crossed_at": row["target_first_crossed_at"],
                "time_to_target_cross_sec": row["time_to_target_cross_sec"],
                "tp_sl_mode": row["tp_sl_mode"],
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
                execution_mode, terminal_path,
                trailing_mode, risk_mode, signal_score, spread_points,
                margin_usage_pct, equity, balance, atr_value, session_hour,
                signal_context_json, strategy_name, strategy_revision,
                target_price, target_factor, target_hit, overshoot_before_close,
                force_close_after_target_crossed, mfe_price_distance, mae_price_distance,
                time_to_close_sec, target_first_crossed_at, time_to_target_cross_sec,
                tp_sl_mode
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade.get("trade_id"),
                "open",
                trade.get("type"),
                trade.get("symbol"),
                trade.get("lot"),
                trade.get("ticket"),
                trade.get("entry"),
                None,
                None,
                trade.get("entryTime"),
                None,
                trade.get("reason", "open"),
                trade.get("tpValue"),
                trade.get("slValue"),
                trade.get("broker_id"),
                trade.get("broker_name"),
                trade.get("account_id"),
                trade.get("platform"),
                trade.get("execution_mode"),
                trade.get("terminal_path"),
                trade.get("trailing_mode"),
                trade.get("risk_mode"),
                trade.get("signal_score"),
                trade.get("spread_points"),
                trade.get("margin_usage_pct"),
                trade.get("equity"),
                trade.get("balance"),
                trade.get("atr_value"),
                trade.get("session_hour"),
                _safe_json_dumps(trade.get("signal_context") if trade.get("signal_context") is not None else trade.get("signal_context_json")),
                trade.get("strategy_name"),
                trade.get("strategy_revision"),
                trade.get("target_price"),
                trade.get("target_factor"),
                trade.get("target_hit"),
                trade.get("overshoot_before_close"),
                trade.get("force_close_after_target_crossed"),
                trade.get("mfe_price_distance"),
                trade.get("mae_price_distance"),
                trade.get("time_to_close_sec"),
                trade.get("target_first_crossed_at"),
                trade.get("time_to_target_cross_sec"),
                trade.get("tp_sl_mode"),
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
                    terminal_path = COALESCE(?, terminal_path),
                    trailing_mode = COALESCE(?, trailing_mode),
                    risk_mode = COALESCE(?, risk_mode),
                    signal_score = CASE WHEN ? IS NULL THEN signal_score ELSE ? END,
                    spread_points = CASE WHEN ? IS NULL THEN spread_points ELSE ? END,
                    margin_usage_pct = CASE WHEN ? IS NULL THEN margin_usage_pct ELSE ? END,
                    equity = CASE WHEN ? IS NULL THEN equity ELSE ? END,
                    balance = CASE WHEN ? IS NULL THEN balance ELSE ? END,
                    atr_value = CASE WHEN ? IS NULL THEN atr_value ELSE ? END,
                    session_hour = CASE WHEN ? IS NULL THEN session_hour ELSE ? END,
                    signal_context_json = COALESCE(?, signal_context_json),
                    strategy_name = COALESCE(?, strategy_name),
                    strategy_revision = COALESCE(?, strategy_revision),
                    target_price = CASE WHEN ? IS NULL THEN target_price ELSE ? END,
                    target_factor = CASE WHEN ? IS NULL THEN target_factor ELSE ? END,
                    target_hit = CASE WHEN ? IS NULL THEN target_hit ELSE ? END,
                    overshoot_before_close = CASE WHEN ? IS NULL THEN overshoot_before_close ELSE ? END,
                    force_close_after_target_crossed = CASE WHEN ? IS NULL THEN force_close_after_target_crossed ELSE ? END,
                    mfe_price_distance = CASE WHEN ? IS NULL THEN mfe_price_distance ELSE ? END,
                    mae_price_distance = CASE WHEN ? IS NULL THEN mae_price_distance ELSE ? END,
                    time_to_close_sec = CASE WHEN ? IS NULL THEN time_to_close_sec ELSE ? END,
                    target_first_crossed_at = CASE WHEN ? IS NULL THEN target_first_crossed_at ELSE ? END,
                    time_to_target_cross_sec = CASE WHEN ? IS NULL THEN time_to_target_cross_sec ELSE ? END,
                    tp_sl_mode = COALESCE(?, tp_sl_mode)
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
                    trade.get("trailing_mode"),
                    trade.get("risk_mode"),
                    trade.get("signal_score"),
                    trade.get("signal_score"),
                    trade.get("spread_points"),
                    trade.get("spread_points"),
                    trade.get("margin_usage_pct"),
                    trade.get("margin_usage_pct"),
                    trade.get("equity"),
                    trade.get("equity"),
                    trade.get("balance"),
                    trade.get("balance"),
                    trade.get("atr_value"),
                    trade.get("atr_value"),
                    trade.get("session_hour"),
                    trade.get("session_hour"),
                    _safe_json_dumps(trade.get("signal_context") if trade.get("signal_context") is not None else trade.get("signal_context_json")),
                    trade.get("strategy_name"),
                    trade.get("strategy_revision"),
                    trade.get("target_price"),
                    trade.get("target_price"),
                    trade.get("target_factor"),
                    trade.get("target_factor"),
                    trade.get("target_hit"),
                    trade.get("target_hit"),
                    trade.get("overshoot_before_close"),
                    trade.get("overshoot_before_close"),
                    trade.get("force_close_after_target_crossed"),
                    trade.get("force_close_after_target_crossed"),
                    trade.get("mfe_price_distance"),
                    trade.get("mfe_price_distance"),
                    trade.get("mae_price_distance"),
                    trade.get("mae_price_distance"),
                    trade.get("time_to_close_sec"),
                    trade.get("time_to_close_sec"),
                    trade.get("target_first_crossed_at"),
                    trade.get("target_first_crossed_at"),
                    trade.get("time_to_target_cross_sec"),
                    trade.get("time_to_target_cross_sec"),
                    trade.get("tp_sl_mode"),
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
                platform, execution_mode, terminal_path,
                trailing_mode, risk_mode, signal_score, spread_points,
                margin_usage_pct, equity, balance, atr_value, session_hour,
                signal_context_json, strategy_name, strategy_revision,
                target_price, target_factor, target_hit, overshoot_before_close,
                force_close_after_target_crossed, mfe_price_distance, mae_price_distance,
                time_to_close_sec, target_first_crossed_at, time_to_target_cross_sec,
                tp_sl_mode
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                trade.get("trailing_mode"),
                trade.get("risk_mode"),
                trade.get("signal_score"),
                trade.get("spread_points"),
                trade.get("margin_usage_pct"),
                trade.get("equity"),
                trade.get("balance"),
                trade.get("atr_value"),
                trade.get("session_hour"),
                _safe_json_dumps(trade.get("signal_context") if trade.get("signal_context") is not None else trade.get("signal_context_json")),
                trade.get("strategy_name"),
                trade.get("strategy_revision"),
                trade.get("target_price"),
                trade.get("target_factor"),
                trade.get("target_hit"),
                trade.get("overshoot_before_close"),
                trade.get("force_close_after_target_crossed"),
                trade.get("mfe_price_distance"),
                trade.get("mae_price_distance"),
                trade.get("time_to_close_sec"),
                trade.get("target_first_crossed_at"),
                trade.get("time_to_target_cross_sec"),
                trade.get("tp_sl_mode"),
            ),
        )
        return conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]


def get_recent_closed_trades(limit=20, broker_id=None, account_id=None):
    safe_limit = max(1, min(int(limit or 20), 500))
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
            SELECT trade_id, type, symbol, lot, ticket, entry, exit, profit,
                   entryTime, exitTime, reason, tpValue, slValue, broker_id,
                   broker_name, account_id, platform, execution_mode,
                   terminal_path, trailing_mode, risk_mode, signal_score,
                   spread_points, margin_usage_pct, equity, balance, atr_value,
                       session_hour, signal_context_json,
                       target_price, target_factor, target_hit, overshoot_before_close,
                       force_close_after_target_crossed, mfe_price_distance,
                       mae_price_distance, time_to_close_sec, target_first_crossed_at,
                       time_to_target_cross_sec
            FROM trade_history
            WHERE {' AND '.join(clauses)}
            ORDER BY COALESCE(exitTime, entryTime, 0) DESC, id DESC
            LIMIT ?
            """,
            (*params, safe_limit),
        ).fetchall()
    return [
        {
            "trade_id": row["trade_id"],
            "type": row["type"],
            "symbol": row["symbol"],
            "lot": row["lot"],
            "ticket": row["ticket"],
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
            "execution_mode": row["execution_mode"],
            "terminal_path": row["terminal_path"],
            "trailing_mode": row["trailing_mode"],
            "risk_mode": row["risk_mode"],
            "signal_score": row["signal_score"],
            "spread_points": row["spread_points"],
            "margin_usage_pct": row["margin_usage_pct"],
            "equity": row["equity"],
            "balance": row["balance"],
            "atr_value": row["atr_value"],
            "session_hour": row["session_hour"],
            "signal_context": _safe_json_loads(row["signal_context_json"]),
            "target_price": row["target_price"],
            "target_factor": row["target_factor"],
            "target_hit": row["target_hit"],
            "overshoot_before_close": row["overshoot_before_close"],
            "force_close_after_target_crossed": row["force_close_after_target_crossed"],
            "mfe_price_distance": row["mfe_price_distance"],
            "mae_price_distance": row["mae_price_distance"],
            "time_to_close_sec": row["time_to_close_sec"],
            "target_first_crossed_at": row["target_first_crossed_at"],
            "time_to_target_cross_sec": row["time_to_target_cross_sec"],
        }
        for row in rows
    ]


def close_trade_record(trade_id, *, exit_price=None, profit=None, exit_time=None, ticket=None, reason="close", runtime_metrics=None):
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT trade_id, type, entry, exit, reason, tpValue, target_price, target_factor,
                   signal_context_json, entryTime, target_first_crossed_at
            FROM trade_history
            WHERE trade_id = ? AND status = 'open'
            ORDER BY id DESC
            LIMIT 1
            """,
            (trade_id,),
        ).fetchone()
        target_fields = _derive_target_learning_fields(dict(row) if row else {}, exit_price=exit_price, reason=reason)
        metrics = dict(runtime_metrics or {})
        close_ts = int(exit_time or time.time())
        row_map = dict(row) if row else {}
        entry_ts = int(row_map.get("entryTime") or 0)
        first_crossed_at = metrics.get("target_first_crossed_at")
        if first_crossed_at is None:
            first_crossed_at = row_map.get("target_first_crossed_at")
        if first_crossed_at is not None:
            try:
                first_crossed_at = int(first_crossed_at)
            except Exception:
                first_crossed_at = None
        time_to_close_sec = max(0, close_ts - entry_ts) if entry_ts > 0 else None
        time_to_target_cross_sec = max(0, first_crossed_at - entry_ts) if (entry_ts > 0 and first_crossed_at is not None) else None
        conn.execute(
            """
            UPDATE trade_history
            SET status = 'closed',
                exit = COALESCE(?, exit),
                profit = COALESCE(?, profit),
                exitTime = COALESCE(?, exitTime),
                ticket = COALESCE(?, ticket),
                reason = ?,
                target_price = CASE WHEN ? IS NULL THEN target_price ELSE ? END,
                target_factor = CASE WHEN ? IS NULL THEN target_factor ELSE ? END,
                target_hit = CASE WHEN ? IS NULL THEN target_hit ELSE ? END,
                overshoot_before_close = CASE WHEN ? IS NULL THEN overshoot_before_close ELSE ? END,
                force_close_after_target_crossed = CASE WHEN ? IS NULL THEN force_close_after_target_crossed ELSE ? END,
                mfe_price_distance = CASE WHEN ? IS NULL THEN mfe_price_distance ELSE ? END,
                mae_price_distance = CASE WHEN ? IS NULL THEN mae_price_distance ELSE ? END,
                time_to_close_sec = CASE WHEN ? IS NULL THEN time_to_close_sec ELSE ? END,
                target_first_crossed_at = CASE WHEN ? IS NULL THEN target_first_crossed_at ELSE ? END,
                time_to_target_cross_sec = CASE WHEN ? IS NULL THEN time_to_target_cross_sec ELSE ? END
            WHERE trade_id = ? AND status = 'open'
            """,
            (
                exit_price,
                profit,
                close_ts,
                ticket,
                reason,
                target_fields.get("target_price"),
                target_fields.get("target_price"),
                target_fields.get("target_factor"),
                target_fields.get("target_factor"),
                target_fields.get("target_hit"),
                target_fields.get("target_hit"),
                target_fields.get("overshoot_before_close"),
                target_fields.get("overshoot_before_close"),
                target_fields.get("force_close_after_target_crossed"),
                target_fields.get("force_close_after_target_crossed"),
                metrics.get("mfe_price_distance"),
                metrics.get("mfe_price_distance"),
                metrics.get("mae_price_distance"),
                metrics.get("mae_price_distance"),
                time_to_close_sec,
                time_to_close_sec,
                first_crossed_at,
                first_crossed_at,
                time_to_target_cross_sec,
                time_to_target_cross_sec,
                trade_id,
            ),
        )


def list_open_trades(broker_id=None):
    with get_db() as conn:
        if broker_id is None:
            rows = conn.execute(
                """
                SELECT trade_id, type, symbol, lot, ticket, entry, entryTime,
                      tpValue, slValue, broker_id, broker_name, account_id, platform,
                      execution_mode, terminal_path, risk_mode, signal_score,
                        margin_usage_pct, equity, balance, spread_points,
                                                atr_value, session_hour, signal_context_json,
                                                target_price, target_factor
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
                      execution_mode, terminal_path, risk_mode, signal_score,
                        margin_usage_pct, equity, balance, spread_points,
                                                atr_value, session_hour, signal_context_json,
                                                target_price, target_factor
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
            "risk_mode": row["risk_mode"],
            "signal_score": row["signal_score"],
            "margin_usage_pct": row["margin_usage_pct"],
            "equity": row["equity"],
            "balance": row["balance"],
            "spread_points": row["spread_points"],
            "atr_value": row["atr_value"],
            "session_hour": row["session_hour"],
            "signal_context": _safe_json_loads(row["signal_context_json"]),
            "target_price": row["target_price"],
            "target_factor": row["target_factor"],
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
    payload = _serialize_profile_payload(profile_dict or {})
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
        conn.execute(
            """
            INSERT INTO auto_trade_profile_history (broker_id, account_id, profile_json, note, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                int(broker_id),
                int(account_id),
                json.dumps(payload, ensure_ascii=True),
                str((profile_dict or {}).get("profile_note") or "save"),
                str((profile_dict or {}).get("profile_source") or "api"),
                now,
            ),
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


def get_auto_trade_profile_history(broker_id=None, account_id=None, limit=200):
    with get_db() as conn:
        clauses = []
        params = []
        if broker_id is not None:
            clauses.append("broker_id = ?")
            params.append(int(broker_id))
        if account_id is not None:
            clauses.append("account_id = ?")
            params.append(int(account_id))
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(
            f"""
            SELECT broker_id, account_id, profile_json, note, source, created_at
            FROM auto_trade_profile_history
            {where_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (*params, int(limit)),
        ).fetchall()
    result = []
    for row in rows:
        try:
            profile = json.loads(row["profile_json"] or "{}")
        except Exception:
            profile = {}
        result.append(
            {
                "broker_id": row["broker_id"],
                "account_id": row["account_id"],
                "profile": profile if isinstance(profile, dict) else {},
                "note": row["note"],
                "source": row["source"],
                "created_at": row["created_at"],
            }
        )
    return result


def log_auto_trade_event(event):
    if not event:
        return None
    payload = dict(event or {})
    nested_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    strategy_meta = payload.get("strategy_meta") if isinstance(payload.get("strategy_meta"), dict) else nested_payload.get("strategy_meta") if isinstance(nested_payload.get("strategy_meta"), dict) else {}
    constraints = payload.get("constraints") if isinstance(payload.get("constraints"), dict) else nested_payload.get("constraints") if isinstance(nested_payload.get("constraints"), dict) else {}
    signal_snapshot = payload.get("signal_snapshot") if isinstance(payload.get("signal_snapshot"), dict) else nested_payload.get("signal_snapshot") if isinstance(nested_payload.get("signal_snapshot"), dict) else {}
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO auto_trade_events (
                timestamp, broker_id, broker_name, account_id, symbol, trade_id,
                event_type, decision, reason, signal, signal_score,
                spread_points, max_spread_points, margin_free, equity, balance,
                margin_usage_pct, atr_value, trailing_mode, risk_mode, lot_mode,
                lot, profit, rr, session_hour, decision_source,
                strategy_meta_json, constraints_json, signal_snapshot_json,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(payload.get("timestamp") or time.time()),
                payload.get("broker_id"),
                payload.get("broker_name"),
                payload.get("account_id"),
                payload.get("symbol"),
                payload.get("trade_id"),
                payload.get("event_type") or "analysis",
                payload.get("decision"),
                payload.get("reason"),
                payload.get("signal"),
                payload.get("signal_score"),
                payload.get("spread_points"),
                payload.get("max_spread_points"),
                payload.get("margin_free"),
                payload.get("equity"),
                payload.get("balance"),
                payload.get("margin_usage_pct"),
                payload.get("atr_value"),
                payload.get("trailing_mode"),
                payload.get("risk_mode"),
                payload.get("lot_mode"),
                payload.get("lot"),
                payload.get("profit"),
                payload.get("rr"),
                payload.get("session_hour"),
                payload.get("decision_source"),
                json.dumps(strategy_meta, ensure_ascii=True, default=str),
                json.dumps(constraints, ensure_ascii=True, default=str),
                json.dumps(signal_snapshot, ensure_ascii=True, default=str),
                json.dumps(payload.get("payload") or {}, ensure_ascii=True, default=str),
            ),
        )
        return int(cur.lastrowid)


def get_auto_trade_events(limit=1000, broker_id=None, account_id=None, event_type=None, since=None):
    with get_db() as conn:
        clauses = []
        params = []
        if broker_id is not None:
            clauses.append("broker_id = ?")
            params.append(int(broker_id))
        if account_id is not None:
            clauses.append("account_id = ?")
            params.append(int(account_id))
        if event_type:
            clauses.append("event_type = ?")
            params.append(str(event_type))
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(int(since))
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(
            f"""
            SELECT timestamp, broker_id, broker_name, account_id, symbol, trade_id,
                   event_type, decision, reason, signal, signal_score,
                   spread_points, max_spread_points, margin_free, equity, balance,
                   margin_usage_pct, atr_value, trailing_mode, risk_mode, lot_mode,
                   lot, profit, rr, session_hour, decision_source,
                   strategy_meta_json, constraints_json, signal_snapshot_json,
                   payload_json
            FROM auto_trade_events
            {where_sql}
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
            """,
            (*params, int(limit)),
        ).fetchall()
    result = []
    for row in rows:
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except Exception:
            payload = {}
        try:
            strategy_meta = json.loads(row["strategy_meta_json"] or "{}")
        except Exception:
            strategy_meta = {}
        try:
            constraints = json.loads(row["constraints_json"] or "{}")
        except Exception:
            constraints = {}
        try:
            signal_snapshot = json.loads(row["signal_snapshot_json"] or "{}")
        except Exception:
            signal_snapshot = {}
        result.append(
            {
                "timestamp": row["timestamp"],
                "broker_id": row["broker_id"],
                "broker_name": row["broker_name"],
                "account_id": row["account_id"],
                "symbol": row["symbol"],
                "trade_id": row["trade_id"],
                "event_type": row["event_type"],
                "decision": row["decision"],
                "reason": row["reason"],
                "signal": row["signal"],
                "signal_score": row["signal_score"],
                "spread_points": row["spread_points"],
                "max_spread_points": row["max_spread_points"],
                "margin_free": row["margin_free"],
                "equity": row["equity"],
                "balance": row["balance"],
                "margin_usage_pct": row["margin_usage_pct"],
                "atr_value": row["atr_value"],
                "trailing_mode": row["trailing_mode"],
                "risk_mode": row["risk_mode"],
                "lot_mode": row["lot_mode"],
                "lot": row["lot"],
                "profit": row["profit"],
                "rr": row["rr"],
                "session_hour": row["session_hour"],
                "decision_source": row["decision_source"],
                "strategy_meta": strategy_meta if isinstance(strategy_meta, dict) else {},
                "constraints": constraints if isinstance(constraints, dict) else {},
                "signal_snapshot": signal_snapshot if isinstance(signal_snapshot, dict) else {},
                "payload": payload if isinstance(payload, dict) else {},
            }
        )
    return result


def link_trade_event_reference(trade_id, event_id, event_role="open"):
    if not trade_id or event_id is None:
        return False
    role = str(event_role or "open").strip().lower()
    with get_db() as conn:
        if role == "close":
            cur = conn.execute(
                """
                UPDATE trade_history
                SET close_event_id = ?
                WHERE id = (
                    SELECT id FROM trade_history
                    WHERE trade_id = ? AND status = 'closed'
                    ORDER BY id DESC
                    LIMIT 1
                )
                """,
                (int(event_id), str(trade_id)),
            )
            return cur.rowcount > 0
        cur = conn.execute(
            """
            UPDATE trade_history
            SET open_event_id = ?
            WHERE id = (
                SELECT id FROM trade_history
                WHERE trade_id = ? AND status = 'open'
                ORDER BY id DESC
                LIMIT 1
            )
            """,
            (int(event_id), str(trade_id)),
        )
        return cur.rowcount > 0


def get_trade_details(trade_identifier):
    with get_db() as conn:
        row = None
        raw_id = str(trade_identifier or "").strip()
        if raw_id:
            row = conn.execute(
                """
                SELECT *
                FROM trade_history
                WHERE trade_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (raw_id,),
            ).fetchone()
            if row is None:
                try:
                    numeric_id = int(raw_id)
                except Exception:
                    numeric_id = None
                if numeric_id is not None:
                    row = conn.execute(
                        """
                        SELECT *
                        FROM trade_history
                        WHERE id = ?
                        LIMIT 1
                        """,
                        (numeric_id,),
                    ).fetchone()
        if row is None:
            return None

        trade = dict(row)

        open_event = None
        close_event = None
        if trade.get("open_event_id"):
            open_event = conn.execute("SELECT * FROM auto_trade_events WHERE id = ? LIMIT 1", (int(trade.get("open_event_id")),)).fetchone()
        if trade.get("close_event_id"):
            close_event = conn.execute("SELECT * FROM auto_trade_events WHERE id = ? LIMIT 1", (int(trade.get("close_event_id")),)).fetchone()

        if open_event is None:
            open_event = conn.execute(
                """
                SELECT * FROM auto_trade_events
                WHERE trade_id = ? AND event_type = 'open_success'
                ORDER BY timestamp DESC, id DESC
                LIMIT 1
                """,
                (trade.get("trade_id"),),
            ).fetchone()
        if close_event is None:
            close_event = conn.execute(
                """
                SELECT * FROM auto_trade_events
                WHERE trade_id = ? AND event_type IN ('close_success', 'auto_close_done')
                ORDER BY timestamp DESC, id DESC
                LIMIT 1
                """,
                (trade.get("trade_id"),),
            ).fetchone()

    def _event_payload(event_row):
        if not event_row:
            return None
        data = dict(event_row)
        return {
            "id": data.get("id"),
            "timestamp": data.get("timestamp"),
            "event_type": data.get("event_type"),
            "decision": data.get("decision"),
            "decision_source": data.get("decision_source"),
            "reason": data.get("reason"),
            "risk_mode": data.get("risk_mode"),
            "trailing_mode": data.get("trailing_mode"),
            "strategy_meta": _safe_json_loads(data.get("strategy_meta_json")) or {},
            "constraints": _safe_json_loads(data.get("constraints_json")) or {},
            "signal_snapshot": _safe_json_loads(data.get("signal_snapshot_json")) or {},
            "payload": _safe_json_loads(data.get("payload_json")) or {},
        }

    open_data = _event_payload(open_event)
    close_data = _event_payload(close_event)

    return {
        "trade": {
            "id": trade.get("id"),
            "trade_id": trade.get("trade_id"),
            "status": trade.get("status"),
            "type": trade.get("type"),
            "symbol": trade.get("symbol"),
            "lot": trade.get("lot"),
            "entry": trade.get("entry"),
            "exit": trade.get("exit"),
            "profit": trade.get("profit"),
            "entryTime": trade.get("entryTime"),
            "exitTime": trade.get("exitTime"),
            "reason": trade.get("reason"),
            "tpValue": trade.get("tpValue"),
            "slValue": trade.get("slValue"),
            "tp_sl_mode": trade.get("tp_sl_mode"),
            "open_event_id": trade.get("open_event_id"),
            "close_event_id": trade.get("close_event_id"),
        },
        "strategy": {
            "risk_mode": trade.get("risk_mode"),
            "trailing_mode": trade.get("trailing_mode"),
            "execution_mode": trade.get("execution_mode"),
            "decision": (open_data or {}).get("decision"),
            "decision_source": (open_data or {}).get("decision_source"),
            "strategy_meta": (open_data or {}).get("strategy_meta") or {},
        },
        "constraints": (open_data or {}).get("constraints") or {},
        "signal_snapshots": {
            "open": (open_data or {}).get("signal_snapshot") or {},
            "close": (close_data or {}).get("signal_snapshot") or {},
        },
        "events": {
            "open": open_data,
            "close": close_data,
        },
    }


def _trade_rr(row):
    try:
        lot = float(row.get("lot") or 0.0)
        sl_value = float(row.get("slValue") or 0.0)
        profit = float(row.get("profit") or 0.0)
    except Exception:
        return None
    if lot <= 0 or sl_value == 0:
        return None
    risk_amount = abs(sl_value) * 100.0 * lot
    if risk_amount <= 0:
        return None
    return profit / risk_amount


def get_auto_trade_statistics(window_days=30, broker_id=None, account_id=None):
    window_days = max(1, min(int(window_days or 30), 3650))
    since = int(time.time()) - (window_days * 86400)

    events = get_auto_trade_events(limit=50000, broker_id=broker_id, account_id=account_id, since=since)
    open_success_map = {}
    for event in events:
        if event.get("event_type") == "open_success" and event.get("trade_id"):
            open_success_map[str(event.get("trade_id"))] = event

    with get_db() as conn:
        clauses = ["status = 'closed'", "COALESCE(exitTime, entryTime, 0) >= ?"]
        params = [since]
        if broker_id is not None:
            clauses.append("COALESCE(broker_id, -1) = ?")
            params.append(int(broker_id))
        if account_id is not None:
            clauses.append("COALESCE(account_id, -1) = ?")
            params.append(int(account_id))
        rows = conn.execute(
            f"""
            SELECT trade_id, type, symbol, lot, ticket, entry, exit, profit, entryTime, exitTime,
                   reason, tpValue, slValue, broker_id, broker_name, account_id, platform,
                   execution_mode, terminal_path, trailing_mode, risk_mode, signal_score,
                     spread_points, margin_usage_pct, equity, balance, atr_value, session_hour,
                     target_price, target_factor, target_hit, overshoot_before_close,
                                         force_close_after_target_crossed, mfe_price_distance,
                                         mae_price_distance, time_to_close_sec, target_first_crossed_at,
                                         time_to_target_cross_sec
            FROM trade_history
            WHERE {' AND '.join(clauses)}
            ORDER BY COALESCE(exitTime, entryTime, 0) ASC, id ASC
            """,
            params,
        ).fetchall()

    closed_trades = [dict(row) for row in rows]
    total_closed = len(closed_trades)
    wins = 0
    losses = 0
    net_profit = 0.0
    gross_profit = 0.0
    gross_loss = 0.0
    running = 0.0
    peak = 0.0
    max_drawdown = 0.0
    rr_values = []
    hour_map = {}
    mode_map = {}
    risk_mode_map = {}
    symbol_map = {}
    signal_bucket_map = {
        "lt_055": {"count": 0, "wins": 0},
        "055_060": {"count": 0, "wins": 0},
        "060_070": {"count": 0, "wins": 0},
        "gte_070": {"count": 0, "wins": 0},
    }
    target_summary = {
        "evaluated": 0,
        "target_hit": 0,
        "missed_target": 0,
        "force_close_after_target_crossed": 0,
        "overshoot_sum": 0.0,
        "overshoot_count": 0,
        "target_factor_sum": 0.0,
        "target_factor_count": 0,
    }

    for row in closed_trades:
        profit = float(row.get("profit") or 0.0)
        net_profit += profit
        if profit > 0:
            wins += 1
            gross_profit += profit
        elif profit < 0:
            losses += 1
            gross_loss += abs(profit)

        running += profit
        peak = max(peak, running)
        max_drawdown = max(max_drawdown, peak - running)

        rr = _trade_rr(row)
        if rr is not None:
            rr_values.append(rr)

        session_hour = row.get("session_hour")
        if session_hour is None:
            entry_time = int(row.get("entryTime") or 0)
            if entry_time > 0:
                session_hour = time.localtime(entry_time).tm_hour
        if session_hour is not None:
            hour_bucket = hour_map.setdefault(int(session_hour), {"count": 0, "wins": 0, "profit": 0.0})
            hour_bucket["count"] += 1
            hour_bucket["profit"] += profit
            if profit > 0:
                hour_bucket["wins"] += 1

        mode = row.get("trailing_mode") or (open_success_map.get(str(row.get("trade_id"))) or {}).get("trailing_mode") or "unknown"
        mode_bucket = mode_map.setdefault(str(mode), {"count": 0, "wins": 0, "profit": 0.0, "rr_sum": 0.0, "rr_count": 0})
        mode_bucket["count"] += 1
        mode_bucket["profit"] += profit
        if profit > 0:
            mode_bucket["wins"] += 1
        if rr is not None:
            mode_bucket["rr_sum"] += rr
            mode_bucket["rr_count"] += 1

        risk_mode = row.get("risk_mode") or (open_success_map.get(str(row.get("trade_id"))) or {}).get("risk_mode") or "unknown"
        risk_bucket = risk_mode_map.setdefault(str(risk_mode), {"count": 0, "wins": 0, "profit": 0.0, "rr_sum": 0.0, "rr_count": 0})
        risk_bucket["count"] += 1
        risk_bucket["profit"] += profit
        if profit > 0:
            risk_bucket["wins"] += 1
        if rr is not None:
            risk_bucket["rr_sum"] += rr
            risk_bucket["rr_count"] += 1

        symbol = str(row.get("symbol") or "-")
        symbol_bucket = symbol_map.setdefault(symbol, {"count": 0, "wins": 0, "profit": 0.0, "atr_sum": 0.0, "atr_count": 0})
        symbol_bucket["count"] += 1
        symbol_bucket["profit"] += profit
        if profit > 0:
            symbol_bucket["wins"] += 1
        atr_value = row.get("atr_value")
        if atr_value is None:
            atr_value = (open_success_map.get(str(row.get("trade_id"))) or {}).get("atr_value")
        try:
            atr_value = float(atr_value)
        except Exception:
            atr_value = None
        if atr_value is not None and atr_value > 0:
            symbol_bucket["atr_sum"] += atr_value
            symbol_bucket["atr_count"] += 1

        signal_score = row.get("signal_score")
        if signal_score is None:
            signal_score = (open_success_map.get(str(row.get("trade_id"))) or {}).get("signal_score")
        try:
            signal_score = float(signal_score)
        except Exception:
            signal_score = None
        if signal_score is not None:
            if signal_score < 0.55:
                bucket = signal_bucket_map["lt_055"]
            elif signal_score < 0.60:
                bucket = signal_bucket_map["055_060"]
            elif signal_score < 0.70:
                bucket = signal_bucket_map["060_070"]
            else:
                bucket = signal_bucket_map["gte_070"]
            bucket["count"] += 1
            if profit > 0:
                bucket["wins"] += 1

        target_price = _safe_float(row.get("target_price"), None)
        target_hit = row.get("target_hit")
        force_cross = row.get("force_close_after_target_crossed")
        if target_hit is not None or force_cross is not None or target_price is not None:
            target_summary["evaluated"] += 1
            if int(target_hit or 0) == 1:
                target_summary["target_hit"] += 1
            if int(force_cross or 0) == 1:
                target_summary["force_close_after_target_crossed"] += 1
            if int(target_hit or 0) == 0 and int(force_cross or 0) == 0:
                target_summary["missed_target"] += 1

        overshoot = _safe_float(row.get("overshoot_before_close"), None)
        if overshoot is not None:
            target_summary["overshoot_sum"] += overshoot
            target_summary["overshoot_count"] += 1

        target_factor = _safe_float(row.get("target_factor"), None)
        if target_factor is not None:
            target_summary["target_factor_sum"] += target_factor
            target_summary["target_factor_count"] += 1

    analysis_events = [e for e in events if e.get("event_type") == "analysis"]
    blocked_events = [e for e in events if e.get("event_type") == "blocked"]
    spread_blocks = [e for e in blocked_events if e.get("reason") == "spread_too_high"]
    margin_blocks = [e for e in blocked_events if e.get("reason") == "margin_guard_blocked"]
    signal_blocks = [e for e in blocked_events if e.get("reason") == "signal_score_below_threshold"]

    signal_scores = [float(e["signal_score"]) for e in analysis_events if e.get("signal_score") is not None]
    spread_points = [float(e["spread_points"]) for e in analysis_events if e.get("spread_points") is not None]
    margin_usage = [float(e["margin_usage_pct"]) for e in analysis_events if e.get("margin_usage_pct") is not None]

    spread_block_by_broker = {}
    for event in spread_blocks:
        broker = event.get("broker_name") or "-"
        spread_block_by_broker[broker] = spread_block_by_broker.get(broker, 0) + 1

    anomaly_rows = []
    for row in reversed(closed_trades):
        first_crossed_at = _safe_float(row.get("target_first_crossed_at"), None)
        reason_text = str(row.get("reason") or "").strip().lower()
        if first_crossed_at is None or first_crossed_at <= 0:
            continue
        if "tp" in reason_text or "take_profit" in reason_text:
            continue
        anomaly_rows.append(
            {
                "trade_id": row.get("trade_id"),
                "symbol": row.get("symbol"),
                "type": row.get("type"),
                "reason": row.get("reason"),
                "profit": row.get("profit"),
                "entry": row.get("entry"),
                "exit": row.get("exit"),
                "entryTime": row.get("entryTime"),
                "exitTime": row.get("exitTime"),
                "target_price": row.get("target_price"),
                "target_hit": row.get("target_hit"),
                "force_close_after_target_crossed": row.get("force_close_after_target_crossed"),
                "overshoot_before_close": row.get("overshoot_before_close"),
                "mfe_price_distance": row.get("mfe_price_distance"),
                "mae_price_distance": row.get("mae_price_distance"),
                "time_to_close_sec": row.get("time_to_close_sec"),
                "target_first_crossed_at": row.get("target_first_crossed_at"),
                "time_to_target_cross_sec": row.get("time_to_target_cross_sec"),
            }
        )
        if len(anomaly_rows) >= 20:
            break

    return {
        "window_days": window_days,
        "since": since,
        "closed_trades": total_closed,
        "wins": wins,
        "losses": losses,
        "winrate": (wins / total_closed * 100.0) if total_closed else 0.0,
        "net_profit": net_profit,
        "average_profit": (net_profit / total_closed) if total_closed else 0.0,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else None,
        "average_rr": (sum(rr_values) / len(rr_values)) if rr_values else 0.0,
        "max_drawdown": max_drawdown,
        "average_signal_score": (sum(signal_scores) / len(signal_scores)) if signal_scores else None,
        "average_spread_points": (sum(spread_points) / len(spread_points)) if spread_points else None,
        "average_margin_usage_pct": (sum(margin_usage) / len(margin_usage)) if margin_usage else None,
        "signal_blocks": len(signal_blocks),
        "spread_blocks": len(spread_blocks),
        "margin_blocks": len(margin_blocks),
        "spread_block_by_broker": sorted(
            [{"broker": broker, "count": count} for broker, count in spread_block_by_broker.items()],
            key=lambda item: item["count"],
            reverse=True,
        ),
        "profit_distribution": {
            "loss": len([r for r in closed_trades if float(r.get("profit") or 0.0) < 0]),
            "breakeven": len([r for r in closed_trades if abs(float(r.get("profit") or 0.0)) < 1e-9]),
            "win": wins,
        },
        "signal_score_distribution": {
            key: {
                "count": value["count"],
                "winrate": (value["wins"] / value["count"] * 100.0) if value["count"] else 0.0,
            }
            for key, value in signal_bucket_map.items()
        },
        "session_performance": sorted(
            [
                {
                    "hour": hour,
                    "count": value["count"],
                    "winrate": (value["wins"] / value["count"] * 100.0) if value["count"] else 0.0,
                    "profit": value["profit"],
                }
                for hour, value in hour_map.items()
            ],
            key=lambda item: item["hour"],
        ),
        "trailing_mode_performance": sorted(
            [
                {
                    "mode": mode,
                    "count": value["count"],
                    "winrate": (value["wins"] / value["count"] * 100.0) if value["count"] else 0.0,
                    "average_rr": (value["rr_sum"] / value["rr_count"]) if value["rr_count"] else 0.0,
                    "profit": value["profit"],
                }
                for mode, value in mode_map.items()
            ],
            key=lambda item: item["count"],
            reverse=True,
        ),
        "risk_mode_performance": sorted(
            [
                {
                    "mode": mode,
                    "count": value["count"],
                    "winrate": (value["wins"] / value["count"] * 100.0) if value["count"] else 0.0,
                    "average_rr": (value["rr_sum"] / value["rr_count"]) if value["rr_count"] else 0.0,
                    "profit": value["profit"],
                }
                for mode, value in risk_mode_map.items()
            ],
            key=lambda item: item["count"],
            reverse=True,
        ),
        "symbol_volatility": sorted(
            [
                {
                    "symbol": symbol,
                    "count": value["count"],
                    "winrate": (value["wins"] / value["count"] * 100.0) if value["count"] else 0.0,
                    "average_atr": (value["atr_sum"] / value["atr_count"]) if value["atr_count"] else None,
                    "profit": value["profit"],
                }
                for symbol, value in symbol_map.items()
            ],
            key=lambda item: item["count"],
            reverse=True,
        ),
        "target_outcome": {
            "evaluated": target_summary["evaluated"],
            "target_hit": target_summary["target_hit"],
            "missed_target": target_summary["missed_target"],
            "force_close_after_target_crossed": target_summary["force_close_after_target_crossed"],
            "target_hit_rate": (target_summary["target_hit"] / target_summary["evaluated"] * 100.0) if target_summary["evaluated"] else 0.0,
            "average_overshoot_before_close": (target_summary["overshoot_sum"] / target_summary["overshoot_count"]) if target_summary["overshoot_count"] else None,
            "average_target_factor": (target_summary["target_factor_sum"] / target_summary["target_factor_count"]) if target_summary["target_factor_count"] else None,
        },
        "anomaly_audit": {
            "count": len(anomaly_rows),
            "rows": anomaly_rows,
        },
    }


def get_risk_mode_performance(window_days=90, broker_id=None, account_id=None, symbol=None):
    window_days = max(1, min(int(window_days or 90), 3650))
    since = int(time.time()) - (window_days * 86400)
    with get_db() as conn:
        clauses = ["status = 'closed'", "COALESCE(exitTime, entryTime, 0) >= ?", "COALESCE(risk_mode, '') != ''"]
        params = [since]
        if broker_id is not None:
            clauses.append("COALESCE(broker_id, -1) = ?")
            params.append(int(broker_id))
        if account_id is not None:
            clauses.append("COALESCE(account_id, -1) = ?")
            params.append(int(account_id))
        if symbol:
            clauses.append("symbol = ?")
            params.append(str(symbol))
        rows = conn.execute(
            f"""
            SELECT risk_mode, COUNT(*) AS total,
                   SUM(CASE WHEN COALESCE(profit, 0) > 0 THEN 1 ELSE 0 END) AS wins,
                   AVG(COALESCE(profit, 0)) AS avg_profit,
                   SUM(COALESCE(profit, 0)) AS net_profit
            FROM trade_history
            WHERE {' AND '.join(clauses)}
            GROUP BY risk_mode
            """,
            params,
        ).fetchall()
    return [
        {
            "risk_mode": row["risk_mode"],
            "total": int(row["total"] or 0),
            "wins": int(row["wins"] or 0),
            "winrate": (float(row["wins"] or 0) / float(row["total"] or 1)) * 100.0,
            "avg_profit": float(row["avg_profit"] or 0.0),
            "net_profit": float(row["net_profit"] or 0.0),
        }
        for row in rows
    ]


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
