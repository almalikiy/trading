import os
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import requests
from dash import ALL, Dash, Input, Output, State, dcc, html
from dash.dash_table import DataTable
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8002")
REFRESH_MS = int(os.getenv("REFRESH_MS", "5000"))
DEFAULT_SYMBOL = "XAUUSD"
DEFAULT_TIMEFRAME = "M1"
DEFAULT_BARS = 60

app = Dash(__name__, title="Trading Dashboard", suppress_callback_exceptions=True)
app.index_string = """<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            body {
                background: #020817;
                color: #e5e7eb;
                font-family: Arial, sans-serif;
            }
            .app-shell {
                min-height: 100vh;
                background: linear-gradient(180deg, #020817, #111827);
                padding: 24px;
            }
            .page-layout {
                max-width: 1500px;
                margin: 0 auto;
                display: flex;
                flex-direction: column;
                gap: 18px;
            }
            .topbar {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 8px;
            }
            .page-nav {
                display: flex;
                align-items: center;
                gap: 10px;
                flex-wrap: wrap;
            }
            .page-nav .dash-radio {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
            }
            .page-nav .dash-radio input {
                display: none;
            }
            .page-nav .dash-radio label {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-width: 110px;
                padding: 9px 14px;
                border-radius: 999px;
                cursor: pointer;
                border: 1px solid #243248;
                background: rgba(30, 41, 59, 0.72);
                color: #dbeafe;
                font-size: 0.75rem;
                font-weight: 700;
                letter-spacing: 0.04em;
                text-transform: uppercase;
            }
            .page-nav .dash-radio input:checked + label {
                background: linear-gradient(135deg, rgba(59, 130, 246, 0.28), rgba(168, 85, 247, 0.18));
                border-color: rgba(96, 165, 250, 0.7);
                box-shadow: inset 0 0 0 1px rgba(147, 197, 253, 0.4);
            }
            .main-title {
                font-size: 2.1rem;
                font-weight: 700;
                letter-spacing: 0.04em;
            }
            .panel {
                background: rgba(15, 23, 42, 0.9);
                border: 1px solid #243248;
                border-radius: 14px;
                padding: 14px 16px;
                box-shadow: 0 10px 25px rgba(0,0,0,0.18);
            }
            .compact-panel {
                background: rgba(15, 23, 42, 0.9);
                border: 1px solid #243248;
                border-radius: 12px;
                padding: 12px 14px;
            }
            .section-label {
                font-size: 0.75rem;
                text-transform: uppercase;
                letter-spacing: 0.12em;
                color: #93c5fd;
                margin-bottom: 12px;
                font-weight: 700;
            }
            .small-muted {
                color: #94a3b8;
                font-size: 0.8rem;
            }
            .metrics-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 16px;
            }
            .metric-card {
                background: rgba(15, 23, 42, 0.9);
                border: 1px solid #243248;
                border-radius: 12px;
                padding: 16px 18px;
            }
            .metric-label {
                color: #a8b5c8;
                font-size: 0.72rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
            }
            .signal-box {
                display: flex;
                flex-direction: column;
                gap: 8px;
                padding: 14px;
                border-radius: 12px;
                background: rgba(15, 23, 42, 0.9);
                border: 1px solid #243248;
                min-height: 120px;
                justify-content: center;
            }
            .mini-stack {
                margin-top: 12px;
                color: #dbeafe;
                display: grid;
                gap: 8px;
            }
            .two-col {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
                gap: 16px;
            }
            .overview-split {
                display: grid;
                grid-template-columns: 1fr;
                gap: 16px;
                align-items: start;
                width: 100%;
            }
            .toolbar {
                display: flex;
                flex-wrap: wrap;
                align-items: end;
                gap: 12px;
            }
            .toolbar label {
                color: #cbd5e1;
                font-size: 0.82rem;
                font-weight: 600;
                margin-right: 8px;
            }
            .nav-panel {
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 18px;
                background: rgba(15, 23, 42, 0.9);
                border: 1px solid #243248;
                border-radius: 16px;
                padding: 14px 18px;
                box-shadow: 0 16px 32px rgba(15, 23, 42, 0.28);
            }
            .brand {
                display: flex;
                align-items: center;
                gap: 12px;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                color: #f8fafc;
            }
            .brand-mark {
                width: 10px;
                height: 10px;
                border-radius: 50%;
                background: linear-gradient(135deg, #22c55e, #38bdf8);
                box-shadow: 0 0 18px rgba(56, 189, 248, 0.7);
            }
            .nav-pills {
                display: flex;
                flex-wrap: wrap;
                align-items: center;
                gap: 8px;
            }
            .nav-pill {
                padding: 8px 12px;
                border-radius: 999px;
                font-size: 0.75rem;
                border: 1px solid #243248;
                background: rgba(30, 41, 59, 0.75);
                color: #dbeafe;
            }
            .nav-pill.active {
                background: linear-gradient(135deg, rgba(59, 130, 246, 0.3), rgba(168, 85, 247, 0.18));
                border-color: rgba(96, 165, 250, 0.55);
            }
            .action-row {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-top: 10px;
            }
            .action-button {
                border: none;
                border-radius: 10px;
                padding: 10px 14px;
                font-weight: 700;
                letter-spacing: 0.02em;
                cursor: pointer;
            }
            .action-button.buy { background: linear-gradient(135deg, #22c55e, #16a34a); color: white; }
            .action-button.sell { background: linear-gradient(135deg, #f97316, #ef4444); color: white; }
            .action-button.neutral { background: rgba(59, 130, 246, 0.18); color: #dbeafe; border: 1px solid rgba(96, 165, 250, 0.4); }
            .status-row {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-top: 10px;
            }
            .status-pill {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                padding: 8px 12px;
                border-radius: 999px;
                background: rgba(15, 23, 42, 0.8);
                border: 1px solid #243248;
                color: #dbeafe;
                font-size: 0.74rem;
                font-weight: 600;
            }
            .status-dot {
                width: 9px;
                height: 9px;
                border-radius: 50%;
                display: inline-block;
            }
            .info-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                gap: 18px;
            }
            .info-card {
                background: rgba(15, 23, 42, 0.9);
                border: 1px solid #243248;
                border-radius: 12px;
                padding: 18px;
            }
            .error-panel {
                background: rgba(69, 10, 10, 0.85);
                border: 1px solid rgba(248, 113, 113, 0.7);
                border-radius: 14px;
                padding: 16px;
                color: #fef2f2;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
"""


