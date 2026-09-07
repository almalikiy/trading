from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TradeRecord:
    id: str
    symbol: str
    side: str
    quantity: float


@dataclass
class AccountRecord:
    id: str
    balance: float
