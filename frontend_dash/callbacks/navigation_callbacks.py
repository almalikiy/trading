from __future__ import annotations

from typing import Any

from dash import Dash, Input, Output, State

from frontend_dash.pages import render_overview_page, render_settings_page, render_strategy_page, render_transactions_page


def register_navigation_callbacks(app: Dash) -> None:
    @app.callback(
        Output("drawer-collapsed", "data"),
        Output("sidebar-drawer", "className"),
        Output("app-content", "className"),
        Input("drawer-toggle", "n_clicks"),
        State("drawer-collapsed", "data"),
        prevent_initial_call=True,
    )
    def toggle_drawer(_n_clicks: int | None, collapsed: bool | None):
        next_state = not bool(collapsed)
        sidebar_class = "sidebar-drawer collapsed" if next_state else "sidebar-drawer"
        content_class = "app-content collapsed" if next_state else "app-content"
        return next_state, sidebar_class, content_class

    @app.callback(
        Output("theme-mode", "data"),
        Input("theme-toggle", "n_clicks"),
        State("theme-mode", "data"),
        prevent_initial_call=True,
    )
    def toggle_theme(_n_clicks: int | None, current_mode: str | None):
        is_light = str(current_mode or "dark").lower() == "light"
        next_mode = "dark" if is_light else "light"
        return next_mode

    @app.callback(
        Output("app-shell", "className"),
        Output("theme-toggle", "children"),
        Input("theme-mode", "data"),
    )
    def apply_theme(current_mode: str | None):
        mode = str(current_mode or "dark").lower()
        if mode not in {"dark", "light"}:
            mode = "dark"
        shell_class = f"app-shell theme-{mode}"
        next_label = "Switch to Light" if mode == "dark" else "Switch to Dark"
        return shell_class, next_label

    @app.callback(
        Output("dashboard-page", "children"),
        Input("refresh-interval", "n_intervals"),
        Input("page-selector", "value"),
        Input("symbol-input", "value"),
        Input("timeframe-input", "value"),
        Input("bars-input", "value"),
    )
    def render_dashboard(_n: int, page: str | None, symbol: str | None, timeframe: str | None, bars: Any):
        page = page or "overview"
        if page == "strategy":
            return render_strategy_page()
        if page == "transactions":
            return render_transactions_page()
        if page == "settings":
            return render_settings_page()
        return render_overview_page(symbol, timeframe, bars)
