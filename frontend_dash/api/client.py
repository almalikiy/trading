from __future__ import annotations

from typing import Any

import requests

from frontend_dash.config import BACKEND_URL


def api_get(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{BACKEND_URL.rstrip('/')}{path}"
    response = requests.get(url, params=params or {}, timeout=15)
    if response.status_code >= 400:
        raise RuntimeError(f"{path} failed: {response.status_code} {response.text[:200]}")
    try:
        payload = response.json()
        if isinstance(payload, (dict, list, str, int, float, bool)) or payload is None:
            return payload
        return {}
    except ValueError:
        return response.text


def api_post(path: str, payload: dict[str, Any] | None = None) -> Any:
    url = f"{BACKEND_URL.rstrip('/')}{path}"
    response = requests.post(url, json=payload or {}, timeout=15)
    if response.status_code >= 400:
        raise RuntimeError(f"{path} failed: {response.status_code} {response.text[:200]}")
    try:
        return response.json()
    except ValueError:
        return response.text


def as_mapping(value: Any, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return default if isinstance(default, dict) else {}
