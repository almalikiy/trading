from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LoggerPort(ABC):
    @abstractmethod
    def info(self, message: str, **kwargs: Any) -> None:
        """Log an informational message."""

    @abstractmethod
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log a warning."""

    @abstractmethod
    def error(self, message: str, **kwargs: Any) -> None:
        """Log an error."""
