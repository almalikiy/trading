from __future__ import annotations

from typing import Any

from dash import ALL, Dash, Input, Output, State

from frontend_dash.api.client import api_get, api_post, as_mapping
from frontend_dash.components.inputs import build_strategy_parameter_inputs


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
    def sync_strategy_parameter_store(values: list[Any], ids: list[dict[str, str]]):
        payload: dict[str, Any] = {}
        for value, item in zip(values, ids):
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
        Output("auto-trade-toolbar-status", "children"),
        Output("auto-trade-toggle", "children"),
        Input("auto-trade-toggle", "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_auto_trade(_n_clicks: int | None):
        try:
            payload = api_get("/account/auto_trade_health")
            health = as_mapping(payload)
            enabled = bool(health.get("auto_trade_enabled") if "auto_trade_enabled" in health else False)
            next_enabled = not enabled
            api_post("/account/set_auto_trade_enabled", {"enabled": next_enabled})
            return (
                f"Auto Trade: {'Enabled' if next_enabled else 'Disabled'}",
                "Disable Auto Trade" if next_enabled else "Enable Auto Trade",
            )
        except Exception as exc:
            return (f"Auto Trade update failed: {exc}", "Enable Auto Trade")
