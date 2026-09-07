from __future__ import annotations

from decimal import Decimal


class Money:
    def __init__(self, amount: Decimal | str | int) -> None:
        self.amount = Decimal(str(amount))

    def __str__(self) -> str:
        return str(self.amount)


class Price:
    def __init__(self, value: Decimal | str | int) -> None:
        self.value = Decimal(str(value))

    def __str__(self) -> str:
        return str(self.value)


class LotSize:
    def __init__(self, value: Decimal | str | int) -> None:
        self.value = Decimal(str(value))

    def __str__(self) -> str:
        return str(self.value)


class Symbol:
    def __init__(self, value: str) -> None:
        self.value = value.upper()

    def __str__(self) -> str:
        return self.value


__all__ = ["Money", "Price", "LotSize", "Symbol"]