def api_get(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{BACKEND_URL.rstrip('/')}{path}"
    response = requests.get(url, params=params or {}, timeout=15)
    if response.status_code >= 400:
        raise RuntimeError(f"{path} failed: {response.status_code} {response.text[:200]}")
    try:
        payload = response.json()
        if isinstance(payload, (dict, list, str, int, float, bool)) or payload is None:
            return payload
        return {}
    except ValueError:
        return response.text


def api_post(path: str, payload: dict[str, Any] | None = None) -> Any:
    url = f"{BACKEND_URL.rstrip('/')}{path}"
    response = requests.post(url, json=payload or {}, timeout=15)
    if response.status_code >= 400:
        raise RuntimeError(f"{path} failed: {response.status_code} {response.text[:200]}")
    try:
        return response.json()
    except ValueError:
        return response.text


def as_mapping(value: Any, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return default if isinstance(default, dict) else {}


def signal_color(value: str) -> str:
    if value == "buy":
        return "#2ecc71"
    if value == "sell":
        return "#ff5c7a"
    return "#95a5a6"


def format_money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "-"


def format_number(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):,.{digits}f}"
    except Exception:
        return "-"


def build_figure(candles: list[dict[str, Any]]) -> go.Figure:
    if not candles:
        fig = go.Figure()
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0b1220",
            plot_bgcolor="#0b1220",
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor="#243248"),
        )
        fig.add_annotation(text="No OHLCV data", x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False)
        return fig

    df = pd.DataFrame(candles)
    df["time"] = pd.to_datetime(df["time"], unit="s", errors="coerce")
    df = df.dropna(subset=["time"]).sort_values("time")
    fig = go.Figure(
        data=[
            go.Candlestick(
                x=df["time"],
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                increasing_line_color="#2ecc71",
                decreasing_line_color="#ff5c7a",
                increasing_fillcolor="#2ecc71",
                decreasing_fillcolor="#ff5c7a",
                whiskerwidth=0.6,
            )
        ]
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(
            title="Time",
            rangeslider=dict(visible=False),
            showgrid=False,
        ),
        yaxis=dict(
            title="Price",
            showgrid=True,
            gridcolor="#243248",
        ),
        font=dict(color="#e5e7eb"),
    )
    return fig


