from __future__ import annotations

from dash import dcc, html
from dash.dash_table import DataTable

from frontend_dash.api.client import api_get, as_mapping


def _format_money(value):
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "-"


def render_settings_page(global_state: dict | None = None):
    state = as_mapping(global_state) if isinstance(global_state, dict) else {}
    try:
        if state:
            account = state.get("account")
            brokers = state.get("brokers")
            keep_alive_status = state.get("keep_alive_status")
            database_status = state.get("database_status")
        else:
            account = api_get("/account/state")
            brokers = api_get("/brokers", {"include_inactive": "true"})
            keep_alive_status = api_get("/account/keep_mt5_alive_status")
            database_status = api_get("/health/database")
        account_data = as_mapping(account)
        rows = brokers if isinstance(brokers, list) else []

        keep_alive_status = as_mapping(keep_alive_status)
        keep_alive_enabled = bool(keep_alive_status.get("enabled", bool(account_data.get("keep_terminal_alive", False))))
        keep_alive_mode = "ON" if keep_alive_enabled else "OFF"

        database_status = as_mapping(database_status)
        backend_name = "PostgreSQL"
        status_value = str(database_status.get("status", "healthy")).title()

        default_broker_name = next((as_mapping(r).get("name", "-") for r in rows if bool(as_mapping(r).get("is_default"))), "-")

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
                html.Div(f"Default Broker: {default_broker_name}", className="kv-line"),
                html.Div(f"MT5 Mode: {'Enabled' if account_data.get('enable_real_trade') else 'Disabled'}"),
            ], className="compact-panel"),
            html.Div([
                html.Div("Data Layer", className="section-label"),
                html.Div(f"Backend: {backend_name}", className="kv-line"),
                html.Div(f"Status: {status_value}", className="kv-line"),
                html.Div(f"Reset Policy: clean PostgreSQL runtime"),
                html.Div(f"MT5 Keep Alive: {keep_alive_mode} • {keep_alive_status.get('status', 'disabled').title()}", className="kv-line"),
            ], className="compact-panel"),
        ]

        account_controls_panel = html.Div(
            [
                html.Div("Account Controls", className="section-label"),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Label("Deposit / Withdraw", className="field-label"),
                                dcc.Input(id="account-adjustment-amount", type="number", value="0", className="strategy-parameter-input"),
                                html.Div(
                                    [
                                        html.Button("Deposit", className="action-button buy", n_clicks=0),
                                        html.Button("Withdraw", className="action-button sell", n_clicks=0),
                                    ],
                                    className="action-row",
                                ),
                            ],
                            className="compact-panel",
                        ),
                        html.Div(
                            [
                                html.Label("Lot Size", className="field-label"),
                                dcc.Input(id="account-lot-input", type="number", value=str(account_data.get("lot", 0.01)), step="0.01", className="strategy-parameter-input"),
                                html.Button("Apply Lot", className="action-button neutral", n_clicks=0),
                            ],
                            className="compact-panel",
                        ),
                        html.Div(
                            [
                                html.Label("Max Open Trades", className="field-label"),
                                dcc.Input(id="account-max-open-trades", type="number", value=str(account_data.get("max_open_trades", 1)), min="1", step="1", className="strategy-parameter-input"),
                                html.Button("Apply Max Open Trades", className="action-button neutral", n_clicks=0),
                            ],
                            className="compact-panel",
                        ),
                    ],
                    className="settings-grid",
                ),
            ],
            id="account-controls-panel",
            className="panel",
        )

        risk_config_panel = html.Div(
            [
                html.Div("Risk Configuration", className="section-label"),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Label("Risk %", className="field-label"),
                                dcc.Input(id="risk-percent-input", type="number", value=str(account_data.get("auto_trade_risk_percent", 1.0)), min="0", step="0.1", className="strategy-parameter-input"),
                            ],
                            className="compact-panel",
                        ),
                        html.Div(
                            [
                                html.Label("Feed Broker", className="field-label"),
                                dcc.Dropdown(
                                    id="feed-broker-selector",
                                    options=[{"label": as_mapping(item).get("name", "Broker"), "value": str(as_mapping(item).get("id", ""))} for item in rows if as_mapping(item).get("id") is not None],
                                    value=str(account_data.get("data_feed_broker_id", "")) if account_data.get("data_feed_broker_id") is not None else None,
                                    clearable=False,
                                    searchable=False,
                                    className="strategy-parameter-input",
                                ),
                            ],
                            className="compact-panel",
                        ),
                        html.Div(
                            [
                                html.Label("Auto-trade Config", className="field-label"),
                                html.Div(
                                    [
                                        html.Button("Save Risk Settings", className="action-button neutral", n_clicks=0),
                                        html.Button("Enable Auto Trade", className="action-button buy", n_clicks=0),
                                    ],
                                    className="action-row",
                                ),
                            ],
                            className="compact-panel",
                        ),
                    ],
                    className="settings-grid",
                ),
            ],
            id="risk-config-panel",
            className="panel",
        )

        broker_crud_panel = html.Div(
            [
                html.Div("Broker CRUD", className="section-label"),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Label("Broker ID", className="field-label"),
                                dcc.Input(id="broker-id-input", type="number", value="", placeholder="Broker ID for update/delete", className="strategy-parameter-input"),
                                html.Label("Broker Name", className="field-label"),
                                dcc.Input(id="broker-name-input", type="text", value="MT5 Demo", className="strategy-parameter-input"),
                                html.Label("Platform", className="field-label"),
                                dcc.Dropdown(id="broker-platform-input", options=[{"label": "MT5", "value": "mt5"}, {"label": "MT4", "value": "mt4"}], value="mt5", clearable=False, searchable=False),
                                html.Label("Default Symbol", className="field-label"),
                                dcc.Input(id="broker-symbol-input", type="text", value="XAUUSD", className="strategy-parameter-input"),
                                html.Label("Terminal Path", className="field-label"),
                                dcc.Input(
                                    id="broker-terminal-path-input",
                                    type="text",
                                    value="D:/MetaQuotes/Terminal",
                                    placeholder="D:/MetaQuotes/Terminal",
                                    className="strategy-parameter-input",
                                ),
                            ],
                            className="compact-panel",
                        ),
                        html.Div(
                            [
                                html.Button("Create Broker", id="broker-create-button", className="action-button neutral", n_clicks=0),
                                html.Button("Update Selected Broker", id="broker-update-button", className="action-button buy", n_clicks=0),
                                html.Button("Delete Selected Broker", id="broker-delete-button", className="action-button sell", n_clicks=0),
                            ],
                            className="action-row",
                        ),
                        html.Div(id="broker-action-status", className="kv-line"),
                    ],
                    className="settings-grid",
                ),
            ],
            id="broker-crud-panel",
            className="panel",
        )

        sync_settings_panel = html.Div(
            [
                html.Div("Trade Sync Settings", className="section-label"),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Label("Sync all history", className="field-label"),
                                dcc.Checklist(id="sync-all-history", options=[{"label": "Sync all", "value": "all"}], value=[]),
                            ],
                            className="compact-panel",
                        ),
                        html.Div(
                            [
                                html.Label("Recent days", className="field-label"),
                                dcc.Input(id="trade-sync-days", type="number", value="90", min="1", step="1", className="strategy-parameter-input"),
                            ],
                            className="compact-panel",
                        ),
                        html.Button("Apply Sync Settings", className="action-button neutral", n_clicks=0),
                    ],
                    className="settings-grid",
                ),
            ],
            id="sync-settings-panel",
            className="panel",
        )

        ml_export_panel = html.Div(
            [
                html.Div("ML Export & Training", className="section-label"),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Label("Dataset window", className="field-label"),
                                dcc.Input(id="ml-dataset-window", type="number", value="90", min="1", className="strategy-parameter-input"),
                            ],
                            className="compact-panel",
                        ),
                        html.Div(
                            [
                                html.Label("Export format", className="field-label"),
                                dcc.Dropdown(id="ml-export-format", options=[{"label": "JSON", "value": "json"}, {"label": "CSV", "value": "csv"}], value="json", clearable=False, searchable=False),
                            ],
                            className="compact-panel",
                        ),
                        html.Div(
                            [
                                html.Button("Train Model", className="action-button buy", n_clicks=0),
                                html.Button("Export Dataset", className="action-button neutral", n_clicks=0),
                                html.Button("Download Export", className="action-button sell", n_clicks=0),
                            ],
                            className="action-row",
                        ),
                    ],
                    className="settings-grid",
                ),
            ],
            id="ml-export-panel",
            className="panel",
        )

        brokers_table = DataTable(
            id="broker-table",
            columns=[
                {"name": "ID", "id": "id", "hidden": True},
                {"name": "Broker", "id": "name"},
                {"name": "Platform", "id": "platform"},
                {"name": "Default Symbol", "id": "default_symbol"},
                {"name": "Terminal Path", "id": "terminal_path"},
                {"name": "Active", "id": "is_active"},
            ],
            data=[
                {
                    "id": as_mapping(item).get("id", ""),
                    "name": as_mapping(item).get("name", "-"),
                    "platform": as_mapping(item).get("platform", "-"),
                    "default_symbol": as_mapping(item).get("default_symbol", "-"),
                    "terminal_path": as_mapping(item).get("terminal_path") or "-",
                    "is_active": "yes" if bool(as_mapping(item).get("is_active")) else "no",
                }
                for item in rows[:20]
            ],
            row_selectable="single",
            selected_rows=[],
            style_table={"overflowX": "auto"},
            style_cell={"padding": "8px"},
        )

        broker_action_panel = html.Div(
            [
                html.Div("Broker Actions", className="section-label"),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div(f"{as_mapping(item).get('name', '-')} • {as_mapping(item).get('platform', '-')} ", className="kv-line"),
                                html.Div(
                                    [
                                        html.Button(
                                            "Launch MT5 Terminal",
                                            id={"type": "broker-launch-button", "index": int(as_mapping(item).get("id", -1))},
                                            className="action-button neutral",
                                            n_clicks=0,
                                        ),
                                        html.Button(
                                            "Sync Account / Transactions",
                                            id={"type": "broker-sync-button", "index": int(as_mapping(item).get("id", -1))},
                                            className="action-button buy",
                                            n_clicks=0,
                                        ),
                                    ],
                                    className="action-row",
                                ),
                            ],
                            className="compact-panel",
                        )
                        for item in rows[:20]
                        if as_mapping(item).get("id") is not None
                    ],
                    className="settings-grid",
                ),
            ],
            className="panel",
        )

        return html.Div([
            html.Div("Settings", className="section-label"),
            html.Div(settings_cards, className="settings-grid"),
            account_controls_panel,
            risk_config_panel,
            sync_settings_panel,
            ml_export_panel,
            broker_crud_panel,
            html.Div(
                [
                    html.Div("Broker List", className="section-label"),
                    html.Div(brokers_table, className="table-dark"),
                    broker_action_panel,
                ],
                className="panel",
            ),
        ], className="page-layout")
    except Exception as exc:
        fallback = html.Div(
            [
                html.Div("Settings", className="section-label"),
                html.Div(
                    [
                        html.Div("Account Controls", className="section-label"),
                        html.Div("Backend unavailable", className="kv-line"),
                    ],
                    id="account-controls-panel",
                    className="panel",
                ),
                html.Div(
                    [
                        html.Div("Risk Configuration", className="section-label"),
                        html.Div("Backend unavailable", className="kv-line"),
                    ],
                    id="risk-config-panel",
                    className="panel",
                ),
                html.Div(
                    [
                        html.H3("Settings unavailable"),
                        html.P(str(exc), className="error-text"),
                    ],
                    className="error-panel",
                ),                html.Div(
                    [
                        html.Div("Broker CRUD", className="section-label"),
                        html.Div("Backend unavailable", className="kv-line"),
                    ],
                    id="broker-crud-panel",
                    className="panel",
                ),
                html.Div(
                    [
                        html.Div("Trade Sync Settings", className="section-label"),
                        html.Div("Backend unavailable", className="kv-line"),
                    ],
                    id="sync-settings-panel",
                    className="panel",
                ),
                html.Div(
                    [
                        html.Div("ML Export & Training", className="section-label"),
                        html.Div("Backend unavailable", className="kv-line"),
                    ],
                    id="ml-export-panel",
                    className="panel",
                ),            ],
            className="page-layout",
        )
        return fallback
