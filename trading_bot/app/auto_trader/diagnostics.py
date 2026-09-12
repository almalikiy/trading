from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any, Callable

DIAG_LOCK = threading.Lock()
OPEN_FAIL_LOG_LOCK = threading.Lock()
OPEN_FAIL_LOG_TS: dict[str, float] = {}
AUTO_TRADE_DIAG: dict[str, Any] = {
    "started_at": int(time.time()),
    "last_cycle_at": None,
    "last_decision": "init",
    "last_reason": "not_started",
    "last_signal": "wait",
    "last_signal_score": 0.0,
    "last_symbol": None,
    "last_open_attempt_at": None,
    "last_open_attempt": None,
    "last_open_success_at": None,
    "last_open_error": None,
    "last_close_attempt_at": None,
    "last_close_attempt": None,
    "skip_counts": {},
    "recent_events": deque(maxlen=40),
}


def _log_open_failure_throttled(reason: str, log_mt5_error: Callable[..., Any], **extra: Any) -> None:
    symbol = str(extra.get("symbol") or "-")
    broker = str(extra.get("broker_name") or "-")
    key = f"{reason}:{symbol}:{broker}"
    now = time.time()

    with OPEN_FAIL_LOG_LOCK:
        last_ts = OPEN_FAIL_LOG_TS.get(key, 0.0)
        if now - last_ts < 30.0:
            return
        OPEN_FAIL_LOG_TS[key] = now

    details = []
    for field in ("signal", "spread_points", "max_spread_points", "lot", "method", "broker_reason", "error"):
        if extra.get(field) is not None:
            details.append(f"{field}={extra.get(field)}")
    message = f"auto_open blocked [{reason}] symbol={symbol} broker={broker}"
    if details:
        message += " " + " ".join(details)
    log_mt5_error(message, broker_name=(None if broker == "-" else broker))


def diag_event(decision: str, reason: str, **extra: Any) -> None:
    now = int(time.time())
    with DIAG_LOCK:
        AUTO_TRADE_DIAG["last_cycle_at"] = now
        AUTO_TRADE_DIAG["last_decision"] = decision
        AUTO_TRADE_DIAG["last_reason"] = reason
        if "symbol" in extra and extra.get("symbol"):
            AUTO_TRADE_DIAG["last_symbol"] = str(extra.get("symbol"))
        if "signal" in extra and extra.get("signal") is not None:
            AUTO_TRADE_DIAG["last_signal"] = str(extra.get("signal"))
        if "signal_score" in extra and extra.get("signal_score") is not None:
            AUTO_TRADE_DIAG["last_signal_score"] = float(extra.get("signal_score"))
        if decision == "skip":
            counts = AUTO_TRADE_DIAG["skip_counts"]
            counts[reason] = int(counts.get(reason, 0)) + 1
        AUTO_TRADE_DIAG["recent_events"].append(
            {
                "ts": now,
                "decision": decision,
                "reason": reason,
                "extra": extra,
            }
        )


def diag_open_attempt(status: str, log_mt5_error: Callable[..., Any], **extra: Any) -> None:
    now = int(time.time())
    with DIAG_LOCK:
        AUTO_TRADE_DIAG["last_open_attempt_at"] = now
        AUTO_TRADE_DIAG["last_open_attempt"] = {"status": status, **extra}
        if status == "ok":
            AUTO_TRADE_DIAG["last_open_success_at"] = now
            AUTO_TRADE_DIAG["last_open_error"] = None
        elif status == "error":
            AUTO_TRADE_DIAG["last_open_error"] = str(extra.get("error") or "unknown")
            details = dict(extra)
            reason = str(details.pop("reason", "unknown"))
            _log_open_failure_throttled(reason, log_mt5_error, **details)


def diag_close_attempt(status: str, **extra: Any) -> None:
    now = int(time.time())
    with DIAG_LOCK:
        AUTO_TRADE_DIAG["last_close_attempt_at"] = now
        AUTO_TRADE_DIAG["last_close_attempt"] = {"status": status, **extra}


def get_runtime_status(loop_started: bool) -> dict[str, Any]:
    with DIAG_LOCK:
        return {
            "loop_started": bool(loop_started),
            "started_at": AUTO_TRADE_DIAG.get("started_at"),
            "last_cycle_at": AUTO_TRADE_DIAG.get("last_cycle_at"),
            "last_decision": AUTO_TRADE_DIAG.get("last_decision"),
            "last_reason": AUTO_TRADE_DIAG.get("last_reason"),
            "last_signal": AUTO_TRADE_DIAG.get("last_signal"),
            "last_signal_score": AUTO_TRADE_DIAG.get("last_signal_score"),
            "last_symbol": AUTO_TRADE_DIAG.get("last_symbol"),
            "last_open_attempt_at": AUTO_TRADE_DIAG.get("last_open_attempt_at"),
            "last_open_attempt": AUTO_TRADE_DIAG.get("last_open_attempt"),
            "last_open_success_at": AUTO_TRADE_DIAG.get("last_open_success_at"),
            "last_open_error": AUTO_TRADE_DIAG.get("last_open_error"),
            "last_close_attempt_at": AUTO_TRADE_DIAG.get("last_close_attempt_at"),
            "last_close_attempt": AUTO_TRADE_DIAG.get("last_close_attempt"),
            "skip_counts": dict(AUTO_TRADE_DIAG.get("skip_counts") or {}),
            "recent_events": list(AUTO_TRADE_DIAG.get("recent_events") or []),
        }
