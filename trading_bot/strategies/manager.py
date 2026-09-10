from __future__ import annotations

import threading
from typing import Any

from .base import BaseStrategy
from .registry import get_strategy_registry


class StrategyManager:
    """Service object that owns the currently active strategy instance."""

    def __init__(self) -> None:
        self.registry = get_strategy_registry()
        self._active_name: str | None = None
        self._active_strategy: BaseStrategy | None = None
        self._lock = threading.RLock()

    def _default_strategy_name(self) -> str | None:
        names = sorted(self.registry.available())
        return names[0] if names else None

    def list_strategies(self) -> list[dict[str, Any]]:
        with self._lock:
            strategies: list[dict[str, Any]] = []
            for name, strategy_cls in sorted(self.registry.available().items()):
                strategy_instance = strategy_cls()
                strategies.append(
                    {
                        "name": name,
                        "class": strategy_cls.__name__,
                        "parameters_schema": strategy_instance.get_parameters_schema(),
                        "default_parameters": strategy_instance.get_parameters(),
                    }
                )
            return strategies

    def get_active_strategy(self) -> dict[str, Any]:
        with self._lock:
            if self._active_strategy is None:
                default_name = self._default_strategy_name()
                if default_name is None:
                    return {"status": "empty", "strategy": None, "state": {"initialized": False}}
                self.switch_strategy(default_name)

            assert self._active_strategy is not None
            return {
                "status": "ok",
                "strategy": {
                    "name": self._active_name,
                    "class": self._active_strategy.__class__.__name__,
                    "parameters": self._active_strategy.get_parameters(),
                    "parameters_schema": self._active_strategy.get_parameters_schema(),
                },
                "state": {
                    "initialized": True,
                    "active": True,
                },
            }

    def switch_strategy(self, strategy_name: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            strategy_cls = self.registry.get(strategy_name)
            if strategy_cls is None:
                raise KeyError(f"Unknown strategy '{strategy_name}'.")

            strategy_instance = strategy_cls(parameters or {})
            self._active_name = strategy_name
            self._active_strategy = strategy_instance

            return {
                "status": "ok",
                "strategy": {
                    "name": strategy_name,
                    "class": strategy_instance.__class__.__name__,
                    "parameters": strategy_instance.get_parameters(),
                    "parameters_schema": strategy_instance.get_parameters_schema(),
                },
                "state": {
                    "initialized": True,
                    "active": True,
                },
            }

    def analyze_active(self, ohlcv_data: list[dict[str, Any]]) -> dict[str, Any]:
        with self._lock:
            strategy = self._active_strategy
            if strategy is None:
                default_name = self._default_strategy_name()
                if default_name is None:
                    raise RuntimeError("No strategies are registered.")
                self.switch_strategy(default_name)
                strategy = self._active_strategy

            if strategy is None:
                raise RuntimeError("Strategy manager could not initialize a strategy.")

            try:
                result = strategy.analyze(ohlcv_data)
            except Exception as exc:  # pragma: no cover - runtime safety guard
                return {
                    "signal": "wait",
                    "confidence": 0.0,
                    "error": str(exc),
                    "parameters": strategy.get_parameters(),
                }

            normalized = dict(result)
            normalized.setdefault("signal", "wait")
            normalized.setdefault("confidence", 0.0)
            normalized.setdefault("parameters", strategy.get_parameters())
            return normalized


strategy_manager = StrategyManager()
