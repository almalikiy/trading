#file : frontend_dash/app.py
import os
import sys
from pathlib import Path

from dash import dcc, html

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parent.parent
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

from frontend_dash.callbacks import register_navigation_callbacks, register_strategy_callbacks # Import callback registration functions
from frontend_dash.components.sidebar import build_sidebar # Import sidebar component builder function
from frontend_dash.components.toolbar import build_toolbar # Import toolbar component builder function
from frontend_dash.config import REFRESH_MS # Import refresh interval configuration
from frontend_dash.server import app # Import Dash app instance


def _dash_runtime_settings() -> tuple[str, int, bool]:
    """Use explicit environment overrides for local development to avoid duplicate reloaders."""
    host = os.getenv("DASH_HOST", "0.0.0.0")
    port = int(os.getenv("DASH_PORT", "8050"))
    debug = os.getenv("DASH_DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"}
    use_reloader = debug and os.getenv("DASH_USE_RELOADER", "true").strip().lower() in {"1", "true", "yes", "on"}
    return host, port, use_reloader


def build_layout() -> html.Div:  # Build the main layout of the Dash app
    return html.Div(
        [
            dcc.Interval(id="refresh-interval", interval=REFRESH_MS, n_intervals=0),
            dcc.Store(id="drawer-collapsed", data=False),
            dcc.Store(id="theme-mode", data="dark", storage_type="local"),
            dcc.Store(id="global-ui-state", data={}),
            dcc.Store(id="stream-status", data={"mode": "degraded", "notice": "MT5 Keep Alive is off. Stream is using cached/non-terminal data only."}),
            build_sidebar(),
            html.Div(
                [
                    build_toolbar(),
                    html.Div(id="dashboard-page", className="page-layout", children=[
                        html.Div(
                            id="status-summary-panel",
                            className="panel",
                            children="System Status",
                        ),
                        html.Div(
                            id="auto-trade-runtime-panel",
                            className="panel",
                            children="Auto-Trade Runtime",
                        ),
                        html.Div(
                            id="broker-management-panel",
                            className="panel",
                            children="Broker Snapshot",
                        ),
                        html.Div(
                            id="auto-trade-constraints-panel",
                            className="panel",
                            children="Auto-Trade Constraints",
                        ),
                        html.Div(
                            id="mt5-diagnostics-panel",
                            className="panel",
                            children="MT5 Diagnostics",
                        ),
                    ]),
                ],
                id="app-content", #
                className="app-content",
            ),
        ],
        id="app-shell",
        className="app-shell theme-dark",
    )


app.layout = build_layout() # Set the layout of the Dash app
register_strategy_callbacks(app) # Register strategy-related callbacks with the Dash app
register_navigation_callbacks(app) # Register navigation-related callbacks with the Dash app


if __name__ == "__main__":
    host, port, use_reloader = _dash_runtime_settings()
    debug = os.getenv("DASH_DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"}
    app.run(host=host, port=port, debug=debug, use_reloader=use_reloader)
