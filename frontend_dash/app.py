#file : frontend_dash/app.py
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


def build_layout() -> html.Div:  # Build the main layout of the Dash app
    return html.Div(
        [
            dcc.Interval(id="refresh-interval", interval=REFRESH_MS, n_intervals=0),
            dcc.Store(id="drawer-collapsed", data=False),
            dcc.Store(id="theme-mode", data="dark", storage_type="local"),
            build_sidebar(),
            html.Div(
                [
                    build_toolbar(),
                    html.Div(id="dashboard-page", className="page-layout"),
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
    app.run(host="0.0.0.0", port=8050, debug=True, use_reloader=True)
