from __future__ import annotations


class PortfolioService:
    def __init__(self) -> None:
        self.positions: list[str] = []

    def add_position(self, symbol: str) -> None:
        if symbol not in self.positions:
            self.positions.append(symbol)
