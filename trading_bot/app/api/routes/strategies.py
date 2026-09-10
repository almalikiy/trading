from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from trading_bot.strategies.manager import strategy_manager

router = APIRouter(prefix="/strategies", tags=["strategies"])


class StrategySwitchRequest(BaseModel):
    name: str = Field(..., min_length=1)
    parameters: dict[str, Any] | None = None


@router.get("/list")
async def list_strategies() -> dict[str, Any]:
    return {
        "status": "ok",
        "strategies": strategy_manager.list_strategies(),
    }


@router.get("/active")
async def get_active_strategy() -> dict[str, Any]:
    return strategy_manager.get_active_strategy()


@router.post("/switch")
async def switch_strategy(payload: StrategySwitchRequest) -> dict[str, Any]:
    try:
        result = strategy_manager.switch_strategy(payload.name, payload.parameters)
        return result
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
