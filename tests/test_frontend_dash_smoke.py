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


def test_dash_callbacks_registered() -> None:
    callback_keys = set(app.callback_map.keys())

    assert "dashboard-page.children" in callback_keys
    assert any("drawer-collapsed.data" in key and "sidebar-drawer.className" in key for key in callback_keys)
    assert "strategy-parameter-inputs.children" in callback_keys
    assert "strategy-control-status.children" in callback_keys
