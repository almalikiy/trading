from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg

from trading_bot.infrastructure.config.settings import get_settings
from trading_bot.infrastructure.database.postgres_bootstrap import build_postgres_dsn


DEFAULT_SQLITE_DB_PATH = Path(__file__).resolve().parents[3] / "trading_data.db"


def normalize_sqlite_timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except ValueError:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def read_sqlite_brokers(db_path: str | os.PathLike[str] | None = None) -> list[dict[str, Any]]:
    target = Path(db_path) if db_path is not None else DEFAULT_SQLITE_DB_PATH
    with sqlite3.connect(str(target)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, name, platform, terminal_path, execution_mode, window_hint,
                   default_symbol, is_default, is_active, created_at, updated_at
            FROM brokers
            ORDER BY is_default DESC, id ASC
            """
        ).fetchall()

    return [
        {
            "id": row["id"],
            "name": row["name"],
            "platform": row["platform"],
            "terminal_path": row["terminal_path"],
            "execution_mode": row["execution_mode"],
            "window_hint": row["window_hint"],
            "default_symbol": row["default_symbol"],
            "is_default": bool(row["is_default"]),
            "is_active": bool(row["is_active"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def ensure_postgres_brokers_schema(conn: Any, *, schema: str = "public") -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.brokers (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL UNIQUE,
            platform VARCHAR(50) NOT NULL DEFAULT 'mt5',
            terminal_path TEXT,
            execution_mode VARCHAR(50) DEFAULT 'mouse',
            window_hint TEXT,
            default_symbol VARCHAR(50) DEFAULT 'XAUUSD',
            is_default BOOLEAN DEFAULT FALSE,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = '{schema}'
                  AND table_name = 'brokers'
                  AND column_name = 'default_symbol'
            ) THEN
                ALTER TABLE {schema}.brokers ADD COLUMN default_symbol VARCHAR(50) DEFAULT 'XAUUSD';
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conrelid = '{schema}.brokers'::regclass
                  AND contype = 'u'
                  AND conname = '{schema}_brokers_name_key'
            ) THEN
                CREATE UNIQUE INDEX IF NOT EXISTS {schema}_brokers_name_key
                    ON {schema}.brokers (name);
            END IF;
        END $$;
        """
    )


