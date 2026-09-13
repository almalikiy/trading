from __future__ import annotations

from typing import Any

from dash import ALL, Dash, Input, Output, State, callback_context

from frontend_dash.api.client import api_delete, api_get, api_post, api_put, as_mapping
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
            signal_status = str(signal.get("status") or "degraded").lower()
            stream_ok = signal_status not in {"degraded", "error", "unavailable"}
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

    @app.callback(
        Output("broker-action-status", "children"),
        Input("broker-create-button", "n_clicks"),
        Input("broker-update-button", "n_clicks"),
        Input("broker-delete-button", "n_clicks"),
        State("broker-id-input", "value"),
        State("broker-name-input", "value"),
        State("broker-platform-input", "value"),
        State("broker-symbol-input", "value"),
        State("broker-terminal-path-input", "value"),
        prevent_initial_call=True,
    )
    def manage_broker(create_clicks: int | None, update_clicks: int | None, delete_clicks: int | None, broker_id_value: str | None, broker_name: str | None, broker_platform: str | None, default_symbol: str | None, terminal_path: str | None):
        try:
            trigger = callback_context.triggered_id if callback_context.triggered_id else None
            broker_id = int(broker_id_value) if broker_id_value not in (None, "") else None
            payload = {
                "name": (broker_name or "").strip(),
                "platform": broker_platform or "mt5",
                "default_symbol": (default_symbol or "").strip() or None,
                "terminal_path": (terminal_path or "").strip() or None,
            }
            if trigger == "broker-create-button":
                if not payload["name"]:
                    return "Broker name is required."
                result = api_post("/brokers", payload)
                broker = as_mapping(result).get("broker") if isinstance(result, dict) else None
                return f"Broker created: {as_mapping(broker).get('name', payload['name'])} • terminal path: {payload['terminal_path'] or '-'}"
            if trigger == "broker-update-button":
                if broker_id is None:
                    return "Enter a Broker ID to update an existing broker."
                result = api_put(f"/brokers/{broker_id}", payload)
                broker = as_mapping(result).get("broker") if isinstance(result, dict) else None
                return f"Broker updated: {as_mapping(broker).get('name', payload['name'])} • terminal path: {payload['terminal_path'] or '-'}"
            if trigger == "broker-delete-button":
                if broker_id is None:
                    return "Enter a Broker ID to delete an existing broker."
                api_delete(f"/brokers/{broker_id}")
                return f"Broker {broker_id} deleted."
            return "No broker action triggered."
        except Exception as exc:
            return f"Broker action failed: {exc}"

    @app.callback(
        Output("broker-action-status", "children"),
        Input({"type": "broker-launch-button", "index": ALL}, "n_clicks"),
        Input({"type": "broker-sync-button", "index": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def handle_broker_row_action(launch_clicks: list[int] | None, sync_clicks: list[int] | None):
        try:
            trigger = callback_context.triggered_id if callback_context.triggered_id else None
            if not isinstance(trigger, dict):
                return "No broker row action triggered."
            broker_id = trigger.get("index")
            action_name = trigger.get("type")
            if action_name == "broker-launch-button":
                result = api_post(f"/brokers/{broker_id}/launch_terminal")
                payload = as_mapping(result)
                started = bool(payload.get("started", False))
                if started:
                    return f"Broker {broker_id}: terminal launch started successfully."
                return f"Broker {broker_id}: terminal launch failed. {payload.get('message') or 'unknown error'}"
            if action_name == "broker-sync-button":
                result = api_post(f"/brokers/{broker_id}/sync", {"history_days": 90})
                payload = as_mapping(result)
                sync_result = as_mapping(payload.get("result"))
                if bool(sync_result.get("synced")):
                    return f"Broker {broker_id}: sync completed successfully."
                return f"Broker {broker_id}: sync status {payload.get('status', 'error')} • {sync_result.get('reason') or 'unknown reason'}"
            return "No broker row action triggered."
        except Exception as exc:
            return f"Broker action failed: {exc}"

    @app.callback(
        Output("broker-table", "selected_rows"),
        Input("broker-table", "data"),
        State("broker-table", "selected_rows"),
    )
    def select_default_broker_row(broker_rows: list[dict[str, Any]] | None, current_selection: list[int] | None):
        if not broker_rows:
            return []
        if current_selection and current_selection[0] < len(broker_rows):
            return current_selection
        default_index = None
        for idx, row in enumerate(broker_rows):
            payload = as_mapping(row)
            if bool(payload.get("is_default")):
                default_index = idx
                break
        if default_index is None and broker_rows:
            default_index = 0
        return [default_index] if default_index is not None else []

    @app.callback(
        Output("broker-id-input", "value"),
        Output("broker-name-input", "value"),
        Output("broker-platform-input", "value"),
        Output("broker-symbol-input", "value"),
        Output("broker-terminal-path-input", "value"),
        Input("broker-table", "selected_rows"),
        Input("broker-table", "data"),
        State("broker-id-input", "value"),
        State("broker-name-input", "value"),
        State("broker-platform-input", "value"),
        State("broker-symbol-input", "value"),
        State("broker-terminal-path-input", "value"),
    )
    def fill_broker_form(selected_rows: list[int] | None, broker_rows: list[dict[str, Any]] | None, current_id: str | None, current_name: str | None, current_platform: str | None, current_symbol: str | None, current_terminal_path: str | None):
        if not selected_rows or not broker_rows:
            if current_name or current_id or current_symbol or current_terminal_path:
                return current_id or "", current_name or "", current_platform or "mt5", current_symbol or "", current_terminal_path or ""
            return "", "MT5 Demo", "mt5", "XAUUSD", "D:/MetaQuotes/Terminal"
        index = selected_rows[0]
        row = broker_rows[index] if 0 <= index < len(broker_rows) else {}
        payload = as_mapping(row)
        return (
            str(payload.get("id", current_id or "") or current_id or ""),
            payload.get("name") or current_name or "",
            payload.get("platform") or current_platform or "mt5",
            payload.get("default_symbol") or current_symbol or "",
            payload.get("terminal_path") or current_terminal_path or "",
        )

    @app.callback(
        Output("mt5-diagnostics-panel-status", "children"),
        Input("clear-mt5-log-button", "n_clicks"),
        prevent_initial_call=True,
    )
    def clear_mt5_error_log(_n_clicks: int | None):
        try:
            api_post("/mt5/error_log/clear")
            return "MT5 error log cleared."
        except Exception as exc:
            return f"Failed to clear MT5 error log: {exc}"
