from __future__ import annotations

import os


def env_or_default(name: str, default: str = "") -> str:
    return os.getenv(name, default)
