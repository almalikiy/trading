from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Signal:
    symbol: str
    direction: str
    confidence: float = 0.0
    metadata: dict[str, Any] | None = None


class SignalService:
    def generate(self, symbol: str, direction: str, confidence: float = 0.0, **metadata: Any) -> Signal:
        return Signal(symbol=symbol, direction=direction, confidence=confidence, metadata=metadata)
