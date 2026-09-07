from __future__ import annotations

from decimal import Decimal


class RiskEngine:
    def __init__(self, max_daily_loss_pct: Decimal | float = 2.0) -> None:
        self.max_daily_loss_pct = Decimal(str(max_daily_loss_pct))

    def is_within_limits(self, daily_loss_pct: Decimal | float) -> bool:
        return Decimal(str(daily_loss_pct)) <= self.max_daily_loss_pct
