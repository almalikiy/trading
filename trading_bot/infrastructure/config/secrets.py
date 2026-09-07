from __future__ import annotations

import os


def get_secret(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    return value
