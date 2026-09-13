from frontend_dash.state import resolve_stream_state


def test_stream_state_is_consistent_across_keep_alive_and_terminal_state():
    mode, badge, notice = resolve_stream_state("degraded", keep_alive_enabled=False, mt5_terminal_state="offline")
    assert mode == "degraded"
    assert badge == "DEGRADED"
    assert "cached/non-terminal" in notice

    mode, badge, notice = resolve_stream_state("ok", keep_alive_enabled=True, mt5_terminal_state="offline")
    assert mode == "live"
    assert badge == "LIVE"
    assert "live terminal-safe data" in notice

    mode, badge, notice = resolve_stream_state("ok", keep_alive_enabled=False, mt5_terminal_state="open")
    assert mode == "live"
    assert badge == "LIVE"
    assert "open manually" in notice
