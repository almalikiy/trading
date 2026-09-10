from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Mapping, TypeVar

from pydantic import BaseModel

StrategyClass = TypeVar("StrategyClass", bound=type["BaseStrategy"])


class BaseStrategy(ABC):
    """Common interface for all trading strategies."""

    name: str = "base_strategy"
    parameters_model: type[BaseModel] | None = None

    def __init__(self, parameters: Mapping[str, Any] | BaseModel | None = None) -> None:
        self.parameters: dict[str, Any] = {}
        self.initialize(parameters)

    def initialize(self, parameters: Mapping[str, Any] | BaseModel | None = None) -> None:
        if parameters is None:
            parameters = {}
        if isinstance(parameters, BaseModel):
            parameters = parameters.model_dump()
        if not isinstance(parameters, Mapping):
            raise TypeError("Strategy parameters must be a mapping or Pydantic model.")

        if self.parameters_model is not None:
            validated = self.parameters_model(**dict(parameters))
            self.parameters = validated.model_dump()
        else:
            self.parameters = dict(parameters)

    @abstractmethod
    def analyze(self, ohlcv_data: list[dict[str, Any]]) -> dict[str, Any]:
        """Return a normalized trading signal and metadata for the supplied OHLCV data."""

    def get_parameters_schema(self) -> dict[str, Any]:
        if self.parameters_model is None:
            return {}
        return self.parameters_model.model_json_schema()

    def get_parameters(self) -> dict[str, Any]:
        return dict(self.parameters)


class StrategyRegistry:
    """Registry that stores all available strategies by name."""

    def __init__(self) -> None:
        self._registry: dict[str, type[BaseStrategy]] = {}

    def register(self, name: str | None = None) -> Callable[[StrategyClass], StrategyClass]:
        def decorator(strategy_cls: StrategyClass) -> StrategyClass:
            if not issubclass(strategy_cls, BaseStrategy):
                raise TypeError(f"{strategy_cls.__name__} must inherit from BaseStrategy.")
            registry_name = name or getattr(strategy_cls, "name", strategy_cls.__name__)
            self._registry[registry_name] = strategy_cls
            return strategy_cls

        return decorator

    def get(self, strategy_name: str) -> type[BaseStrategy] | None:
        return self._registry.get(strategy_name)

    def available(self) -> dict[str, type[BaseStrategy]]:
        return dict(self._registry)

    def create(self, strategy_name: str, parameters: dict[str, Any] | None = None) -> BaseStrategy:
        strategy_cls = self.get(strategy_name)
        if strategy_cls is None:
            raise KeyError(f"Unknown strategy '{strategy_name}'.")
        return strategy_cls(parameters or {})


REGISTRY = StrategyRegistry()
register_strategy = REGISTRY.register


def get_strategy_registry() -> StrategyRegistry:
    return REGISTRY


def list_strategy_names() -> list[str]:
    return sorted(REGISTRY.available().keys())
