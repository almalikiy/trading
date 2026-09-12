#file : frontend_dash/components/toolbar.py
from __future__ import annotations

from dash import dcc, html

from frontend_dash.config import DEFAULT_BARS, DEFAULT_SYMBOL, DEFAULT_TIMEFRAME, TIMEFRAME_OPTIONS


def build_toolbar() -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.Label("Symbol"),
                    dcc.Input(id="symbol-input", value=DEFAULT_SYMBOL, type="text", className="toolbar-input symbol"),
                ],
                className="toolbar-field",
            ),
            html.Div(
                [
                    html.Label("Timeframe"),
                    dcc.Dropdown(
                        id="timeframe-input",
                        options=TIMEFRAME_OPTIONS,
                        value=DEFAULT_TIMEFRAME,
                        clearable=False,
                        className="toolbar-select",
                    ),
                ],
                className="toolbar-field",
            ),
            html.Div(
                [
                    html.Label("Bars"),
                    dcc.Input(id="bars-input", value=str(DEFAULT_BARS), type="number", min=30, max=240, step=30, className="toolbar-input bars"),
                ],
                className="toolbar-field",
            ),
            html.Button("Toggle Auto Trade", id="auto-trade-toggle", n_clicks=0, className="action-button neutral"),
            html.Button("Enable Keep MT5 Alive", id="keep-mt5-alive-toolbar-button", n_clicks=0, className="action-button neutral"),
            html.Button("Confirm MT5 Operational Check", id="confirm-mt5-operation-button", n_clicks=0, className="action-button neutral"),
            html.Div(id="auto-trade-toolbar-status", children="Auto Trade: Unknown", className="toolbar-status"),
            html.Div(id="keep-mt5-alive-toolbar-status", children="MT5 Keep Alive: OFF", className="toolbar-status"),
            html.Div(id="confirm-mt5-operation-status", children="MT5 Operational Check: Pending", className="toolbar-status"),
            html.Div(
                [
                    html.Span(className="status-dot pill-sync-queued", id="toolbar-stream-status-dot"),
                    html.Span("DEGRADED MODE", id="toolbar-stream-status"),
                    html.Span(
                        "MT5 Keep Alive is off. Stream is using cached/non-terminal data only.",
                        id="toolbar-stream-detail",
                        className="toolbar-stream-detail",
                    ),
                ],
                className="toolbar-stream-status",
                title="MT5 Keep Alive is off. Stream is using cached/non-terminal data only.",
            ),
        ],
        className="panel main-toolbar",
    )
