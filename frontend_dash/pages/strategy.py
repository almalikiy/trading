from __future__ import annotations

from dash import dcc, html

from frontend_dash.api.client import api_get
from frontend_dash.components.inputs import build_strategy_parameter_inputs


def render_strategy_page():
    try:
        payload = api_get("/strategies/list")
        strategies = payload.get("strategies", []) if isinstance(payload, dict) else []
        options = [{"label": item.get("name", "unknown"), "value": item.get("name", "unknown")} for item in strategies]
        default_value = options[0]["value"] if options else "moving_average_cross"

        return html.Div(
            [
                html.Div("Strategy Control Center", className="section-label"),
                html.Div(
                    [
                        html.Label("Strategy", className="field-label"),
                        dcc.Dropdown(
                            id="strategy-dropdown",
                            options=options,
                            value=default_value,
                            clearable=False,
                            className="strategy-select",
                        ),
                        html.Div(
                            id="strategy-parameter-inputs",
                            children=build_strategy_parameter_inputs(default_value),
                            className="strategy-params-wrap",
                        ),
                        dcc.Checklist(
                            id="auto-trade-master-toggle",
                            options=[
                                {"label": "Enable Auto Trade", "value": "auto_trade_enabled"},
                                {"label": "Live Trading Mode", "value": "live_mode"},
                            ],
                            value=["auto_trade_enabled", "live_mode"],
                            inline=True,
                            className="strategy-flags",
                        ),
                        html.Button("Apply Strategy", id="strategy-apply-button", n_clicks=0, className="action-button neutral"),
                        html.Div(id="strategy-control-status", className="strategy-status"),
                        dcc.Store(id="strategy-parameter-store", data={}),
                    ],
                    className="strategy-form",
                ),
            ],
            className="page-layout panel",
        )
    except Exception as exc:
        return html.Div([
            html.H3("Strategy page unavailable"),
            html.P(str(exc), className="error-text"),
        ], className="error-panel")
