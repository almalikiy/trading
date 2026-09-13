from __future__ import annotations

from typing import Any

from dash import ALL, Dash, Input, Output, State, callback_context

from frontend_dash.api.client import api_delete, api_get, api_post, api_put, as_mapping
from frontend_dash.pages import render_overview_page, render_settings_page, render_strategy_page, render_transactions_page
from frontend_dash.state import resolve_stream_state


def resolve_keep_alive_state(status_payload: dict[str, Any] | Any) -> tuple[str, str]:
    payload = as_mapping(status_payload)
    enabled = bool(payload.get("enabled", False))
    status = str(payload.get("status", "disabled")).title()
    button = "Disable Keep MT5 Alive" if enabled else "Enable Keep MT5 Alive"
    detail = f"MT5 Keep Alive: {'ON' if enabled else 'OFF'} • {status}"
    return button, detail


def register_navigation_callbacks(app: Dash) -> None:
    @app.callback(
        Output("global-ui-state", "data"),
        Input("refresh-interval", "n_intervals"),
        State("symbol-input", "value"),
        prevent_initial_call=False,
    )
    def sync_global_ui_state(_n_intervals: int | None, symbol: str | None):
        state: dict[str, Any] = {}
        try:
            summary = as_mapping(api_get("/dashboard/summary"))
            state["summary"] = summary
        except Exception:
            state["summary"] = {"brokers": []}
        try:
            account = as_mapping(api_get("/account/state"))
            state["account"] = account
        except Exception:
            state["account"] = {"balance": 0.0, "equity": 0.0}
        try:
            positions = api_get("/positions")
            state["positions"] = positions if isinstance(positions, list) else []
        except Exception:
            state["positions"] = []
        try:
            signal = as_mapping(api_get("/signal", {"symbol": symbol or "XAUUSD", "mode": "real"}))
            state["signal"] = signal
        except Exception:
            state["signal"] = {"signal": "wait", "status": "degraded", "notice": "MT5 Keep Alive is off. Stream is using cached/non-terminal data only."}
        try:
            candles = api_get("/ohlcv", {"symbol": symbol or "XAUUSD", "timeframe": "M5", "bars": 100})
            state["candles"] = candles if isinstance(candles, list) else []
        except Exception:
            state["candles"] = []
        try:
            broker_default = as_mapping(api_get("/brokers/default"))
            state["default_broker"] = broker_default
        except Exception:
            state["default_broker"] = {}
        try:
            mt5_status = as_mapping(api_get("/mt5/status"))
            state["mt5_status"] = mt5_status
        except Exception:
            state["mt5_status"] = {"connected": False}
        try:
            background_sync = as_mapping(api_get("/mt5/background_sync_status"))
            state["background_sync"] = background_sync
        except Exception:
            state["background_sync"] = {"sync_status": "idle"}
        try:
            health = as_mapping(api_get("/account/auto_trade_health"))
            state["auto_trade_health"] = health
            state["auto_trade_enabled"] = bool(health.get("auto_trade_enabled", False))
            state["live_mode"] = bool(health.get("real_trade_enabled", False) or health.get("enable_real_trade", False))
        except Exception:
            state["auto_trade_health"] = {"auto_trade_enabled": False, "checks": []}
            state["auto_trade_enabled"] = False
            state["live_mode"] = False
        try:
            runtime = as_mapping(api_get("/account/auto_trade_runtime"))
            state["auto_trade_runtime"] = runtime
        except Exception:
            state["auto_trade_runtime"] = {}
        try:
            brokers = api_get("/brokers", {"include_inactive": "true"})
            state["brokers"] = brokers if isinstance(brokers, list) else []
        except Exception:
            state["brokers"] = []
        try:
            constraints = as_mapping(api_get("/account/auto_trade_constraints"))
            state["auto_trade_constraints"] = constraints
        except Exception:
            state["auto_trade_constraints"] = {"constraints": {}}
        try:
            stats = as_mapping(api_get("/account/auto_trade_stats", {"window_days": 30}))
            state["auto_trade_stats"] = stats
        except Exception:
            state["auto_trade_stats"] = {"stats": {}}
        try:
            events = as_mapping(api_get("/account/auto_trade_events", {"limit": 10}))
            state["auto_trade_events"] = events
        except Exception:
            state["auto_trade_events"] = {"events": []}
        try:
            mt5_error_log = as_mapping(api_get("/mt5/error_log", {"limit": 8}))
            state["mt5_error_log"] = mt5_error_log
        except Exception:
            state["mt5_error_log"] = {"errors": []}
        try:
            mt5_error_log_summary = as_mapping(api_get("/mt5/error_log_summary", {"limit": 200}))
            state["mt5_error_log_summary"] = mt5_error_log_summary
        except Exception:
            state["mt5_error_log_summary"] = {"errors": []}
        try:
            keep_alive = as_mapping(api_get("/account/keep_mt5_alive_status"))
            state["keep_alive_status"] = keep_alive
            state["keep_mt5_alive_enabled"] = bool(keep_alive.get("enabled", False))
        except Exception:
            state["keep_alive_status"] = {"enabled": False, "status": "disabled"}
            state["keep_mt5_alive_enabled"] = False
        try:
            state["database_status"] = as_mapping(api_get("/health/database"))
        except Exception:
            state["database_status"] = {"status": "unknown"}
        state["mt5_terminal_state"] = "connected" if bool(state.get("mt5_status", {}).get("connected") or state.get("mt5_status", {}).get("ready")) else "open" if bool(state.get("mt5_status", {}).get("terminal_process_running") or state.get("mt5_status", {}).get("manual_terminal_detected") or state.get("mt5_status", {}).get("terminal_open")) else "offline"
        state["signal_status"] = str(state.get("signal", {}).get("status") or "degraded").lower()
        state["signal_notice"] = str(state.get("signal", {}).get("notice") or "")
        mode, badge, notice = resolve_stream_state(
            signal_status=state.get("signal_status"),
            keep_alive_enabled=bool(state.get("keep_mt5_alive_enabled", False)),
            mt5_terminal_state=state.get("mt5_terminal_state"),
            signal_notice=state.get("signal_notice"),
        )
        state["stream_mode"] = mode
        state["stream_badge"] = badge
        state["stream_notice"] = notice
        return state

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
        Input("global-ui-state", "data"),
        Input("refresh-interval", "n_intervals"),
    )
    def render_dashboard(page: str | None, symbol: str | None, timeframe: str | None, bars: Any, global_state: dict[str, Any] | None, _n_intervals: int | None):
        page = page or "overview"
        if page == "strategy":
            return render_strategy_page()
        if page == "transactions":
            return render_transactions_page()
        if page == "settings":
            return render_settings_page(global_state)
        return render_overview_page(symbol, timeframe, bars, global_state)

    @app.callback(
        Output("stream-status-badge", "children"),
        Output("stream-status-badge-dot", "className"),
        Output("stream-status-badge", "title"),
        Output("stream-status-detail", "children"),
        Output("toolbar-stream-status", "children"),
        Output("toolbar-stream-status-dot", "className"),
        Output("toolbar-stream-status", "title"),
        Output("toolbar-stream-detail", "children"),
        Input("global-ui-state", "data"),
        Input("refresh-interval", "n_intervals"),
        State("symbol-input", "value"),
    )
    def sync_stream_status(_global_state: dict[str, Any] | None, _n_intervals: int | None, symbol: str | None):
        try:
            state = as_mapping(_global_state)
            if not state:
                state = as_mapping(api_get("/account/keep_mt5_alive_status"))
            signal_status = str(state.get("signal_status") or "degraded").lower()
            keep_alive_enabled = bool(state.get("keep_mt5_alive_enabled", False))
            mt5_terminal_state = state.get("mt5_terminal_state", "offline")
            stream_mode, badge_label, notice = resolve_stream_state(
                signal_status=signal_status,
                keep_alive_enabled=keep_alive_enabled,
                mt5_terminal_state=mt5_terminal_state,
                signal_notice=state.get("signal_notice"),
            )
            badge_class = "status-dot pill-sync-running" if stream_mode == "live" else "status-dot pill-sync-queued"
            detail = notice
            return badge_label, badge_class, detail, detail, "LIVE MODE" if stream_mode == "live" else "DEGRADED MODE", badge_class, detail, detail
        except Exception:
            fallback = "MT5 Keep Alive is off. Stream is using cached/non-terminal data only."
            return "DEGRADED", "status-dot pill-sync-queued", fallback, fallback, "DEGRADED MODE", "status-dot pill-sync-queued", fallback, fallback

    @app.callback(
        Output("keep-mt5-alive-toolbar-button", "children"),
        Output("keep-mt5-alive-toolbar-status", "children"),
        Input("keep-mt5-alive-toolbar-button", "n_clicks"),
        Input("global-ui-state", "data"),
        prevent_initial_call=False,
    )
    def toggle_keep_mt5_alive(_n_clicks: int | None, global_state: dict[str, Any] | None):
        try:
            state = as_mapping(global_state)
            enabled = bool(state.get("keep_mt5_alive_enabled", False))
            if callback_context.triggered_id == "keep-mt5-alive-toolbar-button" and _n_clicks not in (None, 0):
                next_enabled = not enabled
                api_post("/account/set_keep_terminal_alive", {"enabled": next_enabled})
                enabled = next_enabled
            payload = {"enabled": enabled, "status": "ok" if enabled else "disabled"}
            return resolve_keep_alive_state(payload)
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
        Input({"type": "broker-launch-button", "index": ALL}, "n_clicks"),
        Input({"type": "broker-sync-button", "index": ALL}, "n_clicks"),
        State("broker-id-input", "value"),
        State("broker-name-input", "value"),
        State("broker-platform-input", "value"),
        State("broker-symbol-input", "value"),
        State("broker-terminal-path-input", "value"),
        prevent_initial_call=True,
    )
    def manage_broker(create_clicks: int | None, update_clicks: int | None, delete_clicks: int | None, launch_clicks: list[int] | None, sync_clicks: list[int] | None, broker_id_value: str | None, broker_name: str | None, broker_platform: str | None, default_symbol: str | None, terminal_path: str | None):
        try:
            trigger = callback_context.triggered_id if callback_context.triggered_id else None
            if isinstance(trigger, dict):
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
        index = selected_rows[0] if isinstance(selected_rows, list) and selected_rows else None
        if index is None:
            return current_id or "", current_name or "", current_platform or "mt5", current_symbol or "", current_terminal_path or ""
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
