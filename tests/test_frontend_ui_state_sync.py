from frontend_dash.callbacks.navigation_callbacks import resolve_keep_alive_state
from frontend_dash.callbacks.strategy_callbacks import resolve_auto_trade_toggle_state


def test_auto_trade_toggle_state_uses_backend_enabled_value():
    status, label = resolve_auto_trade_toggle_state({"auto_trade_enabled": True})
    assert status == "Auto Trade: Enabled"
    assert label == "Disable Auto Trade"

    status, label = resolve_auto_trade_toggle_state({"auto_trade_enabled": False})
    assert status == "Auto Trade: Disabled"
    assert label == "Enable Auto Trade"


def test_keep_alive_state_uses_backend_enabled_value():
    button, detail = resolve_keep_alive_state({"enabled": True, "status": "ok"})
    assert button == "Disable Keep MT5 Alive"
    assert detail == "MT5 Keep Alive: ON • Ok"

    button, detail = resolve_keep_alive_state({"enabled": False, "status": "disabled"})
    assert button == "Enable Keep MT5 Alive"
    assert detail == "MT5 Keep Alive: OFF • Disabled"
