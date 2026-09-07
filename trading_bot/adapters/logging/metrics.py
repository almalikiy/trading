from __future__ import annotations


class MetricsCollector:
    def __init__(self) -> None:
        self._values: dict[str, float] = {}

    def increment(self, name: str, value: float = 1.0) -> None:
        self._values[name] = self._values.get(name, 0.0) + value

    def snapshot(self) -> dict[str, float]:
        return dict(self._values)
