from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Body

from trading_bot.adapters.brokers.broker_factory import BrokerFactory
from trading_bot.app import db
from trading_bot.app.persistence.trade_store import get_open_trades_count, get_trade_history
from trading_bot.app.terminal_adapters import sync_trade_state_for_history_flow_in_background


def sync_trade_state_for_history_flow(*args, **kwargs):
    return sync_trade_state_for_history_flow_in_background(*args, **kwargs)
from trading_bot.core.domain.models import Position

router = APIRouter(prefix="/positions", tags=["positions"])

legacy_router = APIRouter(prefix="/trade", tags=["trade-compat"])


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, Decimal):
            return float(value)
        return float(value or default)
    except Exception:
        return default


def _to_timestamp(value: Any) -> int | None:
    if isinstance(value, datetime):
        try:
            return int(value.timestamp())
        except Exception:
            return None
    return None


def _normalize_position(position: Position | dict[str, Any], broker_name: str) -> dict[str, Any]:
    if isinstance(position, Position):
        side = getattr(position.side, "value", str(position.side)).upper()
        return {
            "broker": broker_name,
            "broker_name": broker_name,
            "symbol": position.symbol,
            "type": side,
            "lot": _to_float(position.volume),
            "entry": _to_float(position.entry_price),
            "entry_price": _to_float(position.entry_price),
            "price": _to_float(position.mark_price),
            "last_price": _to_float(position.mark_price),
            "profit": _to_float(position.pnl),
            "status": "open",
            "entryTime": _to_timestamp(position.open_time),
        }

    row = position if isinstance(position, dict) else {}
    return {
        "broker": row.get("broker", broker_name),
        "broker_name": row.get("broker_name", row.get("broker", broker_name)),
        "symbol": row.get("symbol", "-"),
        "type": str(row.get("type", row.get("side", "-"))).upper(),
        "lot": _to_float(row.get("lot", row.get("volume", 0.0))),
        "entry": _to_float(row.get("entry", row.get("entry_price", 0.0))),
        "entry_price": _to_float(row.get("entry_price", row.get("entry", 0.0))),
        "price": _to_float(row.get("price", row.get("last_price", row.get("mark_price", 0.0)))),
        "last_price": _to_float(row.get("last_price", row.get("price", row.get("mark_price", 0.0)))),
        "profit": _to_float(row.get("profit", row.get("pnl", 0.0))),
        "status": str(row.get("status", "open")),
        "entryTime": row.get("entryTime") if isinstance(row.get("entryTime"), int) else None,
    }


async def _fetch_positions() -> list[dict[str, Any]]:
    broker = BrokerFactory.create("mt5")
    try:
        if hasattr(broker, "connected") and not bool(getattr(broker, "connected", False)):
            await broker.connect()
    except Exception:
        return []

    try:
        positions = await broker.get_positions()
    except Exception:
        return []

    rows = positions if isinstance(positions, list) else []
    return [_normalize_position(item, getattr(broker, "name", "mt5")) for item in rows]


def _normalize_trade_history_item(item: dict[str, Any]) -> dict[str, Any]:
    row = item if isinstance(item, dict) else {}
    return {
        "symbol": row.get("symbol", "-"),
        "type": str(row.get("type", row.get("side", "-"))).lower(),
        "entry": _to_float(row.get("entry", row.get("entry_price", 0.0))),
        "exit": _to_float(row.get("exit", row.get("exit_price", 0.0))),
        "lot": _to_float(row.get("lot", row.get("volume", 0.0))),
        "profit": _to_float(row.get("profit", row.get("pnl", 0.0))),
        "status": str(row.get("status", "closed")),
        "reason": str(row.get("reason", "-")),
    }


@router.get("")
async def list_positions() -> list[dict[str, object]]:
    rows = await _fetch_positions()
    return [{"broker": "mt5", "positions": rows}]


@legacy_router.get("/open_positions")
async def list_open_positions_compat() -> list[dict[str, Any]]:
    sync_trade_state_for_history_flow_in_background(timeout_sec=0.75)
    rows = db.list_open_trades()
    return [_normalize_position(item, str(item.get("broker_name") or item.get("broker") or "mt5")) for item in rows]


@legacy_router.get("/open_count")
async def open_positions_count_compat() -> dict[str, int]:
    sync_trade_state_for_history_flow_in_background(timeout_sec=0.75)
    try:
        count = int(get_open_trades_count())
    except Exception:
        count = 0
    safe_count = max(0, count)
    return {"count": safe_count, "open_count": safe_count}


@legacy_router.get("/history")
async def trade_history_compat() -> list[dict[str, Any]]:
    sync_trade_state_for_history_flow_in_background(timeout_sec=0.75)
    try:
        rows = get_trade_history()
    except Exception:
        rows = []

    if not isinstance(rows, list):
        return []
    return [_normalize_trade_history_item(item) for item in rows]


@legacy_router.get("/{trade_identifier}/details")
async def trade_details_compat(trade_identifier: str) -> dict[str, Any]:
    row = db.get_trade_details(str(trade_identifier))
    if not row:
        return {"status": "error", "message": "Trade not found"}
    return {"status": "ok", "trade": row, "details": row}


@legacy_router.post("/update_tpsl")
async def update_tpsl_compat(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    ticket = payload.get("ticket")
    if ticket is None:
        return {"status": "error", "message": "ticket is required"}

    existing = db.get_trade_details(str(ticket))
    if not existing:
        return {"status": "error", "message": "Trade not found"}

    updated = dict(existing)
    for key in ("symbol", "type", "entry_price", "tp", "sl"):
        if key in payload and payload.get(key) is not None:
            updated[key] = payload.get(key)

    db.upsert_trade_history_record(updated)
    row = db.get_trade_details(str(ticket)) or updated
    return {"status": "ok", "message": "TP/SL updated", "trade": row}
