from __future__ import annotations


class SessionFactory:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def create(self):
        return {"dsn": self.dsn, "status": "not_connected"}
