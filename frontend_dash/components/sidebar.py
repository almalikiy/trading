from __future__ import annotations

from dash import dcc, html

from frontend_dash.config import PAGE_OPTIONS


def build_sidebar() -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.Div(className="brand-mark"),
                    html.Span("Trading Console"),
                ],
                className="brand",
            ),
            html.Button(
                [
                    html.Span("<>", className="drawer-icon"),
                    html.Span("Collapse", className="drawer-toggle-text"),
                ],
                id="drawer-toggle",
                className="drawer-toggle",
                n_clicks=0,
            ),
            html.Button(
                "Switch to Light",
                id="theme-toggle",
                className="theme-toggle",
                n_clicks=0,
            ),
            html.Div("Navigation", className="sidebar-section-title"),
            dcc.RadioItems(
                id="page-selector",
                options=PAGE_OPTIONS,
                value="overview",
                className="sidebar-nav",
            ),
            html.Div(
                [
                    html.Div("Stream Status", className="sidebar-section-title"),
                    html.Div(
                        [
                            html.Span(className="status-dot pill-sync-queued", id="stream-status-badge-dot"),
                            html.Span("DEGRADED", id="stream-status-badge"),
                        ],
                        className="global-stream-badge",
                        id="global-stream-badge",
                        title="MT5 Keep Alive is off. Stream is using cached/non-terminal data only.",
                    ),
                    html.Div(
                        "MT5 Keep Alive is off. Stream is using cached/non-terminal data only.",
                        id="stream-status-detail",
                        className="global-stream-detail",
                        title="MT5 Keep Alive is off. Stream is using cached/non-terminal data only.",
                    ),
                ],
                className="sidebar-stream-panel",
            ),
            html.Div(className="sidebar-spacer"),
        ],
        id="sidebar-drawer",
        className="sidebar-drawer",
    )
