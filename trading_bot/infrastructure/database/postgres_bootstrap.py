from __future__ import annotations

from typing import Any

from trading_bot.infrastructure.config.settings import Settings


def build_postgres_dsn(settings: Settings) -> str:
    if settings.postgres_dsn:
        return settings.postgres_dsn

    password = settings.postgres_password.get_secret_value() if settings.postgres_password else ""
    return (
        f"postgresql://{settings.postgres_user}:{password}@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
        f"?sslmode={settings.postgres_sslmode}"
    )


def ensure_brokers_table(conn: Any, *, schema: str = "public") -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.brokers (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
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
        END $$;
        """
    )


def reset_database_for_clean_start(settings: Settings, *, preserve_broker_data_only: bool | None = None) -> dict[str, Any]:
    preserve_only = settings.preserve_broker_data_only if preserve_broker_data_only is None else preserve_broker_data_only
    try:
        import psycopg
    except Exception as exc:  # pragma: no cover - dependency guard
        return {
            "status": "skipped",
            "backend": "postgresql",
            "reason": f"psycopg not installed: {exc}",
            "preserve_broker_data_only": preserve_only,
        }

    dsn = build_postgres_dsn(settings)
    with psycopg.connect(dsn, autocommit=True) as conn:
        schema = settings.postgres_schema or "public"
        ensure_brokers_table(conn, schema=schema)

        if not preserve_only:
            tables = conn.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_type = 'BASE TABLE'
                """,
                (schema,),
            ).fetchall()
            for row in tables:
                name = row[0]
                if name == "brokers":
                    continue
                conn.execute(f'DROP TABLE IF EXISTS {schema}.{name} CASCADE')
            return {
                "status": "reset",
                "backend": "postgresql",
                "schema": schema,
                "preserved": [],
                "tables_cleared": True,
            }

        tables = conn.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_type = 'BASE TABLE'
            """,
            (schema,),
        ).fetchall()
        cleared = []
        for row in tables:
            name = row[0]
            if name == "brokers":
                continue
            conn.execute(f'DROP TABLE IF EXISTS {schema}.{name} CASCADE')
            cleared.append(name)

        ensure_brokers_table(conn, schema=schema)
        return {
            "status": "reset",
            "backend": "postgresql",
            "schema": schema,
            "preserved": ["brokers"],
            "tables_cleared": cleared,
        }


def database_status(settings: Settings) -> dict[str, Any]:
    try:
        import psycopg
    except Exception as exc:  # pragma: no cover
        return {
            "backend": "postgresql",
            "status": "unavailable",
            "reason": f"psycopg not installed: {exc}",
            "dsn": build_postgres_dsn(settings),
        }

    try:
        with psycopg.connect(build_postgres_dsn(settings), autocommit=True) as conn:
            conn.execute("SELECT 1")
            return {
                "backend": "postgresql",
                "status": "ok",
                "database": settings.postgres_db,
                "host": settings.postgres_host,
                "user": settings.postgres_user,
            }
    except Exception as exc:
        return {
            "backend": "postgresql",
            "status": "error",
            "database": settings.postgres_db,
            "host": settings.postgres_host,
            "user": settings.postgres_user,
            "reason": str(exc),
        }