def safe_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
        return max(1, parsed)
    except (TypeError, ValueError):
        return default


def build_strategy_parameter_inputs(strategy_name: str | None) -> html.Div:
    try:
        strategies_payload = api_get("/strategies/list")
        strategies = strategies_payload.get("strategies", []) if isinstance(strategies_payload, dict) else []
        selected = next((item for item in strategies if item.get("name") == strategy_name), None)
        if selected is None and strategies:
            selected = strategies[0]
        schema = selected.get("parameters_schema", {}) if isinstance(selected, dict) else {}
        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        if not properties:
            return html.Div("No additional parameters for this strategy.", className="small-muted")

        children: list[Any] = []
        for key, spec in properties.items():
            default_value = selected.get("default_parameters", {}).get(key) if isinstance(selected, dict) else None
            field_type = spec.get("type", "string")
            if field_type in {"integer", "number"}:
                field = dcc.Input(
                    id={"type": "strategy-parameter", "index": key},
                    type="number",
                    value=default_value if default_value is not None else 0,
                    style={"width": "100%", "minWidth": "120px", "color": "#0f172a"},
                )
            else:
                field = dcc.Input(
                    id={"type": "strategy-parameter", "index": key},
                    type="text",
                    value=str(default_value) if default_value is not None else "",
                    style={"width": "100%", "minWidth": "120px", "color": "#0f172a"},
                )
            children.append(
                html.Div(
                    [
                        html.Label(key.replace("_", " ").title(), style={"display": "block", "marginBottom": "6px", "color": "#dbeafe"}),
                        field,
                    ],
                    style={"display": "grid", "gap": "8px", "marginBottom": "12px"},
                )
            )
        return html.Div(children, style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(180px, 1fr))", "gap": "16px"})
    except Exception:
        return html.Div("Unable to load strategy parameters.", className="small-muted")


