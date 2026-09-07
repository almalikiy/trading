from __future__ import annotations

from trading_bot.app.bootstrap import bootstrap


class Runtime:
    def __init__(self) -> None:
        self.bootstrap_info = bootstrap()

    def info(self) -> dict[str, object]:
        return self.bootstrap_info


runtime = Runtime()
