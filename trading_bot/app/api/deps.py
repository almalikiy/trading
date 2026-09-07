from __future__ import annotations

from typing import Any

from trading_bot.adapters.persistence.state_repository import StateRepository
from trading_bot.core.application.broker_orchestrator import BrokerOrchestrator


_runtime_state = StateRepository()


def get_runtime_context() -> dict[str, Any]:
    return {"context": "trading-bot"}


def get_state_repository() -> StateRepository:
    return _runtime_state


def get_broker_orchestrator(broker_name: str) -> BrokerOrchestrator:
    broker_name = str(broker_name or "").strip()
    if not broker_name:
        raise ValueError("broker_name is required and must be provided at runtime")
    return BrokerOrchestrator(broker_name)
