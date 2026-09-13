from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from trading_bot.infrastructure.database.postgres_migrator import (
    generate_alembic_migration_sql,
    normalize_sqlite_timestamp,
    read_sqlite_brokers,
)


def test_normalize_sqlite_timestamp_handles_epoch_seconds():
    value = normalize_sqlite_timestamp(1700000000)

    assert isinstance(value, datetime)
    assert value.tzinfo is timezone.utc
    assert value.year == 2023
    assert value.month == 11


def test_read_sqlite_brokers_reads_rows(tmp_path):
    db_path = tmp_path / "brokers.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE brokers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            platform TEXT NOT NULL DEFAULT 'mt5',
            terminal_path TEXT,
            execution_mode TEXT DEFAULT 'mouse',
            window_hint TEXT,
            default_symbol TEXT DEFAULT 'XAUUSD',
            is_default INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at INTEGER,
            updated_at INTEGER
        )
        """
    )
    conn.execute(
        """
        INSERT INTO brokers (id, name, platform, terminal_path, execution_mode, window_hint, default_symbol, is_default, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (1, "Trade Way", "mt5", "C:/Terminal/terminal64.exe", "direct", "Trade Way", "XAUUSD", 1, 1, 1700000000, 1700000001),
    )
    conn.commit()
    conn.close()

    rows = read_sqlite_brokers(db_path)

    assert len(rows) == 1
    assert rows[0]["name"] == "Trade Way"
    assert rows[0]["is_default"] is True


def test_generate_alembic_migration_sql_includes_core_runtime_tables():
    sql = generate_alembic_migration_sql()

    for table_name in (
        "brokers",
        "account_state",
        "trade_history",
        "mt5_error_log",
        "account_transactions",
        "auto_trade_profiles",
        "auto_trade_profile_history",
        "auto_trade_risk_policy",
    ):
        assert f"{table_name}" in sql
