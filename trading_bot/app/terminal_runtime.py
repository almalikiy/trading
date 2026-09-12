from __future__ import annotations

import os
import subprocess
import threading
import time
from typing import Any

from trading_bot.app import db

try:  # pragma: no cover - runtime dependency
    import MetaTrader5 as mt5
except Exception:  # pragma: no cover
    mt5 = None

_PROCESS_PATHS_CACHE: dict[str, Any] = {"data": set(), "expires_at": 0.0}
_PROCESS_CACHE_LOCK = threading.Lock()
_BROKER_STATUS_CACHE: dict[tuple[Any, Any], dict[str, Any]] = {}
_BROKER_STATUS_REFRESHING: set[tuple[Any, Any]] = set()
_BROKER_STATUS_LOCK = threading.Lock()
_SYNC_ERROR_THROTTLE: dict[str, float] = {}
_SYNC_ERROR_LOCK = threading.Lock()
_MT5_LOCK = threading.Lock()
_BACKGROUND_SYNC_LOCK = threading.Lock()
_BACKGROUND_SYNC_STATE: dict[str, Any] = {
    "status": "idle",
    "queued_at": None,
    "started_at": None,
    "finished_at": None,
    "error": None,
    "last_result": None,
}
_KEEP_MT5_ALIVE_LOCK = threading.Lock()
_KEEP_MT5_ALIVE_STOP = threading.Event()
_KEEP_MT5_ALIVE_THREAD: threading.Thread | None = None
_KEEP_MT5_ALIVE_STATE: dict[str, Any] = {
    "enabled": False,
    "status": "disabled",
    "last_checked_at": None,
    "broker_name": None,
    "terminal_path": None,
    "message": "Keep MT5 alive is disabled.",
}


def _normalize_terminal_time_offset_seconds(raw_offset_sec: Any) -> int:
    try:
        raw = int(raw_offset_sec)
    except Exception:
        return 0

    candidates = [raw - (86400 * day_shift) for day_shift in range(-2, 3)]
    bounded = [value for value in candidates if abs(value) <= (15 * 3600)]
    if bounded:
        return min(bounded, key=lambda value: abs(value))
    return raw


def normalize_terminal_time_offset_seconds(raw_offset_sec: Any) -> int:
    return _normalize_terminal_time_offset_seconds(raw_offset_sec)


def calibrate_terminal_epoch_for_display(epoch_seconds: Any, offset_seconds: Any) -> int | None:
    try:
        ts = int(epoch_seconds or 0)
    except Exception:
        ts = 0
    if ts <= 0:
        return None
    try:
        return int(ts + int(offset_seconds or 0))
    except Exception:
        return ts


def _list_process_paths() -> set[str]:
    now = time.monotonic()
    with _PROCESS_CACHE_LOCK:
        if _PROCESS_PATHS_CACHE["expires_at"] > now:
            return set(_PROCESS_PATHS_CACHE["data"])

    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process | Select-Object -ExpandProperty ExecutablePath",
            ],
            text=True,
            timeout=1,
        )
        lines = [line.strip() for line in out.splitlines() if line and line.strip()]
        paths = set()
        for line in lines:
            try:
                if os.path.exists(line):
                    paths.add(os.path.normcase(os.path.abspath(line)))
            except Exception:
                continue
        with _PROCESS_CACHE_LOCK:
            _PROCESS_PATHS_CACHE["data"] = paths
            _PROCESS_PATHS_CACHE["expires_at"] = time.monotonic() + 3.0
        return paths
    except Exception:
        with _PROCESS_CACHE_LOCK:
            _PROCESS_PATHS_CACHE["data"] = set()
            _PROCESS_PATHS_CACHE["expires_at"] = time.monotonic() + 1.0
        return set()


def _safe_mt5_shutdown() -> None:
    if mt5 is None:
        return
    try:
        with _MT5_LOCK:
            mt5.shutdown()
    except Exception:
        pass


def _normalize_terminal_path_value(path_value: Any) -> str | None:
    try:
        text = str(path_value or "").strip()
    except Exception:
        return None
    if not text:
        return None
    return os.path.normcase(os.path.abspath(text))


def _default_broker_terminal_path() -> str | None:
    try:
        default_broker = db.get_default_broker() or {}
    except Exception:
        default_broker = {}
    return _normalize_terminal_path_value(default_broker.get("terminal_path"))


