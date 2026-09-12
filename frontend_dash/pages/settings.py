from __future__ import annotations

from dash import html
from dash.dash_table import DataTable

from frontend_dash.api.client import api_get, as_mapping


def _format_money(value):
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "-"


def render_settings_page():
    try:
        account = api_get("/account/state")
        brokers = api_get("/brokers", {"include_inactive": "true"})
        account_data = as_mapping(account)
        rows = brokers if isinstance(brokers, list) else []

        keep_alive_status = as_mapping(api_get("/account/keep_mt5_alive_status"))
        keep_alive_enabled = bool(keep_alive_status.get("enabled", bool(account_data.get("keep_terminal_alive", False))))
        keep_alive_mode = "ON" if keep_alive_enabled else "OFF"

        settings_cards = [
            html.Div([
                html.Div("Account", className="section-label"),
                html.Div(f"Balance: {_format_money(account_data.get('balance', 0.0))}", className="kv-line"),
                html.Div(f"Equity: {_format_money(account_data.get('equity', 0.0))}", className="kv-line"),
                html.Div(f"Lot: {account_data.get('lot', 0.01)}", className="kv-line"),
                html.Div(f"Max Open Trades: {account_data.get('max_open_trades', 1)}"),
            ], className="compact-panel"),
            html.Div([
                html.Div("Broker Defaults", className="section-label"),
                html.Div(f"Total Brokers: {len(rows)}", className="kv-line"),
                html.Div(f"Default Broker: {next((r.get('name', '-') for r in rows if r.get('is_default')), '-')}", className="kv-line"),
                html.Div(f"MT5 Mode: {'Enabled' if account_data.get('enable_real_trade') else 'Disabled'}"),
            ], className="compact-panel"),
            html.Div([
                html.Div("Execution", className="section-label"),
                html.Div("Trade Execution: Operational Controls", className="kv-line"),
                html.Div("Risk Guard: Active", className="kv-line"),
                html.Div("Alerts: Enabled"),
            ], className="compact-panel"),
            html.Div([
                html.Div("Keep MT5 Alive", className="section-label"),
                html.Div(f"Status: {keep_alive_mode} • {keep_alive_status.get('status', 'disabled').title()}", className="kv-line"),
            ], className="compact-panel"),
        ]

        brokers_table = DataTable(
            columns=[
                {"name": "Broker", "id": "name"},
                {"name": "Platform", "id": "platform"},
                {"name": "Default Symbol", "id": "default_symbol"},
                {"name": "Active", "id": "is_active"},
            ],
            data=[
                {
                    "name": as_mapping(item).get("name", "-"),
                    "platform": as_mapping(item).get("platform", "-"),
                    "default_symbol": as_mapping(item).get("default_symbol", "-"),
                    "is_active": "yes" if bool(as_mapping(item).get("is_active")) else "no",
                }
                for item in rows[:20]
            ],
            style_table={"overflowX": "auto"},
            style_cell={"padding": "8px"},
        )

        return html.Div([
            html.Div("Settings", className="section-label"),
            html.Div(settings_cards, className="settings-grid"),
            html.Div(
                [
                    html.Div("Broker List", className="section-label"),
                    html.Div(brokers_table, className="table-dark"),
                ],
                className="panel",
            ),
        ], className="page-layout")
    except Exception as exc:
        return html.Div([
            html.H3("Settings unavailable"),
            html.P(str(exc), className="error-text"),
        ], className="error-panel")
