from __future__ import annotations

from decimal import Decimal


class RiskService:
    def validate(self, symbol: str, risk_pct: Decimal | float, max_risk_pct: Decimal | float) -> bool:
        current = Decimal(str(risk_pct))
        limit = Decimal(str(max_risk_pct))
        return current <= limit