def _require_default_mt5_terminal_permission(terminal_path: str | None = None) -> str | None:
    if not _is_keep_terminal_alive_enabled():
        raise RuntimeError("MT5 startup denied: Keep MT5 alive is disabled.")

    default_path = _default_broker_terminal_path()
    if not terminal_path:
        if default_path:
            return default_path
        raise RuntimeError("MT5 startup denied: No default broker terminal is configured.")

    normalized = _normalize_terminal_path_value(terminal_path)
    if default_path and normalized and normalized == default_path:
        return default_path
    raise RuntimeError(
        "MT5 startup denied: Only the default broker terminal may initialize while keep-alive is enabled."
    )


def _allows_backend_terminal_autostart(terminal_path: str | None, *, broker: dict[str, Any] | None = None) -> bool:
    del broker
    if not terminal_path:
        return False
    normalized = _normalize_terminal_path_value(terminal_path)
    if not normalized:
        return False
    if not _is_keep_terminal_alive_enabled():
        return False

    default_path = _default_broker_terminal_path()
    if default_path and normalized == default_path:
        return True
    return False


def _get_active_mt5_terminal_target() -> tuple[str | None, str | None]:
    try:
        default_broker = db.get_default_broker() or {}
    except Exception:
        default_broker = {}

    if not default_broker:
        return None, None
    if str(default_broker.get("platform", "mt5")).lower() != "mt5":
        return None, None
    return default_broker.get("terminal_path"), default_broker.get("name")


def _is_keep_terminal_alive_enabled(state: dict[str, Any] | None = None) -> bool:
    runtime_enabled = bool(_KEEP_MT5_ALIVE_STATE.get("enabled", False))

    try:
        current = db.get_account_state() if state is None else state
    except Exception:
        current = state or {}

    if not isinstance(current, dict):
        return runtime_enabled

    persisted_enabled = bool(current.get("keep_terminal_alive", False))
    return bool(runtime_enabled or persisted_enabled)


def _log_mt5_error_throttled(
    message: str,
    *,
    broker_id: Any = None,
    broker_name: Any = None,
    account_id: Any = None,
    key: str | None = None,
    cooldown_sec: float = 30.0,
) -> bool:
    now = time.time()
    throttle_key = key or f"{broker_id}:{broker_name}:{message}"
    with _SYNC_ERROR_LOCK:
        last_ts = _SYNC_ERROR_THROTTLE.get(throttle_key, 0.0)
        if now - last_ts < float(cooldown_sec):
            return False
        _SYNC_ERROR_THROTTLE[throttle_key] = now

    db.log_mt5_error(message, broker_id=broker_id, broker_name=broker_name, account_id=account_id)
    return True


def _build_mt5_call_notice(*, call_name: str, strategy_related: bool) -> dict[str, Any]:
    if strategy_related:
        return {
            "call_classification": "frequent_strategy",
            "strategy_related": True,
            "notice": "This MT5 call is required for live trade strategy monitoring and can run when trade logic needs current market data.",
        }
    return {
        "call_classification": "rare_operational",
        "strategy_related": False,
        "notice": "This is a non-strategy MT5 operational check. It is deferred by default to avoid interfering with active trading and will only run after explicit user confirmation.",
    }


def _defer_non_strategy_mt5_check(*, call_name: str, payload: dict[str, Any], strategy_related: bool) -> bool:
    if strategy_related:
        return False
    notice = _build_mt5_call_notice(call_name=call_name, strategy_related=False)
    payload.update({
        "call_classification": notice["call_classification"],
        "strategy_related": notice["strategy_related"],
        "notice": notice["notice"],
        "reason": "deferred_non_strategy_check",
    })
    return True


def _check_mt5_non_strategy_confirmation(*, call_name: str, payload: dict[str, Any], strategy_related: bool) -> bool:
    if strategy_related:
        return False
    try:
        state = db.get_account_state()
    except Exception:
        state = {}
    if not isinstance(state, dict):
        state = {}
    require_confirmation = bool(state.get("mt5_non_strategy_require_confirmation", True))
    if not require_confirmation:
        return False
    confirmation_key = f"mt5_confirmed_{call_name}"
    confirmed = bool(state.get(confirmation_key, False))
    if confirmed:
        state[confirmation_key] = False
        try:
            db.save_account_state(state)
        except Exception:
            pass
        return False
    notice = _build_mt5_call_notice(call_name=call_name, strategy_related=False)
    payload.update({
        "call_classification": notice["call_classification"],
        "strategy_related": notice["strategy_related"],
        "notice": f"{notice['notice']} User confirmation is required before this operational MT5 check executes.",
        "reason": "confirmation_required",
        "requires_confirmation": True,
        "confirmation_required": True,
        "call_name": call_name,
    })
    return True


