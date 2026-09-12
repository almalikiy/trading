from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from trading_bot.app.api.deps import get_broker_orchestrator
from trading_bot.app.persistence.broker_store import list_brokers
from trading_bot.core.application.production_guard_service import ProductionGuardService
from trading_bot.core.domain.enums import OrderSide, OrderType
from trading_bot.core.domain.models import OrderRequest
from trading_bot.infrastructure.config.settings import get_settings

router = APIRouter(prefix="/orders", tags=["orders"])


class OrderPayload(BaseModel):
    symbol: str = Field(..., min_length=1, description="Trading symbol, e.g. XAUUSD, BTCUSDT, or other user-selected pair")
    side: str = Field(..., description="BUY or SELL")
    volume: Decimal = Field(..., gt=0)
    order_type: str = Field(default="MARKET")
    broker: str = Field(..., min_length=1, description="Broker identifier, e.g. mt5, binance, or stockbit")
    client_order_id: str | None = None
    max_lot: Decimal | None = Field(default=None, gt=0)
    max_daily_loss_pct: Decimal | None = Field(default=None, gt=0)
    max_drawdown_pct: Decimal | None = Field(default=None, gt=0)
    current_drawdown_pct: Decimal | None = Field(default=None, ge=0)
    min_margin_buffer_pct: Decimal | None = Field(default=None, gt=0)
    daily_loss_pct: Decimal | None = Field(default=None)
    max_open_positions: int | None = Field(default=None, ge=0)
    kill_switch_enabled: bool | None = Field(default=None, description="Override global kill switch for a specific order request")


@router.get("")
async def list_orders() -> list[dict[str, object]]:
    try:
        brokers = list_brokers(include_inactive=True)
        return [
            {
                "broker": broker.get("name") or broker.get("platform") or "unknown",
                "platform": broker.get("platform") or "unknown",
                "symbol": broker.get("default_symbol") or "XAUUSD",
                "execution_mode": broker.get("execution_mode") or "mouse",
                "is_active": bool(broker.get("is_active")),
                "status": "ready" if broker.get("is_active") else "inactive",
            }
            for broker in brokers
        ]
    except Exception:
        return []


@router.post("")
async def create_order(payload: OrderPayload) -> dict[str, object]:
    settings = get_settings()
    guard = ProductionGuardService(
        max_lot=payload.max_lot if payload.max_lot is not None else settings.max_lot,
        max_daily_loss_pct=payload.max_daily_loss_pct if payload.max_daily_loss_pct is not None else settings.max_daily_loss_pct,
        max_drawdown_pct=payload.max_drawdown_pct if payload.max_drawdown_pct is not None else settings.max_drawdown_pct,
        min_margin_buffer_pct=payload.min_margin_buffer_pct if payload.min_margin_buffer_pct is not None else settings.min_margin_buffer_pct,
        max_open_positions=payload.max_open_positions if payload.max_open_positions is not None else settings.max_open_positions,
        kill_switch_enabled=(payload.kill_switch_enabled if payload.kill_switch_enabled is not None else settings.kill_switch_enabled),
    )

    validation = await guard.validate_order_request(
        broker_name=payload.broker,
        symbol=payload.symbol,
        side=payload.side,
        volume=payload.volume,
        max_lot=payload.max_lot if payload.max_lot is not None else settings.max_lot,
        max_daily_loss_pct=payload.max_daily_loss_pct if payload.max_daily_loss_pct is not None else settings.max_daily_loss_pct,
        max_drawdown_pct=payload.max_drawdown_pct if payload.max_drawdown_pct is not None else settings.max_drawdown_pct,
        current_drawdown_pct=payload.current_drawdown_pct,
        min_margin_buffer_pct=payload.min_margin_buffer_pct if payload.min_margin_buffer_pct is not None else settings.min_margin_buffer_pct,
        daily_loss_pct=payload.daily_loss_pct,
        max_open_positions=(payload.max_open_positions if payload.max_open_positions is not None else settings.max_open_positions),
        kill_switch_enabled=(payload.kill_switch_enabled if payload.kill_switch_enabled is not None else settings.kill_switch_enabled),
    )

    if not validation["allowed"]:
        raise HTTPException(status_code=400, detail={
            "allowed": False,
            "broker": validation["broker"],
            "symbol": validation["symbol"],
            "errors": validation["errors"],
            "alerts": validation["alerts"],
            "risk": validation["risk"],
        })

    orchestrator = get_broker_orchestrator(payload.broker)
    request = OrderRequest(
        symbol=payload.symbol,
        side=OrderSide[payload.side.upper()],
        order_type=OrderType[payload.order_type.upper()],
        volume=payload.volume,
        client_order_id=payload.client_order_id,
    )
    result = await orchestrator.handle_signal(
        symbol=payload.symbol,
        direction=payload.side.upper(),
        risk_pct=0.5,
        max_risk_pct=2.0,
        request=request,
    )
    return result
