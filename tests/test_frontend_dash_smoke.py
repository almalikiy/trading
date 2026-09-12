from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from frontend_dash.app import app


def _iter_children(node: Any) -> Iterable[Any]:
    children = getattr(node, "children", None)
    if children is None:
        return []
    if isinstance(children, (list, tuple)):
        return children
    return [children]


def _collect_ids(node: Any, ids: set[str]) -> None:
    node_id = getattr(node, "id", None)
    if isinstance(node_id, str):
        ids.add(node_id)
    for child in _iter_children(node):
        _collect_ids(child, ids)


def test_dash_layout_contains_core_nodes() -> None:
    layout = app.layout
    ids: set[str] = set()
    _collect_ids(layout, ids)

    assert "sidebar-drawer" in ids
    assert "app-content" in ids
    assert "dashboard-page" in ids
    assert "drawer-toggle" in ids
    assert "page-selector" in ids
    assert "stream-status" in ids
    assert "stream-status-badge" in ids
    assert "toolbar-stream-status" in ids
    assert "status-summary-panel" in ids


def test_dash_callbacks_registered() -> None:
    callback_keys = set(app.callback_map.keys())

    assert "dashboard-page.children" in callback_keys
    assert any("drawer-collapsed.data" in key and "sidebar-drawer.className" in key for key in callback_keys)
    assert "strategy-parameter-inputs.children" in callback_keys
    assert "strategy-control-status.children" in callback_keys


def test_overview_page_renders_without_backend_errors() -> None:
    from frontend_dash.pages.overview import render_overview_page

    page = render_overview_page("XAUUSD", "M1", 60)
    assert page is not None
    assert getattr(page, "children", None) is not None


def test_overview_page_includes_real_chart_component() -> None:
    from dash import dcc

    from frontend_dash.pages.overview import render_overview_page

    page = render_overview_page("XAUUSD", "M1", 60)
    found = False

    def walk(node: Any):
        nonlocal found
        if isinstance(node, dcc.Graph):
            found = True
            return
        children = getattr(node, "children", None)
        if isinstance(children, (list, tuple)):
            for item in children:
                walk(item)
        elif children is not None:
            walk(children)

    walk(page)
    assert found is True


def test_overview_page_counts_nested_positions_payload(monkeypatch) -> None:
    import frontend_dash.pages.overview as overview

    async def fake_api_get(path: str, params: dict[str, Any] | None = None, timeout: float = 2):
        mapping = {
            "/dashboard/summary": {
                "status": "ready",
                "brokers": [],
                "trade_sync": {"status": "idle"},
                "account": {"balance": 1000.0, "equity": 1000.0},
                "trading": {"open_positions": 1},
            },
            "/account/state": {"balance": 1000.0, "equity": 1000.0},
            "/positions": [{
                "broker": "mt5",
                "positions": [{
                    "symbol": "XAUUSD",
                    "type": "BUY",
                    "lot": 0.1,
                    "entry_price": 2345.0,
                    "price": 2350.0,
                    "profit": 5.0,
                    "status": "open",
                }],
            }],
            "/signal": {"signal": "buy", "indicators": {"last": 2350.0, "bid": 2349.0, "ask": 2351.0, "source": "market-data"}, "status": "live", "notice": "ok"},
            "/ohlcv": [{"time": 1710000000, "open": 2340.0, "high": 2355.0, "low": 2338.0, "close": 2350.0}],
            "/brokers/default": {"name": "MT5 Demo"},
            "/mt5/status": {"connected": False},
            "/mt5/background_sync_status": {"sync_status": "idle"},
            "/account/auto_trade_health": {"auto_trade_enabled": True, "checks": [{"key": "auto_trade_enabled", "ok": True}]},
        }
        return mapping.get(path, {})

    monkeypatch.setattr(overview, "api_get_async", fake_api_get)

    page = overview.render_overview_page("XAUUSD", "M1", 10)

    def walk(node: Any, labels: list[str] | None = None):
        if labels is None:
            labels = []
        children = getattr(node, "children", None)
        if isinstance(children, list):
            for item in children:
                walk(item, labels)
        elif children is not None:
            walk(children, labels)
        text = getattr(node, "children", None)
        if isinstance(text, str):
            labels.append(text)
        return labels

    texts = walk(page)
    assert "Open Positions" in texts
    assert "1" in texts