def render_overview_page(symbol: str | None, timeframe: str | None, bars: Any):
    symbol = (symbol or DEFAULT_SYMBOL).upper()
    timeframe = timeframe or DEFAULT_TIMEFRAME
    bars = safe_int(bars, DEFAULT_BARS)

    try:
        summary = api_get("/dashboard/summary")
        account = api_get("/account/state")
        positions = api_get("/trade/open_positions")
        signal = api_get("/signal", {"symbol": symbol, "mode": "real"})
        candles = api_get("/ohlcv", {"symbol": symbol, "timeframe": timeframe, "bars": bars})
        brokers = api_get("/brokers", {"include_inactive": "true"})
        default_broker = api_get("/brokers/default")
        mt5_status = api_get("/mt5/status")

        signal_data = as_mapping(signal)
        account_data = as_mapping(account)
        summary_data = as_mapping(summary)
        default_broker_data = as_mapping(default_broker)
        mt5_status_data = as_mapping(mt5_status)

        brokers_rows = brokers if isinstance(brokers, list) else []
        position_rows = positions if isinstance(positions, list) else []
        candles_rows = candles if isinstance(candles, list) else []

        last_signal = str(signal_data.get("signal", "wait")).lower()
        indicators = signal_data.get("indicators") if isinstance(signal_data.get("indicators"), dict) else {}
        signal_last_price = float((indicators.get("last") or 0.0) or 0.0)
        ohlcv_last_price = float(candles_rows[-1].get("close", signal_last_price)) if candles_rows else signal_last_price
        last_price = ohlcv_last_price if candles_rows and ohlcv_last_price else signal_last_price if signal_last_price else 0.0

        account_balance = float(account_data.get("balance", 0.0) or 0.0)
        open_count = len(position_rows)
        total_pnl = 0.0
        for row in position_rows:
            try:
                total_pnl += float(as_mapping(row).get("profit", 0.0) or 0.0)
            except Exception:
                pass

        metrics = [
            {"label": "Account Balance", "value": format_money(account_balance), "accent": "#60a5fa"},
            {"label": "Open Positions", "value": str(open_count), "accent": "#34d399"},
            {"label": "Last Price", "value": format_number(last_price), "accent": "#fbbf24"},
            {"label": "P/L Open", "value": format_money(total_pnl), "accent": "#f472b6"},
        ]

        broker_summary = summary_data.get("brokers", []) if isinstance(summary_data.get("brokers", []), list) else []
        mt5_connected = bool(mt5_status_data.get("connected", False))

        metric_cards = [
            html.Div(
                [
                    html.Div(item["label"], className="metric-label"),
                    html.Div(item["value"], style={"fontSize": "1.55rem", "fontWeight": "700", "color": item["accent"]}),
                ],
                className="metric-card",
                style={"borderTop": f"4px solid {item['accent']}"},
            )
            for item in metrics
        ]

        market_fig = build_figure(candles_rows)
        signal_status = last_signal.upper() if last_signal in {"buy", "sell", "wait"} else "WAIT"

        auto_trade_health = api_get("/account/auto_trade_health")
        auto_trade_health_map = as_mapping(auto_trade_health)
        auto_trade_checks = auto_trade_health_map.get("checks", []) if isinstance(auto_trade_health_map.get("checks", []), list) else []
        auto_trade_enabled = bool(
            auto_trade_health_map.get("auto_trade_enabled")
            if "auto_trade_enabled" in auto_trade_health_map
            else any(as_mapping(item).get("key") == "auto_trade_enabled" and bool(as_mapping(item).get("ok", False)) for item in auto_trade_checks)
        )

        quick_info = html.Div(
            [
                html.Div("Operational Overview", className="section-label"),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Span("Signal", className="status-dot", style={"backgroundColor": signal_color(last_signal)}),
                                html.Span(f"{signal_status}"),
                            ],
                            className="status-pill",
                        ),
                        html.Div(
                            [
                                html.Span("Broker", className="status-dot", style={"backgroundColor": "#60a5fa"}),
                                html.Span(f"{len(broker_summary)} active"),
                            ],
                            className="status-pill",
                        ),
                        html.Div(
                            [
                                html.Span("MT5", className="status-dot", style={"backgroundColor": "#fbbf24" if not mt5_connected else "#22c55e"}),
                                html.Span("Connected" if mt5_connected else "Offline"),
                            ],
                            className="status-pill",
                        ),
                    ],
                    className="status-row",
                ),
                html.Div(
                    [
                        html.Div(f"Last Price: {format_number(last_price)}", style={"marginBottom": "8px"}),
                        html.Div(f"Mode: {signal_data.get('mode', 'real')}", style={"marginBottom": "8px"}),
                        html.Div(f"Source: {indicators.get('source', 'market-data')}", style={"marginBottom": "8px"}),
                        html.Div(f"Bid / Ask: {format_number(indicators.get('bid', 0.0))} / {format_number(indicators.get('ask', 0.0))}", style={"marginBottom": "8px"}),
                        html.Div(f"Default Broker: {default_broker_data.get('name', '-') if default_broker_data else '-'}"),
                    ],
                    style={"marginTop": "12px", "color": "#dbeafe", "lineHeight": "1.7"},
                ),
                html.Div(
                    [
                        html.Button("Enable Auto Trade" if not auto_trade_enabled else "Disable Auto Trade", id="auto-trade-toggle", n_clicks=0, className="action-button neutral"),
                        html.Button("BUY", className="action-button buy"),
                        html.Button("SELL", className="action-button sell"),
                        html.Button("REFRESH", className="action-button neutral"),
                    ],
                    className="action-row",
                ),
                html.Div(
                    id="auto-trade-status",
                    children=f"Auto Trade: {'Enabled' if auto_trade_enabled else 'Disabled'}",
                    style={"marginTop": "10px", "color": "#cbd5e1", "fontWeight": "700"},
                ),
            ],
            className="panel",
            style={"minHeight": "100%"},
        )

        chart_panel = html.Div(
            [
                html.Div(
                    [
                        html.Div("Market Chart", className="section-label"),
                        html.Div(f"{symbol} • {timeframe} • {bars} bars", className="small-muted"),
                    ],
                    style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "8px"},
                ),
                dcc.Graph(figure=market_fig, config={"displayModeBar": False}, style={"height": "520px", "width": "100%"}),
            ],
            className="panel",
            style={"width": "100%", "minHeight": "600px", "display": "block"},
        )

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
                for item in brokers_rows[:10]
            ],
            style_table={"overflowX": "auto", "backgroundColor": "#0f172a"},
            style_cell={"color": "#e5e7eb", "backgroundColor": "#0f172a", "border": "1px solid #243248", "padding": "8px"},
            style_header={"backgroundColor": "#111827", "fontWeight": "700"},
        )

        positions_table = DataTable(
            columns=[
                {"name": "Broker", "id": "broker"},
                {"name": "Symbol", "id": "symbol"},
                {"name": "Direction", "id": "direction"},
                {"name": "Volume", "id": "lot"},
                {"name": "Entry", "id": "entry"},
                {"name": "Current", "id": "price"},
                {"name": "P/L", "id": "profit"},
                {"name": "Status", "id": "status"},
            ],
            data=[
                {
                    "broker": as_mapping(row).get("broker_name", as_mapping(row).get("broker", "-")),
                    "symbol": as_mapping(row).get("symbol", "-"),
                    "direction": (as_mapping(row).get("type", "-") or "-").upper(),
                    "lot": as_mapping(row).get("lot", 0),
                    "entry": format_number(as_mapping(row).get("entry", as_mapping(row).get("entry_price", 0.0))),
                    "price": format_number(as_mapping(row).get("price", as_mapping(row).get("last_price", 0.0))),
                    "profit": format_money(as_mapping(row).get("profit", 0.0)),
                    "status": (as_mapping(row).get("status", "open") or "open").capitalize(),
                }
                for row in position_rows[:20]
            ],
            style_table={"overflowX": "auto", "backgroundColor": "#0f172a"},
            style_cell={"color": "#e5e7eb", "backgroundColor": "#0f172a", "border": "1px solid #243248", "padding": "8px"},
            style_header={"backgroundColor": "#111827", "fontWeight": "700"},
        )

        strategy_panel = html.Div(
            [
                html.Div("Strategy Control Center", className="section-label"),
                html.Div(
                    [
                        html.Label("Strategy", style={"display": "block", "marginBottom": "8px", "color": "#dbeafe", "fontWeight": "700"}),
                        dcc.Dropdown(
                            id="strategy-dropdown",
                            options=[],
                            value="moving_average_cross",
                            clearable=False,
                            style={"color": "#0f172a", "marginBottom": "16px"},
                        ),
                        html.Div(id="strategy-parameter-inputs", children=build_strategy_parameter_inputs("moving_average_cross"), style={"marginBottom": "16px"}),
                        dcc.Checklist(
                            id="auto-trade-master-toggle",
                            options=[
                                {"label": "Enable Auto Trade", "value": "auto_trade_enabled"},
                                {"label": "Live Trading Mode", "value": "live_mode"},
                            ],
                            value=["auto_trade_enabled", "live_mode"],
                            inline=True,
                            style={"color": "#dbeafe", "marginBottom": "16px"},
                        ),
                        html.Button("Apply Strategy", id="strategy-apply-button", n_clicks=0, className="action-button neutral"),
                        html.Div(id="strategy-control-status", style={"marginTop": "12px", "color": "#cbd5e1", "fontWeight": "600"}),
                        dcc.Store(id="strategy-parameter-store", data={}),
                    ],
                    style={"display": "grid", "gap": "12px"},
                ),
            ],
            className="panel",
        )

        return html.Div(
            [
                html.Div(metric_cards, className="metrics-grid"),
                html.Div(chart_panel, className="panel", style={"width": "100%", "minHeight": "600px"}),
                html.Div(quick_info, className="panel", style={"width": "100%"}),
                strategy_panel,
                html.Div(
                    [
                        html.Div("Broker List", className="section-label"),
                        brokers_table,
                    ],
                    className="panel",
                ),
                html.Div(
                    [
                        html.Div("Active Transactions", className="section-label"),
                        positions_table,
                    ],
                    className="panel",
                ),
            ],
            className="page-layout",
        )
    except Exception as exc:
        return html.Div([
            html.H3("Backend unavailable"),
            html.P(str(exc), style={"color": "#fca5a5"}),
        ], className="error-panel")


