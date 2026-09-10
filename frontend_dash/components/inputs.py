from __future__ import annotations

from typing import Any

from dash import dcc, html

from frontend_dash.api.client import api_get


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
                    className="strategy-parameter-input",
                )
            else:
                field = dcc.Input(
                    id={"type": "strategy-parameter", "index": key},
                    type="text",
                    value=str(default_value) if default_value is not None else "",
                    className="strategy-parameter-input",
                )
            children.append(
                html.Div(
                    [
                        html.Label(key.replace("_", " ").title(), className="strategy-parameter-label"),
                        field,
                    ],
                    className="strategy-parameter-item",
                )
            )
        return html.Div(children, className="strategy-parameter-grid")
    except Exception:
        return html.Div("Unable to load strategy parameters.", className="small-muted")
