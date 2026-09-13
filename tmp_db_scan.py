import os

if not os.environ.get("ALLOW_SQLITE_SCAN"):
    raise SystemExit("Legacy SQLite scanning is disabled by default. Set ALLOW_SQLITE_SCAN=1 only for one-off diagnostics.")

import sqlite3

root = r'D:\development\trading'
for db in ['account_state.db', 'trading_data.db']:
    p = os.path.join(root, db)
    print('DB', db, 'exists=', os.path.exists(p))
    if not os.path.exists(p):
        continue
    con = sqlite3.connect(p)
    try:
        tables = con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        print('TABLES', [t[0] for t in tables])
        for table in ['brokers', 'account_state', 'settings', 'broker_config', 'broker_credentials', 'broker_info', 'mt5_settings']:
            try:
                cols = con.execute(f'PRAGMA table_info({table})').fetchall()
                if not cols:
                    continue
                print('TABLE', table, 'COLS', [c[1] for c in cols])
                rows = con.execute(f'SELECT * FROM {table} LIMIT 5').fetchall()
                print('ROWS', rows)
            except Exception as e:
                print('skip', table, type(e).__name__, e)
    finally:
        con.close()
