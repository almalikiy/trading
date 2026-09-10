from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from .base import BaseStrategy
from .registry import register_strategy


class MovingAverageCrossParameters(BaseModel):
    fast_period: int = Field(default=10, ge=2, le=200)
    slow_period: int = Field(default=30, ge=3, le=400)

    @model_validator(mode="after")
    def validate_periods(self) -> "MovingAverageCrossParameters":
        if self.fast_period >= self.slow_period:
            raise ValueError("fast_period must be smaller than slow_period.")
        return self


@register_strategy("moving_average_cross")
class MovingAverageCrossStrategy(BaseStrategy):
    name = "moving_average_cross"
    parameters_model = MovingAverageCrossParameters

    def initialize(self, parameters: dict[str, Any] | BaseModel | None = None) -> None:
        super().initialize(parameters)

    def analyze(self, ohlcv_data: list[dict[str, Any]]) -> dict[str, Any]:
        if not ohlcv_data:
            return {
                "signal": "hold",
                "confidence": 0.0,
                "fast_ma": None,
                "slow_ma": None,
            }

        closes = [float(candle.get("close", 0.0)) for candle in ohlcv_data if candle.get("close") is not None]
        if len(closes) < max(self.parameters["fast_period"], self.parameters["slow_period"]):
            return {
                "signal": "hold",
                "confidence": 0.0,
                "fast_ma": None,
                "slow_ma": None,
            }

        fast_period = int(self.parameters.get("fast_period", 10))
        slow_period = int(self.parameters.get("slow_period", 30))

        fast_values = closes[-fast_period:]
        slow_values = closes[-slow_period:]
        fast_ma = sum(fast_values) / len(fast_values)
        slow_ma = sum(slow_values) / len(slow_values)

        if fast_ma > slow_ma:
            signal = "buy"
        elif fast_ma < slow_ma:
            signal = "sell"
        else:
            signal = "hold"

        confidence = min(1.0, abs(fast_ma - slow_ma) / max(abs(slow_ma), 1e-6))
        return {
            "signal": signal,
            "confidence": round(float(confidence), 4),
            "fast_ma": round(float(fast_ma), 5),
            "slow_ma": round(float(slow_ma), 5),
            "parameters": self.get_parameters(),
        }
