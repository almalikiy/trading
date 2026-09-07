from __future__ import annotations

from decimal import Decimal


class PnLGuard:
    def __init__(self, max_drawdown_pct: Decimal | float = 5.0) -> None:
        self.max_drawdown_pct = Decimal(str(max_drawdown_pct))

    def should_block(self, drawdown_pct: Decimal | float) -> bool:
        return Decimal(str(drawdown_pct)) >= self.max_drawdown_pct