def render_transactions_page():
    try:
        history = api_get("/trade/history")
        rows = history if isinstance(history, list) else []
        table = DataTable(
            columns=[
                {"name": "Symbol", "id": "symbol"},
                {"name": "Type", "id": "type"},
                {"name": "Entry", "id": "entry"},
                {"name": "Exit", "id": "exit"},
                {"name": "Lot", "id": "lot"},
                {"name": "Profit", "id": "profit"},
                {"name": "Status", "id": "status"},
                {"name": "Reason", "id": "reason"},
            ],
            data=[
                {
                    "symbol": as_mapping(item).get("symbol", "-"),
                    "type": (as_mapping(item).get("type", "-") or "-").upper(),
                    "entry": format_number(as_mapping(item).get("entry", 0.0)),
                    "exit": format_number(as_mapping(item).get("exit", 0.0)),
                    "lot": as_mapping(item).get("lot", 0),
                    "profit": format_money(as_mapping(item).get("profit", 0.0)),
                    "status": (as_mapping(item).get("status", "closed") or "closed").capitalize(),
                    "reason": as_mapping(item).get("reason", "-"),
                }
                for item in rows[:50]
            ],
            style_table={"overflowX": "auto", "backgroundColor": "#0f172a"},
            style_cell={"color": "#e5e7eb", "backgroundColor": "#0f172a", "border": "1px solid #243248", "padding": "8px"},
            style_header={"backgroundColor": "#111827", "fontWeight": "700"},
        )
        return html.Div([
            html.Div("Transaction History", className="section-label"),
            html.Div(table, className="panel"),
        ], className="page-layout")
    except Exception as exc:
        return html.Div([
            html.H3("Transaction history unavailable"),
            html.P(str(exc), style={"color": "#fca5a5"}),
        ], className="error-panel")


