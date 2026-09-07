from fastapi import FastAPI

from trading_bot.app.api.routes.health import router as health_router
from trading_bot.app.api.routes.dashboard import router as dashboard_router
from trading_bot.app.api.routes.orders import router as orders_router
from trading_bot.app.api.routes.positions import router as positions_router
from trading_bot.app.api.routes.live_validation import router as live_validation_router
from trading_bot.infrastructure.config.settings import get_settings


app = FastAPI(title="Trading Bot API", version="0.1.0")
settings = get_settings()

app.include_router(health_router)
app.include_router(dashboard_router)
app.include_router(orders_router)
app.include_router(positions_router)
app.include_router(live_validation_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": settings.app_name, "status": "ok"}
