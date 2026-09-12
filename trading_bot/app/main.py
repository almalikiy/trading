# file : trading_bot/app/main.py
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from trading_bot.app.api.routes.account import router as account_router
from trading_bot.app.api.routes.brokers import router as brokers_router
from trading_bot.app.api.routes.dashboard import router as dashboard_router
from trading_bot.app.api.routes.health import router as health_router
from trading_bot.app.api.routes.live_validation import router as live_validation_router
from trading_bot.app.api.routes.market_data import router as market_data_router
from trading_bot.app.api.routes.mt5 import router as mt5_router
from trading_bot.app.api.routes.orders import router as orders_router
from trading_bot.app.api.routes.positions import legacy_router as positions_legacy_router
from trading_bot.app.api.routes.positions import router as positions_router
from trading_bot.app.api.routes.strategies import router as strategies_router
from trading_bot.infrastructure.config.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Trading Bot API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://trading.almalikiy.net",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8050",
            "http://127.0.0.1:8050",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "*",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def startup_event() -> None:
        try:
            from trading_bot.app.bootstrap import bootstrap

            bootstrap()
        except Exception:
            pass

    app.include_router(account_router)
    app.include_router(health_router)
    app.include_router(brokers_router)
    app.include_router(dashboard_router)
    app.include_router(orders_router)
    app.include_router(positions_router)
    app.include_router(positions_legacy_router)
    app.include_router(mt5_router)
    app.include_router(live_validation_router)
    app.include_router(market_data_router)
    app.include_router(strategies_router)

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"service": settings.app_name, "status": "ok"}

    return app


app = create_app()

__all__ = ["app", "create_app"]
