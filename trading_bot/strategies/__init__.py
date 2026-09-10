"""Strategy registry, base contract, and concrete strategy implementations."""

from .base import BaseStrategy
from .base import StrategyRegistry, get_strategy_registry, list_strategy_names, register_strategy
from .manager import strategy_manager

# Import concrete strategies so they self-register at package import time.
from .moving_average_cross import MovingAverageCrossStrategy  # noqa: F401
from .rsi_threshold import RsiThresholdStrategy  # noqa: F401

__all__ = [
    "BaseStrategy",
    "StrategyRegistry",
    "register_strategy",
    "get_strategy_registry",
    "list_strategy_names",
    "strategy_manager",
    "MovingAverageCrossStrategy",
    "RsiThresholdStrategy",
]
