from __future__ import annotations

from typing import Any

from dash import ALL, Dash, Input, Output, State, callback_context

from frontend_dash.api.client import api_get, api_post, as_mapping
from frontend_dash.components.inputs import build_strategy_parameter_inputs


def resolve_auto_trade_toggle_state(health: dict[str, Any] | Any) -> tuple[str, str]:
    payload = as_mapping(health)
    enabled = bool(payload.get("auto_trade_enabled") if "auto_trade_enabled" in payload else False)
    status = f"Auto Trade: {'Enabled' if enabled else 'Disabled'}"
    label = "Disable Auto Trade" if enabled else "Enable Auto Trade"
    return status, label


def register_strategy_callbacks(app: Dash) -> None:
    @app.callback(
        Output("strategy-parameter-inputs", "children"),
        Input("strategy-dropdown", "value"),
    )
    def update_strategy_parameter_inputs(strategy_name: str | None):
        return build_strategy_parameter_inputs(strategy_name or "moving_average_cross")

    @app.callback(
        Output("strategy-parameter-store", "data"),
        Input({"type": "strategy-parameter", "index": ALL}, "value"),
        State({"type": "strategy-parameter", "index": ALL}, "id"),
        prevent_initial_call=True,
    )
    def sync_strategy_parameter_store(values: list[Any] | None, ids: list[dict[str, str]] | None):
        payload: dict[str, Any] = {}
        values = values or []
        ids = ids or []
        for value, item in zip(values, ids[: len(values)]):
            key = item.get("index") if isinstance(item, dict) else None
            if key:
                payload[key] = value
        return payload

    @app.callback(
        Output("strategy-control-status", "children"),
        Input("strategy-apply-button", "n_clicks"),
        Input("auto-trade-master-toggle", "value"),
        State("strategy-dropdown", "value"),
        State("strategy-parameter-store", "data"),
        prevent_initial_call=True,
    )
    def apply_strategy_and_settings(_n_clicks: int | None, master_toggle: list[str] | None, strategy_name: str | None, parameter_store: dict[str, Any] | None):
        try:
            enabled = "auto_trade_enabled" in (master_toggle or [])
            live_mode = "live_mode" in (master_toggle or [])
            if strategy_name:
                api_post("/strategies/switch", {"name": strategy_name, "parameters": parameter_store or {}})
            api_post("/account/set_auto_trade_enabled", {"enabled": enabled})
            api_post("/account/set_enable_real_trade", {"enabled": live_mode})
            return f"Strategy {strategy_name or 'default'} applied. Auto Trade: {'ON' if enabled else 'OFF'} | Live Mode: {'ON' if live_mode else 'OFF'}"
        except Exception as exc:
            return f"Strategy update failed: {exc}"

    @app.callback(
        Output("auto-trade-master-toggle", "value"),
        Input("global-ui-state", "data"),
        prevent_initial_call=False,
    )
    def sync_auto_trade_master_toggle(global_state: dict[str, Any] | None):
        state = as_mapping(global_state)
        values: list[str] = []
        if bool(state.get("auto_trade_enabled", False)):
            values.append("auto_trade_enabled")
        if bool(state.get("live_mode", False)):
            values.append("live_mode")
        return values

    @app.callback(
        Output("auto-trade-toolbar-status", "children"),
        Output("auto-trade-toggle", "children"),
        Input("auto-trade-toggle", "n_clicks"),
        Input("global-ui-state", "data"),
        prevent_initial_call=False,
    )
    def toggle_auto_trade(_n_clicks: int | None, global_state: dict[str, Any] | None):
        try:
            state = as_mapping(global_state)
            enabled = bool(state.get("auto_trade_enabled", False))
            if callback_context.triggered_id == "auto-trade-toggle" and _n_clicks not in (None, 0):
                next_enabled = not enabled
                api_post("/account/set_auto_trade_enabled", {"enabled": next_enabled})
                enabled = next_enabled
            status, label = resolve_auto_trade_toggle_state({"auto_trade_enabled": enabled})
            return status, label
        except Exception as exc:
            return (f"Auto Trade update failed: {exc}", "Enable Auto Trade")