def migrate_sqlite_brokers_to_postgres(db_path: str | os.PathLike[str] | None = None, *, schema: str = "public") -> dict[str, Any]:
    settings = get_settings()
    rows = read_sqlite_brokers(db_path)

    if not rows:
        return {
            "status": "skipped",
            "backend": "postgresql",
            "schema": schema,
            "rows_migrated": 0,
            "message": "No broker rows found in SQLite source.",
        }

    dsn = build_postgres_dsn(settings)

    with psycopg.connect(dsn, autocommit=True) as conn:
        ensure_postgres_brokers_schema(conn, schema=schema)

        existing = conn.execute(
            f"SELECT id FROM {schema}.brokers ORDER BY id ASC"
        ).fetchall()
        existing_ids = {row[0] for row in existing}

        inserted = 0
        for row in rows:
            if row["id"] in existing_ids:
                continue
            conn.execute(
                f"""
                INSERT INTO {schema}.brokers (
                    id, name, platform, terminal_path, execution_mode, window_hint,
                    default_symbol, is_default, is_active, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    row["id"],
                    row["name"],
                    row["platform"],
                    row["terminal_path"],
                    row["execution_mode"],
                    row["window_hint"],
                    row["default_symbol"],
                    row["is_default"],
                    row["is_active"],
                    normalize_sqlite_timestamp(row["created_at"]),
                    normalize_sqlite_timestamp(row["updated_at"]),
                ),
            )
            inserted += 1

    return {
        "status": "ok",
        "backend": "postgresql",
        "schema": schema,
        "rows_migrated": inserted,
        "message": "SQLite broker rows migrated to PostgreSQL.",
    }


def generate_alembic_migration_sql() -> str:
    return """
-- Alembic revision template for PostgreSQL-first runtime parity
-- Target: PostgreSQL primary DB

CREATE TABLE IF NOT EXISTS public.brokers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    platform VARCHAR(50) NOT NULL DEFAULT 'mt5',
    terminal_path TEXT,
    execution_mode VARCHAR(50) DEFAULT 'mouse',
    window_hint TEXT,
    default_symbol VARCHAR(50) DEFAULT 'XAUUSD',
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE public.brokers
    ADD COLUMN IF NOT EXISTS default_symbol VARCHAR(50) DEFAULT 'XAUUSD';

CREATE UNIQUE INDEX IF NOT EXISTS public_brokers_name_key
    ON public.brokers (name);

CREATE TABLE IF NOT EXISTS public.account_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    balance DOUBLE PRECISION DEFAULT 1000,
    initial_balance DOUBLE PRECISION DEFAULT 1000,
    enable_real_trade BOOLEAN DEFAULT FALSE,
    auto_trade_enabled BOOLEAN DEFAULT FALSE,
    keep_terminal_alive BOOLEAN DEFAULT FALSE,
    data_feed_broker_id INTEGER,
    auto_analytic_tpsl BOOLEAN DEFAULT FALSE,
    tp_value DOUBLE PRECISION DEFAULT 0.5,
    sl_value DOUBLE PRECISION,
    lot DOUBLE PRECISION DEFAULT 0.01,
    max_open_trades INTEGER DEFAULT 1,
    auto_trade_symbol VARCHAR(50) DEFAULT 'XAUUSD',
    auto_trade_interval_sec INTEGER DEFAULT 2,
    trade_history_sync_days INTEGER DEFAULT 90,
    trade_history_sync_all BOOLEAN DEFAULT FALSE,
    auto_trade_risk_mode VARCHAR(50) DEFAULT 'fixed_lot',
    auto_trade_risk_percent DOUBLE PRECISION DEFAULT 1.0,
    auto_trade_use_account_balance BOOLEAN DEFAULT TRUE,
    auto_trade_use_available_margin BOOLEAN DEFAULT TRUE,
    auto_trade_min_free_margin_pct DOUBLE PRECISION DEFAULT 30,
    auto_trade_max_margin_usage_pct DOUBLE PRECISION DEFAULT 70,
    auto_trade_max_spread_points INTEGER DEFAULT 120,
    auto_trade_min_signal_score DOUBLE PRECISION DEFAULT 0.55,
    auto_trade_allow_sell BOOLEAN DEFAULT TRUE,
    auto_trade_cooldown_sec INTEGER DEFAULT 30,
    auto_trade_session_start_hour INTEGER DEFAULT 0,
    auto_trade_session_end_hour INTEGER DEFAULT 24,
    auto_trade_use_atr_tpsl BOOLEAN DEFAULT TRUE,
    auto_trade_atr_period INTEGER DEFAULT 14,
    auto_trade_atr_sl_mult DOUBLE PRECISION DEFAULT 1.5,
    auto_trade_atr_tp_mult DOUBLE PRECISION DEFAULT 2.5,
    auto_trade_trailing_enabled BOOLEAN DEFAULT TRUE,
    auto_trade_trailing_activation_rr DOUBLE PRECISION DEFAULT 1.0,
    auto_trade_trailing_atr_mult DOUBLE PRECISION DEFAULT 1.0,
    auto_trade_confidence_model VARCHAR(50) DEFAULT 'weighted',
    auto_trade_confidence_threshold DOUBLE PRECISION DEFAULT 0.6,
    auto_trade_timeframes VARCHAR(200) DEFAULT 'M1,M5,M15,M30',
    auto_trade_tf_weight_m1 DOUBLE PRECISION DEFAULT 0.35,
    auto_trade_tf_weight_m5 DOUBLE PRECISION DEFAULT 0.30,
    auto_trade_tf_weight_m15 DOUBLE PRECISION DEFAULT 0.20,
    auto_trade_tf_weight_m30 DOUBLE PRECISION DEFAULT 0.15,
    auto_trade_partial_tp_enabled BOOLEAN DEFAULT TRUE,
    auto_trade_partial_tp_rr1 DOUBLE PRECISION DEFAULT 1.0,
    auto_trade_partial_tp_close_pct1 DOUBLE PRECISION DEFAULT 40.0,
    auto_trade_partial_tp_rr2 DOUBLE PRECISION DEFAULT 2.0,
    auto_trade_partial_tp_close_pct2 DOUBLE PRECISION DEFAULT 35.0,
    auto_trade_break_even_enabled BOOLEAN DEFAULT TRUE,
    auto_trade_break_even_rr DOUBLE PRECISION DEFAULT 1.0,
    auto_trade_break_even_offset_atr_mult DOUBLE PRECISION DEFAULT 0.1,
    auto_trade_trailing_mode VARCHAR(50) DEFAULT 'stateful_hl',
    auto_trade_stateful_trail_buffer_atr_mult DOUBLE PRECISION DEFAULT 0.5,
    auto_trade_protective_mode VARCHAR(50) DEFAULT 'broker_sl',
    auto_trade_min_hold_sec INTEGER DEFAULT 15,
    auto_trade_reversal_confirm_cycles INTEGER DEFAULT 2
);

CREATE TABLE IF NOT EXISTS public.trade_history (
    id SERIAL PRIMARY KEY,
    trade_id VARCHAR(200),
    status VARCHAR(32),
    type VARCHAR(32),
    symbol VARCHAR(64),
    lot DOUBLE PRECISION,
    ticket INTEGER,
    entry DOUBLE PRECISION,
    exit DOUBLE PRECISION,
    profit DOUBLE PRECISION,
    entryTime BIGINT,
    exitTime BIGINT,
    reason TEXT,
    tpValue DOUBLE PRECISION,
    slValue DOUBLE PRECISION,
    broker_id INTEGER,
    broker_name VARCHAR(200),
    account_id INTEGER,
    platform VARCHAR(64),
    execution_mode VARCHAR(50),
    terminal_path TEXT,
    trailing_mode VARCHAR(50),
    risk_mode VARCHAR(50),
    signal_score DOUBLE PRECISION,
    spread_points INTEGER,
    margin_usage_pct DOUBLE PRECISION,
    equity DOUBLE PRECISION,
    balance DOUBLE PRECISION,
    atr_value DOUBLE PRECISION,
    session_hour INTEGER,
    signal_context_json TEXT,
    strategy_name VARCHAR(200),
    strategy_revision INTEGER,
    target_price DOUBLE PRECISION,
    target_factor DOUBLE PRECISION,
    target_hit INTEGER,
    overshoot_before_close DOUBLE PRECISION,
    force_close_after_target_crossed INTEGER,
    mfe_price_distance DOUBLE PRECISION,
    mae_price_distance DOUBLE PRECISION,
    time_to_close_sec INTEGER,
    target_first_crossed_at BIGINT,
    time_to_target_cross_sec INTEGER,
    open_event_id INTEGER,
    close_event_id INTEGER,
    tp_sl_mode VARCHAR(32)
);