def render_settings_page():
    try:
        account = api_get("/account/state")
        brokers = api_get("/brokers", {"include_inactive": "true"})
        account_data = as_mapping(account)
        rows = brokers if isinstance(brokers, list) else []
        settings_cards = [
            html.Div([
                html.Div("Account", className="section-label"),
                html.Div(f"Balance: {format_money(account_data.get('balance', 0.0))}", style={"marginBottom": "8px"}),
                html.Div(f"Equity: {format_money(account_data.get('equity', 0.0))}", style={"marginBottom": "8px"}),
                html.Div(f"Lot: {account_data.get('lot', 0.01)}", style={"marginBottom": "8px"}),
                html.Div(f"Max Open Trades: {account_data.get('max_open_trades', 1)}"),
            ], className="compact-panel"),
            html.Div([
                html.Div("Broker Defaults", className="section-label"),
                html.Div(f"Total Brokers: {len(rows)}", style={"marginBottom": "8px"}),
                html.Div(f"Default Broker: {next((r.get('name', '-') for r in rows if r.get('is_default')), '-')}", style={"marginBottom": "8px"}),
                html.Div(f"MT5 Mode: {'Enabled' if account_data.get('enable_real_trade') else 'Disabled'}"),
            ], className="compact-panel"),
            html.Div([
                html.Div("Execution", className="section-label"),
                html.Div("Trade Execution: Operational Controls", style={"marginBottom": "8px"}),
                html.Div("Risk Guard: Active", style={"marginBottom": "8px"}),
                html.Div("Alerts: Enabled"),
            ], className="compact-panel"),
        ]
        return html.Div([
            html.Div("Settings", className="section-label"),
            html.Div(settings_cards, style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(220px, 1fr))", "gap": "16px"}),
        ], className="page-layout")
    except Exception as exc:
        return html.Div([
            html.H3("Settings unavailable"),
            html.P(str(exc), style={"color": "#fca5a5"}),
        ], className="error-panel")


@app.callback(
    Output("strategy-dropdown", "options"),
    Input("refresh-interval", "n_intervals"),
)
def update_strategy_dropdown(_n: int):
    try:
        payload = api_get("/strategies/list")
        strategies = payload.get("strategies", []) if isinstance(payload, dict) else []
        options = [{"label": item.get("name", "unknown"), "value": item.get("name", "unknown")} for item in strategies]
        return options
    except Exception:
        return []


@app.callback(
    Output("strategy-parameter-inputs", "children"),
    Input("strategy-dropdown", "value"),
    Input("refresh-interval", "n_intervals"),
)
def update_strategy_parameter_inputs(strategy_name: str | None, _n: int):
    return build_strategy_parameter_inputs(strategy_name or "moving_average_cross")


