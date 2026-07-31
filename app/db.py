import json
import os
import sqlite3
import time
from contextlib import contextmanager

DB_PATH = "trading_data.db"


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
                max_open_trades INTEGER DEFAULT 1
            )
            """
        )
        _add_column_if_missing(conn, "account_state", "auto_trade_enabled", "INTEGER DEFAULT 0")
        _add_column_if_missing(conn, "account_state", "keep_terminal_alive", "INTEGER DEFAULT 1")
        _add_column_if_missing(conn, "account_state", "data_feed_broker_id", "INTEGER")
        conn.execute(
            """
            INSERT INTO account_state (
                id, balance, initial_balance, enable_real_trade, auto_trade_enabled,
                keep_terminal_alive, data_feed_broker_id,
                auto_analytic_tpsl, tp_value, sl_value, lot, max_open_trades
            )
            VALUES (1, 1000, 1000, 0, 0, 1, NULL, 0, 0.5, NULL, 0.01, 1)
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
                platform TEXT,
                execution_mode TEXT,
                terminal_path TEXT
            )
            """
        )
        _add_column_if_missing(conn, "trade_history", "broker_id", "INTEGER")
        _add_column_if_missing(conn, "trade_history", "broker_name", "TEXT")
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
                broker_name TEXT
            )
            """
        )
        _add_column_if_missing(conn, "mt5_error_log", "broker_id", "INTEGER")
        _add_column_if_missing(conn, "mt5_error_log", "broker_name", "TEXT")

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
            CREATE TABLE IF NOT EXISTS brokers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                platform TEXT NOT NULL DEFAULT 'mt5',
                terminal_path TEXT,
                execution_mode TEXT NOT NULL DEFAULT 'mouse',
                window_hint TEXT,
                is_default INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )

        now = int(time.time())
        conn.execute(
            """
            INSERT INTO brokers (
                name, platform, terminal_path, execution_mode,
                window_hint, is_default, is_active, created_at, updated_at
            )
            VALUES (?, 'mt5', NULL, 'mouse', 'FinexBisnisSolusi', 1, 1, ?, ?)
            ON CONFLICT(name) DO NOTHING
            """,
            ("Default Broker", now, now),
        )

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
                     tp_value, sl_value, lot, max_open_trades
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
            "history": transactions,
        }


def save_account_state(state):
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO account_state (
                id, balance, initial_balance, enable_real_trade, auto_trade_enabled,
                keep_terminal_alive, data_feed_broker_id,
                auto_analytic_tpsl, tp_value, sl_value, lot, max_open_trades
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                max_open_trades = excluded.max_open_trades
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
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO trade_history (
                type, entry, exit, profit, entryTime, exitTime, reason,
                tpValue, slValue, broker_id, broker_name, platform,
                execution_mode, terminal_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade.get("type"),
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
                     tpValue, slValue, broker_id, broker_name, platform,
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
                tpValue, slValue, broker_id, broker_name, platform,
                execution_mode, terminal_path
            )
            VALUES (?, 'open', ?, ?, ?, ?, ?, NULL, NULL, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
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
                trade.get("platform"),
                trade.get("execution_mode"),
                trade.get("terminal_path"),
            ),
        )


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
                       tpValue, slValue, broker_id, broker_name, platform,
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
                       tpValue, slValue, broker_id, broker_name, platform,
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


def get_open_trades_count():
    with get_db() as conn:
        row = conn.execute("SELECT COUNT(*) AS total FROM trade_history WHERE status = 'open'").fetchone()
    return int(row["total"]) if row else 0


def clear_trade_history():
    with get_db() as conn:
        conn.execute("DELETE FROM trade_history")


def log_mt5_error(message, broker_id=None, broker_name=None, timestamp=None):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO mt5_error_log (timestamp, message, broker_id, broker_name) VALUES (?, ?, ?, ?)",
            (int(timestamp or time.time()), message, broker_id, broker_name),
        )


def get_mt5_error_log(limit=500):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT timestamp, message, broker_id, broker_name FROM mt5_error_log ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
        return [
            {
                "timestamp": row["timestamp"],
                "message": row["message"],
                "broker_id": row["broker_id"],
                "broker_name": row["broker_name"],
            }
            for row in rows
        ]


def clear_mt5_error_log():
    with get_db() as conn:
        conn.execute("DELETE FROM mt5_error_log")


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
                       is_default, is_active, created_at, updated_at
                FROM brokers
                ORDER BY is_default DESC, name ASC
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, name, platform, terminal_path, execution_mode, window_hint,
                       is_default, is_active, created_at, updated_at
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
                   is_default, is_active, created_at, updated_at
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
                name, platform, terminal_path, execution_mode, window_hint,
                is_default, is_active, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 0, 1, ?, ?)
            """,
            (
                payload["name"],
                platform,
                payload.get("terminal_path"),
                execution_mode,
                payload.get("window_hint"),
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
        "is_active": int(bool(payload.get("is_active", current["is_active"]))),
        "updated_at": int(time.time()),
    }
    updated["execution_mode"] = _normalize_broker_execution_mode(updated["platform"], updated["execution_mode"])
    with get_db() as conn:
        conn.execute(
            """
            UPDATE brokers
            SET name = ?, platform = ?, terminal_path = ?, execution_mode = ?,
                window_hint = ?, is_active = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                updated["name"],
                updated["platform"],
                updated["terminal_path"],
                updated["execution_mode"],
                updated["window_hint"],
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
