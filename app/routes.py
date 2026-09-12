from __future__ import annotations

from fastapi import HTTPException

from app.db import get_trade_details


def get_trade_details_endpoint(trade_identifier: str):
    payload = get_trade_details(trade_identifier)
    if not payload:
        raise HTTPException(status_code=404, detail="Trade not found")
    return payload
