from __future__ import annotations

import uuid


class UUIDService:
    @staticmethod
    def new_uuid() -> str:
        return str(uuid.uuid4())
