from __future__ import annotations

from typing import Any

from dash import Dash, Input, Output, State

from frontend_dash.api.client import api_get, api_post, as_mapping
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
        Input("page-selector", "value"),
        Input("symbol-input", "value"),
        Input("timeframe-input", "value"),
        Input("bars-input", "value"),
    )
    def render_dashboard(page: str | None, symbol: str | None, timeframe: str | None, bars: Any):
        page = page or "overview"
        if page == "strategy":
            return render_strategy_page()
        if page == "transactions":
            return render_transactions_page()
        if page == "settings":
            return render_settings_page()
        return render_overview_page(symbol, timeframe, bars)

    @app.callback(
        Output("stream-status-badge", "children"),
        Output("stream-status-badge-dot", "className"),
        Output("stream-status-badge", "title"),
        Output("stream-status-detail", "children"),
        Output("toolbar-stream-status", "children"),
        Output("toolbar-stream-status-dot", "className"),
        Output("toolbar-stream-status", "title"),
        Output("toolbar-stream-detail", "children"),
        Input("refresh-interval", "n_intervals"),
        State("symbol-input", "value"),
    )
    def sync_stream_status(_n_intervals: int | None, symbol: str | None):
        try:
            keep_alive = as_mapping(api_get("/account/keep_mt5_alive_status"))
            enabled = bool(keep_alive.get("enabled", False))
            signal = as_mapping(api_get("/signal", {"symbol": symbol or "XAUUSD", "mode": "real"}))
            stream_ok = not enabled or bool(signal.get("status") not in {"degraded", "error"})
            badge_label = "LIVE" if stream_ok else "DEGRADED"
            badge_class = "status-dot pill-sync-running" if stream_ok else "status-dot pill-sync-queued"
            notice = str(signal.get("notice") or ("MT5 Keep Alive is on." if enabled else "MT5 Keep Alive is off. Stream is using cached/non-terminal data only."))
            detail = notice
            return badge_label, badge_class, detail, detail, "LIVE MODE" if stream_ok else "DEGRADED MODE", badge_class, detail, detail
        except Exception:
            fallback = "MT5 Keep Alive is off. Stream is using cached/non-terminal data only."
            return "DEGRADED", "status-dot pill-sync-queued", fallback, fallback, "DEGRADED MODE", "status-dot pill-sync-queued", fallback, fallback

    @app.callback(
        Output("keep-mt5-alive-toolbar-button", "children"),
        Output("keep-mt5-alive-toolbar-status", "children"),
        Input("keep-mt5-alive-toolbar-button", "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_keep_mt5_alive(_n_clicks: int | None):
        try:
            current = as_mapping(api_get("/account/keep_mt5_alive_status"))
            enabled = bool(current.get("enabled", False))
            next_enabled = not enabled
            response = api_post("/account/set_keep_terminal_alive", {"enabled": next_enabled})
            actual = bool(as_mapping(response).get("keep_terminal_alive", next_enabled))
            status = as_mapping(api_get("/account/keep_mt5_alive_status"))
            label = "Disable Keep MT5 Alive" if actual else "Enable Keep MT5 Alive"
            detail = f"MT5 Keep Alive: {'ON' if actual else 'OFF'} • {str(status.get('status', 'disabled')).title()}"
            return label, detail
        except Exception as exc:
            return "Enable Keep MT5 Alive", f"MT5 Keep Alive: failed • {exc}"

    @app.callback(
        Output("confirm-mt5-operation-button", "children"),
        Output("confirm-mt5-operation-status", "children"),
        Input("confirm-mt5-operation-button", "n_clicks"),
        prevent_initial_call=True,
    )
    def confirm_mt5_operation(_n_clicks: int | None):
        try:
            response = api_post(
                "/account/confirm_mt5_operation",
                {"call_name": "manual_operational_check", "confirm": True, "approved": True},
            )
            payload = as_mapping(response)
            confirmed = bool(payload.get("confirmed", False))
            label = "MT5 Check Approved" if confirmed else "Confirm MT5 Operational Check"
            detail = "MT5 Operational Check: Approved" if confirmed else "MT5 Operational Check: Pending"
            if payload.get("message"):
                detail = f"MT5 Operational Check: {payload.get('message')}"
            return label, detail
        except Exception as exc:
            return "Confirm MT5 Operational Check", f"MT5 Operational Check: failed • {exc}"