@app.callback(
    Output("strategy-parameter-store", "data"),
    Input({"type": "strategy-parameter", "index": ALL}, "value"),
    State({"type": "strategy-parameter", "index": ALL}, "id"),
    prevent_initial_call=True,
)
def sync_strategy_parameter_store(values: list[Any], ids: list[dict[str, str]]):
    payload: dict[str, Any] = {}
    for value, item in zip(values, ids):
        key = item.get("index") if isinstance(item, dict) else None
        if key:
            payload[key] = value
    return payload


@app.callback(
    Output("strategy-control-status", "children"),
    Input("strategy-apply-button", "n_clicks"),
    Input("auto-trade-master-toggle", "value"),
    State("strategy-dropdown", "value"),
    State("strategy-parameter-store", "data"),
    prevent_initial_call=True,
)
def apply_strategy_and_settings(_n_clicks: int | None, master_toggle: list[str] | None, strategy_name: str | None, parameter_store: dict[str, Any] | None):
    try:
        enabled = "auto_trade_enabled" in (master_toggle or [])
        live_mode = "live_mode" in (master_toggle or [])
        if strategy_name:
            payload = {"name": strategy_name, "parameters": parameter_store or {}}
            api_post("/strategies/switch", payload)
        api_post("/account/set_auto_trade_enabled", {"enabled": enabled})
        api_post("/account/set_enable_real_trade", {"enabled": live_mode})
        return f"Strategy {strategy_name or 'default'} applied. Auto Trade: {'ON' if enabled else 'OFF'} | Live Mode: {'ON' if live_mode else 'OFF'}"
    except Exception as exc:
        return f"Strategy update failed: {exc}"


@app.callback(
    Output("dashboard-page", "children"),
    Input("refresh-interval", "n_intervals"),
    Input("page-selector", "value"),
    Input("symbol-input", "value"),
    Input("timeframe-input", "value"),
    Input("bars-input", "value"),
    Input("auto-trade-toggle", "n_clicks"),
    prevent_initial_call=True,
)
def render_dashboard(_n: int, page: str | None, symbol: str | None, timeframe: str | None, bars: Any, auto_trade_clicks: int | None):
    page = page or "overview"
    if auto_trade_clicks and auto_trade_clicks > 0 and page == "overview":
        try:
            payload = api_get("/account/auto_trade_health")
            health = as_mapping(payload)
            enabled = bool(health.get("auto_trade_enabled") if "auto_trade_enabled" in health else False)
            requests.post(f"{BACKEND_URL.rstrip('/')}/account/set_auto_trade_enabled", json={"enabled": not enabled}, timeout=15)
        except Exception:
            pass
    if page == "transactions":
        return render_transactions_page()
    if page == "settings":
        return render_settings_page()
    return render_overview_page(symbol, timeframe, bars)


app.layout = html.Div(
    [
        dcc.Interval(id="refresh-interval", interval=REFRESH_MS, n_intervals=0),
        html.Div(
            [
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div(className="brand-mark"),
                                html.Div("Trading Signal Console"),
                            ],
                            className="brand",
                        ),
                        html.Div(
                            [
                                dcc.RadioItems(
                                    id="page-selector",
                                    options=[
                                        {"label": "Overview", "value": "overview"},
                                        {"label": "Transactions", "value": "transactions"},
                                        {"label": "Settings", "value": "settings"},
                                    ],
                                    value="overview",
                                    inline=True,
                                    className="page-nav",
                                )
                            ],
                            className="page-nav",
                        ),
                    ],
                    className="nav-panel",
                ),
                html.Div(
                    [
                        html.Label("Symbol"),
                        dcc.Input(id="symbol-input", value=DEFAULT_SYMBOL, type="text", style={"width": "120px"}),
                        html.Label("Timeframe"),
                        dcc.Dropdown(
                            id="timeframe-input",
                            options=["M1", "M5", "M15", "M30", "H1"],
                            value=DEFAULT_TIMEFRAME,
                            clearable=False,
                            style={"minWidth": "120px", "color": "#0f172a"},
                        ),
                        html.Label("Bars"),
                        dcc.Input(id="bars-input", value=str(DEFAULT_BARS), type="number", min=30, max=240, step=30, style={"width": "80px"}),
                    ],
                    className="toolbar panel",
                ),
                html.Div(id="dashboard-page"),
            ],
            className="page-layout",
        ),
    ],
    className="app-shell",
)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False, use_reloader=False)
