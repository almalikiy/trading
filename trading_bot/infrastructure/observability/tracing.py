from __future__ import annotations


class Tracing:
    def __init__(self) -> None:
        self.spans: list[str] = []

    def start_span(self, name: str) -> str:
        self.spans.append(name)
        return name
