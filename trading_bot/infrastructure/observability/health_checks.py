from __future__ import annotations


class HealthCheck:
    def __init__(self) -> None:
        self.status = "ok"

    def check(self) -> str:
        return self.status
