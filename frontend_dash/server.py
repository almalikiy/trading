from __future__ import annotations

from dash import Dash

app = Dash(
	__name__,
	title="Trading Dashboard",
	suppress_callback_exceptions=True,
	external_stylesheets=[],
)
