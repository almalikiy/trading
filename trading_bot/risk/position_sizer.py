from __future__ import annotations

from decimal import Decimal


class PositionSizer:
    def calculate_lot(self, account_balance: Decimal | float, risk_pct: Decimal | float, stop_distance: Decimal | float) -> Decimal:
        balance = Decimal(str(account_balance))
        risk = Decimal(str(risk_pct)) / Decimal("100")
        distance = Decimal(str(stop_distance))
        if distance <= 0:
            return Decimal("0")
        return (balance * risk) / distance
