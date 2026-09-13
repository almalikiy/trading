from __future__ import annotations

import asyncio
from typing import Any

import requests

from frontend_dash.config import BACKEND_URL


def api_get(path: str, params: dict[str, Any] | None = None, timeout: float = 2) -> Any:
    url = f"{BACKEND_URL.rstrip('/')}{path}"
    response = requests.get(url, params=params or {}, timeout=timeout)
    if response.status_code >= 400:
        raise RuntimeError(f"{path} failed: {response.status_code} {response.text[:200]}")
    try:
        payload = response.json()
        if isinstance(payload, (dict, list, str, int, float, bool)) or payload is None:
            return payload
        return {}
    except ValueError:
        return response.text


async def api_get_async(path: str, params: dict[str, Any] | None = None, timeout: float = 2) -> Any:
    return await asyncio.to_thread(api_get, path, params=params, timeout=timeout)


def api_post(path: str, payload: dict[str, Any] | None = None, timeout: float = 15) -> Any:
    url = f"{BACKEND_URL.rstrip('/')}{path}"
    response = requests.post(url, json=payload or {}, timeout=timeout)
    if response.status_code >= 400:
        raise RuntimeError(f"{path} failed: {response.status_code} {response.text[:200]}")
    try:
        return response.json()
    except ValueError:
        return response.text


async def api_post_async(path: str, payload: dict[str, Any] | None = None, timeout: float = 15) -> Any:
    return await asyncio.to_thread(api_post, path, payload=payload, timeout=timeout)


def api_put(path: str, payload: dict[str, Any] | None = None, timeout: float = 15) -> Any:
    url = f"{BACKEND_URL.rstrip('/')}{path}"
    response = requests.put(url, json=payload or {}, timeout=timeout)
    if response.status_code >= 400:
        raise RuntimeError(f"{path} failed: {response.status_code} {response.text[:200]}")
    try:
        return response.json()
    except ValueError:
        return response.text


def api_delete(path: str, timeout: float = 15) -> Any:
    url = f"{BACKEND_URL.rstrip('/')}{path}"
    response = requests.delete(url, timeout=timeout)
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
