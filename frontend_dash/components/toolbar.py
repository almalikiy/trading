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
            html.Div(id="auto-trade-toolbar-status", children="Auto Trade: Unknown", className="toolbar-status"),
        ],
        className="panel main-toolbar",
    )
