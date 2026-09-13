from __future__ import annotations

from typing import Any


def resolve_stream_state(
    signal_status: Any | None,
    keep_alive_enabled: bool | None = False,
    mt5_terminal_state: Any | None = None,
    signal_notice: Any | None = None,
) -> tuple[str, str, str]:
    """Return a single stream state for all dashboard panels."""
    status = str(signal_status or "degraded").lower()
    terminal_state = str(mt5_terminal_state or "offline").lower()
    is_live = status not in {"degraded", "error", "unavailable"} and (keep_alive_enabled or terminal_state in {"connected", "open"})
    mode = "live" if is_live else "degraded"
    if signal_notice:
        notice = str(signal_notice)
    elif keep_alive_enabled:
        notice = "MT5 Keep Alive is on. Stream is using live terminal-safe data."
    elif terminal_state == "open":
        notice = "MT5 terminal is open manually. Backend adapter connectivity is separate from the terminal process status."
    elif is_live:
        notice = "MT5 market feed connected."
    else:
        notice = "MT5 Keep Alive is off. Stream is using cached/non-terminal data only."
    badge = "LIVE" if is_live else "DEGRADED"
    return mode, badge, notice
