from __future__ import annotations

from typing import Type

from .base_strategy import BaseStrategy
from .breakout import BreakoutStrategy
from .mean_reversion import MeanReversionStrategy
from .multi_tf_confirmation import MultiTimeframeConfirmationStrategy
from .trend_following import TrendFollowingStrategy


def get_strategy_registry() -> dict[str, Type[BaseStrategy]]:
    return {
        "trend_following": TrendFollowingStrategy,
        "mean_reversion": MeanReversionStrategy,
        "breakout": BreakoutStrategy,
        "multi_tf_confirmation": MultiTimeframeConfirmationStrategy,
    }
