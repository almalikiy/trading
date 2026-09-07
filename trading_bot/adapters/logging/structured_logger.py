from __future__ import annotations

import logging


class StructuredLogger:
    def __init__(self, name: str = "trading-bot") -> None:
        self.logger = logging.getLogger(name)

    def info(self, message: str, **kwargs) -> None:
        self.logger.info(message, extra=kwargs)

    def warning(self, message: str, **kwargs) -> None:
        self.logger.warning(message, extra=kwargs)

    def error(self, message: str, **kwargs) -> None:
        self.logger.error(message, extra=kwargs)
