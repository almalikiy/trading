#!/usr/bin/env python3
"""Check whether SQLite trades marked as open still match live MT5 positions.

Usage examples:
  python scripts/check_open_trade_reconcile.py
  python scripts/check_open_trade_reconcile.py --symbol XAUUSD
  python scripts/check_open_trade_reconcile.py --broker-id 1 --json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:  # pragma: no cover - runtime environment dependency
    import MetaTrader5 as mt5
except Exception:  # pragma: no cover
    mt5 = None

DEFAULT_DB_PATH = ROOT / "trading_data.db"


def should_allow_sqlite_access(db_path: str | Path, *, allow_sqlite: bool = False) -> bool:
    if allow_sqlite:
        return True
    candidate = Path(db_path).resolve()
    default_path = DEFAULT_DB_PATH.resolve()
    return candidate != default_path


def normalize_symbol(value: Any) -> str:
    return str(value or "").strip().upper().replace("~", "")


def normalize_direction(value: Any) -> str | None:
    direction = str(value or "").strip().lower()
    if direction in {"buy", "long", "b"}:
        return "buy"
    if direction in {"sell", "short", "s"}:
        return "sell"
    return None


def connect_db(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def fetch_open_db_trades(db_path: str | Path, broker_id: int | None = None, symbol: str | None = None):
    query = "SELECT * FROM trade_history WHERE status = 'open'"
    params: list[Any] = []
    if broker_id is not None:
        query += " AND broker_id = ?"
        params.append(int(broker_id))
    if symbol:
        query += " AND UPPER(symbol) = ?"
        params.append(normalize_symbol(symbol))
    query += " ORDER BY entryTime ASC, id ASC"

    with connect_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def _mt5_positions(symbol: str | None = None):
    if mt5 is None:
        raise RuntimeError("MetaTrader5 package is not installed")

    try:
        initialized = mt5.initialize()
        if not initialized:
            raise RuntimeError(mt5.last_error() or "MT5 initialize() failed")
        positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        return positions or []
    except Exception:
        raise


def build_mt5_index(positions):
    by_ticket: dict[int, Any] = {}
    by_symbol_type: dict[tuple[str, str], list[Any]] = {}

    for pos in positions:
        symbol = normalize_symbol(getattr(pos, "symbol", ""))
        if not symbol:
            continue
        direction = None
        pos_type = getattr(pos, "type", None)
        if pos_type == getattr(mt5, "POSITION_TYPE_BUY", None):
            direction = "buy"
        elif pos_type == getattr(mt5, "POSITION_TYPE_SELL", None):
            direction = "sell"

        if direction is not None:
            by_symbol_type.setdefault((symbol, direction), []).append(pos)

        ticket = getattr(pos, "ticket", None)
        if ticket is not None:
            try:
                by_ticket[int(ticket)] = pos
            except (TypeError, ValueError):
                pass

    return by_ticket, by_symbol_type


def _match_db_row_to_mt5(row, by_ticket, by_symbol_type):
    ticket_value = row.get("ticket")
    symbol = normalize_symbol(row.get("symbol"))
    direction = normalize_direction(row.get("type"))
    lot = float(row.get("lot") or 0.0)

    if ticket_value not in (None, ""):
        try:
            mt5_match = by_ticket.get(int(ticket_value))
            if mt5_match is not None:
                return {
                    "matched": True,
                    "reason": "ticket",
                    "position": mt5_match,
                }
        except (TypeError, ValueError):
            pass

    if symbol and direction:
        candidates = by_symbol_type.get((symbol, direction), [])
        if candidates:
            best = None
            best_delta = None
            for candidate in candidates:
                candidate_lot = float(getattr(candidate, "volume", 0.0) or 0.0)
                delta = abs(candidate_lot - lot)
                if best is None or delta < best_delta:
                    best = candidate
                    best_delta = delta
            if best is not None:
                return {
                    "matched": True,
                    "reason": "symbol_direction",
                    "position": best,
                }

    return {"matched": False, "reason": "not_found", "position": None}


def summarize_position(pos):
    if pos is None:
        return None
    payload = {
        "ticket": getattr(pos, "ticket", None),
        "symbol": getattr(pos, "symbol", None),
        "type": "buy" if getattr(pos, "type", None) == getattr(mt5, "POSITION_TYPE_BUY", None) else "sell" if getattr(pos, "type", None) == getattr(mt5, "POSITION_TYPE_SELL", None) else None,
        "volume": getattr(pos, "volume", None),
        "price_open": getattr(pos, "price_open", None),
        "price_current": getattr(pos, "price_current", None),
        "profit": getattr(pos, "profit", None),
    }
    return payload


def reconcile_open_db_trades(db_path: str | Path = DEFAULT_DB_PATH, positions=None, apply: bool = True):
    db_path = Path(db_path)
    db_rows = fetch_open_db_trades(db_path)
    if positions is None:
        positions = []
        if mt5 is not None:
            try:
                positions = _mt5_positions()
            except Exception:
                positions = []

    by_ticket, by_symbol_type = build_mt5_index(positions)
    matches: list[dict[str, Any]] = []
    stale_rows: list[dict[str, Any]] = []

    for row in db_rows:
        result = _match_db_row_to_mt5(row, by_ticket, by_symbol_type)
        item = {
            "db_trade_id": row.get("trade_id"),
            "db_ticket": row.get("ticket"),
            "db_symbol": row.get("symbol"),
            "db_type": row.get("type"),
            "db_lot": row.get("lot"),
            "match_status": "matched" if result["matched"] else "stale_or_closed",
            "match_reason": result["reason"],
            "mt5_position": summarize_position(result["position"]),
        }
        if result["matched"]:
            matches.append(item)
        else:
            stale_rows.append(item)

    if apply:
        with connect_db(db_path) as conn:
            for item in stale_rows:
                trade_id = item["db_trade_id"]
                if not trade_id:
                    continue
                row = conn.execute(
                    "SELECT id, symbol, entry, exit, profit, entryTime, ticket, status FROM trade_history WHERE trade_id = ? AND status = 'open' ORDER BY id DESC LIMIT 1",
                    (trade_id,),
                ).fetchone()
                if row is None:
                    continue
                exit_value = row["exit"] if row["exit"] is not None else row["entry"]
                close_ts = int(time.time())
                if row["entryTime"]:
                    close_ts = int(row["entryTime"]) if int(row["entryTime"]) > 0 else close_ts
                conn.execute(
                    """
                    UPDATE trade_history
                    SET status = 'closed',
                        exit = COALESCE(?, exit),
                        profit = COALESCE(?, profit),
                        exitTime = COALESCE(?, exitTime),
                        reason = 'reconciled_closed_no_live_mt5'
                    WHERE trade_id = ? AND status = 'open'
                    """,
                    (exit_value, 0.0, close_ts, trade_id),
                )

    mt5_orphans = []
    matched_mt5_tickets = {int(getattr(v["mt5_position"], "get", lambda *_: 0)('ticket', 0) or 0) for v in matches if v["mt5_position"]}
    for pos in positions:
        ticket = getattr(pos, "ticket", None)
        try:
            ticket_int = int(ticket)
        except (TypeError, ValueError):
            continue
        if ticket_int in matched_mt5_tickets:
            continue
        mt5_orphans.append(summarize_position(pos))

    report = {
        "status": "ok" if not stale_rows and not mt5_orphans else "mismatch_detected",
        "db_open_trade_count": len(db_rows),
        "mt5_position_count": len(positions),
        "matches": matches,
        "stale_or_closed_in_db": stale_rows,
        "orphan_mt5_positions": mt5_orphans,
        "reconciled_count": len(stale_rows) if apply else 0,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to SQLite DB file (default: trading_data.db)")
    parser.add_argument("--broker-id", type=int, default=None, help="Filter to a specific broker_id")
    parser.add_argument("--symbol", default=None, help="Filter to a specific symbol")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a human-readable table")
    parser.add_argument("--no-apply", action="store_true", help="Only report stale rows without updating the database")
    parser.add_argument("--allow-sqlite", action="store_true", help="Explicitly allow legacy SQLite access for migration and troubleshooting only")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not should_allow_sqlite_access(db_path, allow_sqlite=args.allow_sqlite):
        print(
            "SQLite legacy access is disabled by default because the project is PostgreSQL-first. "
            "Re-run with --allow-sqlite only for migration or debugging.",
            file=sys.stderr,
        )
        return 2
    if not db_path.exists():
        print(f"ERROR: DB file not found: {db_path}")
        return 2

    db_rows = fetch_open_db_trades(db_path, broker_id=args.broker_id, symbol=args.symbol)
    if not db_rows:
        print("No trades in DB currently marked as 'open'.")
        return 0

    if mt5 is None:
        report = {
            "status": "mt5_unavailable",
            "db_open_trade_count": len(db_rows),
            "matches": [],
            "orphan_mt5_positions": [],
            "notes": ["MetaTrader5 package is not installed or not available in this environment."],
        }
        if args.json:
            print(json.dumps(report, indent=2, default=str))
        else:
            print("MetaTrader5 package is not available; unable to validate live positions.")
            print(f"DB open trades found: {len(db_rows)}")
            for row in db_rows:
                print(f"- ticket={row.get('ticket')} symbol={row.get('symbol')} type={row.get('type')} lot={row.get('lot')}")
        return 0

    try:
        positions = _mt5_positions(symbol=args.symbol)
    except Exception as exc:
        report = {
            "status": "mt5_connect_failed",
            "db_open_trade_count": len(db_rows),
            "matches": [],
            "orphan_mt5_positions": [],
            "notes": [str(exc)],
        }
        if args.json:
            print(json.dumps(report, indent=2, default=str))
        else:
            print(f"MT5 live validation failed: {exc}")
            print(f"DB open trades found: {len(db_rows)}")
            for row in db_rows:
                print(f"- ticket={row.get('ticket')} symbol={row.get('symbol')} type={row.get('type')} lot={row.get('lot')}")
        return 0

    report = reconcile_open_db_trades(db_path, positions=positions, apply=not args.no_apply)
    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0

    print(f"DB open trades: {len(db_rows)} | MT5 live positions: {len(positions)}")
    print("")
    if report["stale_or_closed_in_db"]:
        action = "reconciled" if not args.no_apply and report["reconciled_count"] else "identified"
        print(f"STALE / CLOSED IN DB ({action}):")
        for item in report["stale_or_closed_in_db"]:
            print(
                f"- trade_id={item['db_trade_id']} ticket={item['db_ticket']} "
                f"symbol={item['db_symbol']} type={item['db_type']} lot={item['db_lot']} -> no matching live MT5 position"
            )
    else:
        print("All DB open trades still have a live MT5 match.")

    if report["orphan_mt5_positions"]:
        print("")
        print("ORPHAN MT5 POSITIONS (open in broker but missing in DB):")
        for item in report["orphan_mt5_positions"]:
            print(
                f"- ticket={item['ticket']} symbol={item['symbol']} type={item['type']} "
                f"volume={item['volume']} price_open={item['price_open']}"
            )

    if not report["stale_or_closed_in_db"] and not report["orphan_mt5_positions"]:
        print("")
        print("No reconciliation gaps found between DB and live MT5 positions.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