CREATE TABLE IF NOT EXISTS public.mt5_error_log (
    id SERIAL PRIMARY KEY,
    timestamp BIGINT,
    message TEXT,
    broker_id INTEGER,
    broker_name VARCHAR(200),
    account_id INTEGER
);

CREATE TABLE IF NOT EXISTS public.account_transactions (
    id SERIAL PRIMARY KEY,
    type VARCHAR(32),
    amount DOUBLE PRECISION,
    note TEXT,
    timestamp BIGINT
);

CREATE TABLE IF NOT EXISTS public.auto_trade_profiles (
    id SERIAL PRIMARY KEY,
    broker_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    profile_json TEXT NOT NULL,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    UNIQUE (broker_id, account_id)
);

CREATE TABLE IF NOT EXISTS public.auto_trade_profile_history (
    id SERIAL PRIMARY KEY,
    broker_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    profile_json TEXT NOT NULL,
    note TEXT,
    source VARCHAR(100),
    created_at BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS public.auto_trade_risk_policy (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    policy_json TEXT NOT NULL,
    updated_at BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS public.auto_trade_events (
    id SERIAL PRIMARY KEY,
    timestamp BIGINT NOT NULL,
    broker_id INTEGER,
    broker_name VARCHAR(200),
    account_id INTEGER,
    symbol VARCHAR(64),
    trade_id VARCHAR(200),
    event_type VARCHAR(100) NOT NULL,
    decision VARCHAR(100),
    reason TEXT,
    signal TEXT,
    signal_score DOUBLE PRECISION,
    spread_points INTEGER,
    max_spread_points INTEGER,
    margin_free DOUBLE PRECISION,
    equity DOUBLE PRECISION,
    balance DOUBLE PRECISION,
    margin_usage_pct DOUBLE PRECISION,
    atr_value DOUBLE PRECISION,
    trailing_mode VARCHAR(50),
    risk_mode VARCHAR(50),
    lot_mode VARCHAR(50),
    lot DOUBLE PRECISION,
    profit DOUBLE PRECISION,
    rr DOUBLE PRECISION,
    session_hour INTEGER,
    strategy_name VARCHAR(200),
    strategy_revision INTEGER,
    payload_json TEXT,
    decision_source VARCHAR(100),
    strategy_meta_json TEXT,
    constraints_json TEXT,
    signal_snapshot_json TEXT
);

CREATE TABLE IF NOT EXISTS public.auto_trade_strategy_versions (
    id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(200) NOT NULL,
    revision INTEGER NOT NULL,
    broker_id INTEGER,
    account_id INTEGER,
    config_json TEXT NOT NULL,
    note TEXT,
    source VARCHAR(100),
    created_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_auto_trade_strategy_versions_name_scope
    ON public.auto_trade_strategy_versions(strategy_name, broker_id, account_id, revision);

INSERT INTO public.auto_trade_risk_policy (id, policy_json, updated_at)
VALUES (1, '{"auto_trade_risk_selector_strategy": "manual", "auto_trade_risk_atr_threshold": 12.0, "auto_trade_risk_balance_fixed_threshold": 500.0, "auto_trade_risk_confidence_threshold": 0.7, "auto_trade_risk_spread_fixed_threshold": 120, "auto_trade_risk_spread_low_threshold": 60, "auto_trade_risk_hybrid_addon_rr_threshold": 2.0, "auto_trade_risk_hybrid_entry_mode": "risk_percent", "auto_trade_risk_hybrid_addon_mode": "balance_scaled", "auto_trade_risk_adaptive_window_days": 90, "auto_trade_risk_adaptive_min_trades": 12, "hedge_enabled": true, "hedge_threshold": -0.05, "hedge_slots": 2}', EXTRACT(EPOCH FROM CURRENT_TIMESTAMP)::BIGINT)
ON CONFLICT (id) DO NOTHING;
"""


__all__ = [
    "DEFAULT_SQLITE_DB_PATH",
    "normalize_sqlite_timestamp",
    "read_sqlite_brokers",
    "ensure_postgres_brokers_schema",
    "migrate_sqlite_brokers_to_postgres",
    "generate_alembic_migration_sql",
]