def _trade_type_from_position(position_type: Any) -> str:
    return "BUY" if mt5 is not None and position_type == mt5.POSITION_TYPE_BUY else "SELL"


def _trade_type_from_deal(deal_type: Any) -> str:
    return "BUY" if mt5 is not None and deal_type == mt5.DEAL_TYPE_BUY else "SELL"


def _weighted_price(deals: list[Any]) -> float | None:
    total_volume = sum(float(getattr(deal, "volume", 0) or 0) for deal in deals)
    if total_volume <= 0:
        return None
    total_value = sum(float(getattr(deal, "price", 0) or 0) * float(getattr(deal, "volume", 0) or 0) for deal in deals)
    return total_value / total_volume


def _sync_trade_id(broker_id: Any, account_id: Any, ticket: Any) -> str:
    return f"terminal-sync:{broker_id}:{account_id or 'unknown'}:{ticket}"


def _group_deals_by_position(deals: list[Any]):
    grouped: dict[int, list[Any]] = {}
    for deal in deals or []:
        position_id = int(getattr(deal, "position_id", 0) or 0)
        if position_id <= 0:
            continue
        grouped.setdefault(position_id, []).append(deal)
    for items in grouped.values():
        items.sort(key=lambda deal: (int(getattr(deal, "time", 0) or 0), int(getattr(deal, "ticket", 0) or 0)))
    return grouped


def normalize_lot_with_constraints(lot: float, constraints: dict[str, Any] | None):
    if constraints is None:
        return max(0.01, float(lot))
    step = float(constraints.get("volume_step") or 0)
    minimum = float(constraints.get("volume_min") or 0.01)
    maximum = float(constraints.get("volume_max") or max(minimum, float(lot)))
    value = float(lot)
    if value < minimum:
        value = minimum
    if value > maximum:
        value = maximum
    if step > 0:
        offset_steps = round((value - minimum) / step)
        value = minimum + (offset_steps * step)
        value = min(max(value, minimum), maximum)
        step_text = f"{step:.12f}".rstrip("0")
        decimals = len(step_text.split(".")[1]) if "." in step_text else 0
        value = round(value, min(max(decimals, 2), 8))
    return value


__all__ = [
    "mt5",
    "_PROCESS_PATHS_CACHE",
    "_PROCESS_CACHE_LOCK",
    "_BROKER_STATUS_CACHE",
    "_BROKER_STATUS_REFRESHING",
    "_BROKER_STATUS_LOCK",
    "_SYNC_ERROR_THROTTLE",
    "_SYNC_ERROR_LOCK",
    "_MT5_LOCK",
    "_BACKGROUND_SYNC_LOCK",
    "_BACKGROUND_SYNC_STATE",
    "_KEEP_MT5_ALIVE_LOCK",
    "_KEEP_MT5_ALIVE_STOP",
    "_KEEP_MT5_ALIVE_THREAD",
    "_KEEP_MT5_ALIVE_STATE",
    "_normalize_terminal_time_offset_seconds",
    "normalize_terminal_time_offset_seconds",
    "calibrate_terminal_epoch_for_display",
    "_list_process_paths",
    "_safe_mt5_shutdown",
    "_normalize_terminal_path_value",
    "_default_broker_terminal_path",
    "_require_default_mt5_terminal_permission",
    "_allows_backend_terminal_autostart",
    "_get_active_mt5_terminal_target",
    "_is_keep_terminal_alive_enabled",
    "_log_mt5_error_throttled",
    "_build_mt5_call_notice",
    "_defer_non_strategy_mt5_check",
    "_check_mt5_non_strategy_confirmation",
    "_trade_type_from_position",
    "_trade_type_from_deal",
    "_weighted_price",
    "_sync_trade_id",
    "_group_deals_by_position",
    "normalize_lot_with_constraints",
]
