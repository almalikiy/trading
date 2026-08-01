import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.db as db


def test_init_db_adds_default_symbol_column(tmp_path):
    db.DB_PATH = str(tmp_path / "test.db")
    db.init_db()

    with sqlite3.connect(db.DB_PATH) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(brokers)")}
        assert "default_symbol" in columns

        row = conn.execute(
            "SELECT default_symbol FROM brokers WHERE name = ?",
            ("Default Broker",),
        ).fetchone()
        assert row is not None
        assert row[0] == "XAUUSD"
