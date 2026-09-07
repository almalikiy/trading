from __future__ import annotations

from typing import Any


class OrchestrationService:
    def __init__(self, signal_service: Any, risk_service: Any, execution_service: Any) -> None:
        self.signal_service = signal_service
        self.risk_service = risk_service
        self.execution_service = execution_service

    async def handle_signal(
        self,
        symbol: str,
        direction: str,
        risk_pct: float,
        max_risk_pct: float,
        request: Any,
    ) -> dict[str, Any]:
        signal = self.signal_service.generate(symbol=symbol, direction=direction, confidence=0.8)
        approved = self.risk_service.validate(symbol, risk_pct, max_risk_pct)
        if not approved:
            return {
                "approved": False,
                "signal": signal,
                "reason": "risk_limit_exceeded",
            }

        order = await self.execution_service.execute(request)
        return {
            "approved": True,
            "signal": signal,
            "order": order,
        }
