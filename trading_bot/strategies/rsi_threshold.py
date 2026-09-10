from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .base import BaseStrategy
from .registry import register_strategy


class RsiThresholdParameters(BaseModel):
    rsi_period: int = Field(default=14, ge=2, le=200)
    overbought: float = Field(default=70.0, gt=50.0, le=100.0)
    oversold: float = Field(default=30.0, ge=0.0, lt=50.0)


@register_strategy("rsi_threshold")
class RsiThresholdStrategy(BaseStrategy):
    name = "rsi_threshold"
    parameters_model = RsiThresholdParameters

    def analyze(self, ohlcv_data: list[dict[str, Any]]) -> dict[str, Any]:
        if len(ohlcv_data) < max(2, int(self.parameters.get("rsi_period", 14))):
            return {
                "signal": "hold",
                "confidence": 0.0,
                "rsi": None,
            }

        closes = [float(candle.get("close", 0.0)) for candle in ohlcv_data if candle.get("close") is not None]
        period = int(self.parameters.get("rsi_period", 14))
        gains: list[float] = []
        losses: list[float] = []

        for previous, current in zip(closes, closes[1:]):
            delta = current - previous
            gains.append(max(delta, 0.0))
            losses.append(max(-delta, 0.0))

        if len(gains) < period:
            return {
                "signal": "hold",
                "confidence": 0.0,
                "rsi": None,
            }

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))

        overbought = float(self.parameters.get("overbought", 70.0))
        oversold = float(self.parameters.get("oversold", 30.0))

        if rsi >= overbought:
            signal = "sell"
        elif rsi <= oversold:
            signal = "buy"
        else:
            signal = "hold"

        confidence = min(1.0, abs(rsi - ((overbought + oversold) / 2.0)) / max(abs(overbought - oversold), 1.0))
        return {
            "signal": signal,
            "confidence": round(float(confidence), 4),
            "rsi": round(float(rsi), 4),
            "parameters": self.get_parameters(),
        }
