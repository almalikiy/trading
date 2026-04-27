import sqlite3
from contextlib import contextmanager

DB_PATH = 'trading_data.db'

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.commit()
        conn.close()

def init_db():
    with get_db() as conn:
        # Account state
        conn.execute('''
            CREATE TABLE IF NOT EXISTS account_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                balance REAL DEFAULT 1000,
                enable_real_trade BOOLEAN DEFAULT 0,
                auto_analytic_tpsl BOOLEAN DEFAULT 0,
                tp_value REAL DEFAULT 0.5,
                sl_value REAL
            )
        ''')
        cur = conn.execute('SELECT COUNT(*) FROM account_state')
        if cur.fetchone()[0] == 0:
            conn.execute('INSERT INTO account_state (id) VALUES (1)')

        # Trade history
        conn.execute('''
            CREATE TABLE IF NOT EXISTS trade_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT,
                entry REAL,
                exit REAL,
                profit REAL,
                entryTime INTEGER,
                exitTime INTEGER,
                reason TEXT,
                tpValue REAL,
                slValue REAL
            )
        ''')

        # MT5 error log
        conn.execute('''
            CREATE TABLE IF NOT EXISTS mt5_error_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER,
                message TEXT
            )
        ''')
def get_trade_history():
    with get_db() as conn:
        rows = conn.execute('SELECT type, entry, exit, profit, entryTime, exitTime, reason, tpValue, slValue FROM trade_history ORDER BY entryTime ASC').fetchall()
        return [
            {
                "type": row[0],
                "entry": row[1],
                "exit": row[2],
                "profit": row[3],
                "entryTime": row[4],
                "exitTime": row[5],
                "reason": row[6],
                "tpValue": row[7],
                "slValue": row[8],
            }
            for row in rows
        ]

def append_trade_history(trade):
    with get_db() as conn:
        conn.execute('''
            INSERT INTO trade_history (type, entry, exit, profit, entryTime, exitTime, reason, tpValue, slValue)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade.get("type"),
            trade.get("entry"),
            trade.get("exit"),
            trade.get("profit"),
            trade.get("entryTime"),
            trade.get("exitTime"),
            trade.get("reason"),
            trade.get("tpValue"),
            trade.get("slValue"),
        ))

def clear_trade_history():
    with get_db() as conn:
        conn.execute('DELETE FROM trade_history')

def get_mt5_error_log():
    with get_db() as conn:
        rows = conn.execute('SELECT timestamp, message FROM mt5_error_log ORDER BY timestamp DESC').fetchall()
        return [
            {"timestamp": row[0], "message": row[1]} for row in rows
        ]

def log_mt5_error(message):
    import time
    with get_db() as conn:
        conn.execute('INSERT INTO mt5_error_log (timestamp, message) VALUES (?, ?)', (int(time.time()), message))

def clear_mt5_error_log():
    with get_db() as conn:
        conn.execute('DELETE FROM mt5_error_log')

def get_account_state():
    with get_db() as conn:
        row = conn.execute('SELECT balance, enable_real_trade, auto_analytic_tpsl, tp_value, sl_value FROM account_state WHERE id=1').fetchone()
        if not row:
            return {"balance": 1000, "enable_real_trade": False, "auto_analytic_tpsl": False, "tp_value": 0.5, "sl_value": None}
        return {
            "balance": row[0],
            "enable_real_trade": bool(row[1]),
            "auto_analytic_tpsl": bool(row[2]),
            "tp_value": row[3],
            "sl_value": row[4]
        }

def save_account_state(state):
    with get_db() as conn:
        conn.execute('''
            INSERT INTO account_state (id, balance, enable_real_trade, auto_analytic_tpsl, tp_value, sl_value)
            VALUES (1, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                balance = excluded.balance,
                enable_real_trade = excluded.enable_real_trade,
                auto_analytic_tpsl = excluded.auto_analytic_tpsl,
                tp_value = excluded.tp_value,
                sl_value = excluded.sl_value
        ''', (
            state.get("balance", 1000),
            int(bool(state.get("enable_real_trade", False))),
            int(bool(state.get("auto_analytic_tpsl", False))),
            state.get("tp_value", 0.5),
            state.get("sl_value", None)
        ))
        print("Saving state:", state)


