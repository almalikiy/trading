from __future__ import annotations


class ExposureLimits:
    def __init__(self, max_open_positions: int = 5) -> None:
        self.max_open_positions = max_open_positions

    def allowed(self, current_positions: int) -> bool:
        return current_positions < self.max_open_positions
