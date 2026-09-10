from __future__ import annotations

from dash import html
from dash.dash_table import DataTable

from frontend_dash.api.client import api_get, as_mapping


def _format_money(value):
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "-"


def _format_number(value, digits: int = 2):
    try:
        return f"{float(value):,.{digits}f}"
    except Exception:
        return "-"


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
                    "entry": _format_number(as_mapping(item).get("entry", 0.0)),
                    "exit": _format_number(as_mapping(item).get("exit", 0.0)),
                    "lot": as_mapping(item).get("lot", 0),
                    "profit": _format_money(as_mapping(item).get("profit", 0.0)),
                    "status": (as_mapping(item).get("status", "closed") or "closed").capitalize(),
                    "reason": as_mapping(item).get("reason", "-"),
                }
                for item in rows[:50]
            ],
            style_table={"overflowX": "auto"},
            style_cell={"padding": "8px"},
        )
        return html.Div([
            html.Div("Transaction History", className="section-label"),
            html.Div(html.Div(table, className="table-dark"), className="panel"),
        ], className="page-layout")
    except Exception as exc:
        return html.Div([
            html.H3("Transaction history unavailable"),
            html.P(str(exc), className="error-text"),
        ], className="error-panel")
