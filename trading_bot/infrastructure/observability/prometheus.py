from __future__ import annotations


class PrometheusMetrics:
    def __init__(self) -> None:
        self._metrics: dict[str, float] = {}

    def increment(self, name: str, value: float = 1.0) -> None:
        self._metrics[name] = self._metrics.get(name, 0.0) + value

    def snapshot(self) -> dict[str, float]:
        return dict(self._metrics)
