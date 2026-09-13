from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from trading_bot.infrastructure.config.settings import get_settings
from trading_bot.infrastructure.database.postgres_bootstrap import database_status, reset_database_for_clean_start

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/database")
async def database_health() -> dict[str, Any]:
    settings = get_settings()
    payload = database_status(settings)
    payload.update({
        "database_backend": settings.database_backend,
        "postgres_enabled": settings.postgres_enabled,
    })
    return payload


@router.post("/database/reset")
async def reset_database() -> dict[str, Any]:
    settings = get_settings()
    return reset_database_for_clean_start(settings, preserve_broker_data_only=settings.preserve_broker_data_only)
