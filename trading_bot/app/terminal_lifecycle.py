from __future__ import annotations

import os
import subprocess
import threading
import time
from typing import Any

from trading_bot.app import db
from trading_bot.app.terminal_runtime import (
    _KEEP_MT5_ALIVE_LOCK,
    _KEEP_MT5_ALIVE_STATE,
    _KEEP_MT5_ALIVE_STOP,
    _KEEP_MT5_ALIVE_THREAD,
    _allows_backend_terminal_autostart,
    _get_active_mt5_terminal_target,
    _is_keep_terminal_alive_enabled,
    _list_process_paths,
)


def ensure_terminal_running(terminal_path: str | None, *, force: bool = False, broker: dict[str, Any] | None = None) -> bool:
    if not terminal_path:
        return False
    if not _allows_backend_terminal_autostart(terminal_path, broker=broker):
        return False
    if force and not _is_keep_terminal_alive_enabled():
        return False
    normalized = os.path.normcase(os.path.abspath(terminal_path))
    for proc in _list_process_paths():
        if proc == normalized:
            return True
    try:
        subprocess.Popen([terminal_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def _keep_mt5_alive_loop() -> None:
    while not _KEEP_MT5_ALIVE_STOP.is_set():
        try:
            enabled = bool(_KEEP_MT5_ALIVE_STATE.get("enabled", False))
            if not enabled:
                _KEEP_MT5_ALIVE_STATE["status"] = "disabled"
                _KEEP_MT5_ALIVE_STATE["message"] = "Keep MT5 alive is disabled."
                break
            terminal_path, broker_name = _get_active_mt5_terminal_target()
            if not terminal_path:
                _KEEP_MT5_ALIVE_STATE.update({
                    "status": "idle",
                    "broker_name": broker_name,
                    "terminal_path": None,
                    "last_checked_at": time.time(),
                    "message": "No active MT5 terminal path found for keep-alive monitoring.",
                })
            else:
                default_broker = db.get_default_broker() or {}
                started = ensure_terminal_running(
                    terminal_path,
                    force=True,
                    broker={
                        "is_default": bool(default_broker.get("is_default")),
                        "terminal_path": default_broker.get("terminal_path"),
                    },
                )
                _KEEP_MT5_ALIVE_STATE.update({
                    "status": "running" if started else "failed",
                    "broker_name": broker_name,
                    "terminal_path": terminal_path,
                    "last_checked_at": time.time(),
                    "message": f"MT5 terminal check completed. started={started}",
                })
        except Exception as exc:
            _KEEP_MT5_ALIVE_STATE.update({
                "status": "failed",
                "broker_name": None,
                "terminal_path": None,
                "last_checked_at": time.time(),
                "message": str(exc),
            })
        _KEEP_MT5_ALIVE_STOP.wait(15.0)


def set_keep_mt5_alive(enabled: bool) -> dict[str, Any]:
    enabled = bool(enabled)
    state = db.get_account_state()
    state["keep_terminal_alive"] = enabled
    db.save_account_state(state)
    with _KEEP_MT5_ALIVE_LOCK:
        _KEEP_MT5_ALIVE_STATE["enabled"] = enabled
        _KEEP_MT5_ALIVE_STATE["status"] = "running" if enabled else "disabled"
        _KEEP_MT5_ALIVE_STATE["message"] = "Keep MT5 alive is enabled." if enabled else "Keep MT5 alive is disabled."
        _KEEP_MT5_ALIVE_STATE["last_checked_at"] = time.time()
    if enabled:
        global _KEEP_MT5_ALIVE_THREAD
        _KEEP_MT5_ALIVE_STOP.clear()
        if (_KEEP_MT5_ALIVE_THREAD is None) or (not _KEEP_MT5_ALIVE_THREAD.is_alive()):
            thread = threading.Thread(target=_keep_mt5_alive_loop, name="mt5-keepalive", daemon=True)
            _KEEP_MT5_ALIVE_THREAD = thread
            thread.start()
    else:
        _KEEP_MT5_ALIVE_STOP.set()
        _KEEP_MT5_ALIVE_STATE["status"] = "disabled"
    return get_keep_mt5_alive_status()


def get_keep_mt5_alive_status() -> dict[str, Any]:
    try:
        state = db.get_account_state()
    except Exception:
        state = {}
    enabled = bool(state.get("keep_terminal_alive", _KEEP_MT5_ALIVE_STATE.get("enabled", False)))
    with _KEEP_MT5_ALIVE_LOCK:
        payload = {
            "enabled": enabled,
            "status": _KEEP_MT5_ALIVE_STATE.get("status", "disabled"),
            "last_checked_at": _KEEP_MT5_ALIVE_STATE.get("last_checked_at"),
            "broker_name": _KEEP_MT5_ALIVE_STATE.get("broker_name"),
            "terminal_path": _KEEP_MT5_ALIVE_STATE.get("terminal_path"),
            "message": _KEEP_MT5_ALIVE_STATE.get("message", "Keep MT5 alive is disabled."),
        }
    payload["enabled"] = enabled
    return payload


__all__ = [
    "ensure_terminal_running",
    "_keep_mt5_alive_loop",
    "set_keep_mt5_alive",
    "get_keep_mt5_alive_status",
]
