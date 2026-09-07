from __future__ import annotations


class KillSwitch:
    def __init__(self) -> None:
        self.enabled = False

    def arm(self) -> None:
        self.enabled = True

    def disarm(self) -> None:
        self.enabled = False

    def is_active(self) -> bool:
        return self.enabled
