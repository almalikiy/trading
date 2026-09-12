from __future__ import annotations

import os
import subprocess
import threading
import time
from typing import Any

from trading_bot.app import db
from trading_bot.app import terminal_runtime as runtime
from trading_bot.app.terminal_brokers import (
    MT5Adapter,
    MouseAdapter,
    SimulationAdapter,
    TerminalAdapter,
    estimate_broker_time_offset_seconds,
    get_broker_account_metrics,
    get_broker_adapter,
    get_broker_order_status_snapshot,
    get_broker_symbol_constraints,
    get_broker_symbol_tick,
    normalize_lot_with_constraints,
    probe_broker_order_status,
)
from trading_bot.app.terminal_lifecycle import (
    get_keep_mt5_alive_status,
    set_keep_mt5_alive,
)
from trading_bot.app.terminal_runtime import (
    _KEEP_MT5_ALIVE_LOCK,
    _KEEP_MT5_ALIVE_STATE,
    _KEEP_MT5_ALIVE_STOP,
    _KEEP_MT5_ALIVE_THREAD,
    _MT5_LOCK,
    _default_broker_terminal_path,
    _get_active_mt5_terminal_target,
    _is_keep_terminal_alive_enabled,
    _list_process_paths,
    _require_default_mt5_terminal_permission,
    calibrate_terminal_epoch_for_display,
    mt5,
    normalize_terminal_time_offset_seconds,
)
from trading_bot.app.terminal_sync import (
    get_background_mt5_sync_status,
    sync_all_terminal_trade_state,
    sync_broker_trade_state,
    sync_trade_state_for_history_flow,
    sync_trade_state_for_history_flow_in_background,
)


def ensure_terminal_running(terminal_path: str | None, *, force: bool = False, broker: dict[str, Any] | None = None) -> bool:
    if not terminal_path:
        return False

    if not _is_keep_terminal_alive_enabled():
        return False

    default_broker = db.get_default_broker() or {}
    default_path = runtime._normalize_terminal_path_value(default_broker.get("terminal_path"))
    normalized = runtime._normalize_terminal_path_value(terminal_path)
    if not normalized:
        return False
    if default_path and normalized != default_path:
        return False

    for proc in _list_process_paths():
        if proc == normalized:
            return True

    try:
        if force or broker is None or bool(broker.get("is_default") or broker.get("terminal_path") == terminal_path):
            subprocess.Popen([terminal_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
    except Exception:
        return False
    return False

__all__ = [
    "TerminalAdapter",
    "MT5Adapter",
    "MouseAdapter",
    "SimulationAdapter",
    "_MT5_LOCK",
    "normalize_terminal_time_offset_seconds",
    "calibrate_terminal_epoch_for_display",
    "estimate_broker_time_offset_seconds",
    "ensure_terminal_running",
    "set_keep_mt5_alive",
    "get_keep_mt5_alive_status",
    "get_broker_adapter",
    "probe_broker_order_status",
    "get_broker_order_status_snapshot",
    "normalize_lot_with_constraints",
    "get_broker_symbol_constraints",
    "get_broker_account_metrics",
    "get_broker_symbol_tick",
    "sync_broker_trade_state",
    "sync_all_terminal_trade_state",
    "sync_trade_state_for_history_flow",
    "get_background_mt5_sync_status",
    "sync_trade_state_for_history_flow_in_background",
]
