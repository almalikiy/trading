from __future__ import annotations

from typing import Any

from trading_bot.adapters.brokers.broker_factory import BrokerFactory
from trading_bot.core.application.execution_service import ExecutionService
from trading_bot.core.application.orchestration_service import OrchestrationService
from trading_bot.core.application.risk_service import RiskService
from trading_bot.core.application.signal_service import SignalService


class BrokerOrchestrator:
    def __init__(self, broker_name: str) -> None:
        self.broker = BrokerFactory.create(broker_name)
        self.executer = ExecutionService(self.broker)
        self.signal_service = SignalService()
        self.risk_service = RiskService()
        self.orchestrator = OrchestrationService(
            signal_service=self.signal_service,
            risk_service=self.risk_service,
            execution_service=self.executer,
        )

    async def handle_signal(self, symbol: str, direction: str, risk_pct: float, max_risk_pct: float, request: Any) -> dict[str, Any]:
        return await self.orchestrator.handle_signal(symbol, direction, risk_pct, max_risk_pct, request)
