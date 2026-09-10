from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from trading_bot.core.application.production_guard_service import ProductionGuardService

router = APIRouter(prefix="/live-validation", tags=["live-validation"])


class LiveValidationPayload(BaseModel):
    broker: str = Field(..., min_length=1, description="Broker id such as mt5, binance, stockbit")
    symbol: str = Field(..., min_length=1, description="Trading symbol selected by user, e.g. XAUUSD")
    side: str = Field(..., description="BUY or SELL")
    volume: Decimal = Field(..., gt=0, description="Requested lot/volume")
    max_lot: Decimal | None = Field(default=None, gt=0, description="Operational cap for this validation")
    max_daily_loss_pct: Decimal | None = Field(default=None, gt=0, description="Daily loss cap in percent")
    max_drawdown_pct: Decimal | None = Field(default=None, gt=0, description="Drawdown cap in percent")
    current_drawdown_pct: Decimal | None = Field(default=None, ge=0, description="Current portfolio drawdown percent")
    min_margin_buffer_pct: Decimal | None = Field(default=None, gt=0, description="Minimum margin buffer in percent")
    daily_loss_pct: Decimal | None = Field(default=None, description="Current realized daily loss percent")
    max_open_positions: int | None = Field(default=None, ge=0, description="Current open positions cap")
    kill_switch_enabled: bool | None = Field(default=None, description="Override current kill-switch state for this validation")


@router.post("")
async def validate_live_broker(payload: LiveValidationPayload) -> dict[str, object]:
    guard = ProductionGuardService()
    result = await guard.validate_order_request(
        broker_name=payload.broker,
        symbol=payload.symbol,
        side=payload.side,
        volume=payload.volume,
        max_lot=payload.max_lot,
        max_daily_loss_pct=payload.max_daily_loss_pct,
        max_drawdown_pct=payload.max_drawdown_pct,
        current_drawdown_pct=payload.current_drawdown_pct,
        min_margin_buffer_pct=payload.min_margin_buffer_pct,
        daily_loss_pct=payload.daily_loss_pct,
        max_open_positions=payload.max_open_positions,
        kill_switch_enabled=payload.kill_switch_enabled,
    )

    if not result["allowed"]:
        raise HTTPException(status_code=400, detail={
            "allowed": False,
            "broker": result["broker"],
            "symbol": result["symbol"],
            "errors": result["errors"],
            "alerts": result["alerts"],
            "risk": result["risk"],
        })

    return {
        "allowed": True,
        "broker": result["broker"],
        "symbol": result["symbol"],
        "errors": [],
        "alerts": result["alerts"],
        "risk": result["risk"],
        "message": "broker is ready for manual live testing with user-specified symbol and broker",
    }
