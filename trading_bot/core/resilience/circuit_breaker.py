from __future__ import annotations

import time
from enum import Enum


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 30.0, half_open_max_calls: int = 1) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.half_open_max_calls = half_open_max_calls
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time = 0.0
        self._half_open_calls = 0

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self._half_open_calls = 0

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

    def allow_request(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.monotonic() - self.last_failure_time >= self.reset_timeout:
                self.state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                return True
            return False
        if self.state == CircuitState.HALF_OPEN:
            if self._half_open_calls < self.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False
        return True

    def reset(self) -> None:
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self._half_open_calls = 0
