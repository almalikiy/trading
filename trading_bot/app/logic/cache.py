from __future__ import annotations

import threading
import time
from typing import Any, Callable

signal_cache: dict[str, dict[str, Any]] = {}
ohlcv_cache: dict[str, dict[str, Any]] = {}
refreshing_signal: set[str] = set()
refreshing_ohlcv: set[str] = set()
cache_lock = threading.Lock()


def cache_key(*parts: Any) -> str:
    return "|".join("" if part is None else str(part) for part in parts)


def start_background_refresh(kind: str, key: str, producer: Callable[[], Any]) -> bool:
    with cache_lock:
        target_refreshing = refreshing_signal if kind == "signal" else refreshing_ohlcv
        if key in target_refreshing:
            return False
        target_refreshing.add(key)

    def runner() -> None:
        try:
            data = producer()
            if kind == "ohlcv" and not isinstance(data, list):
                data = []
        except Exception:
            data = [] if kind == "ohlcv" else {"error": "refresh_failed"}
        finally:
            with cache_lock:
                target_cache = signal_cache if kind == "signal" else ohlcv_cache
                target_cache[key] = {
                    "kind": kind,
                    "data": data,
                    "updated_at": time.time(),
                }
                if kind == "signal":
                    refreshing_signal.discard(key)
                else:
                    refreshing_ohlcv.discard(key)

    threading.Thread(target=runner, daemon=True).start()
    return True
