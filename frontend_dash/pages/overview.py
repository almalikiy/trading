#file: frontend_dash/pages/overview.py
from __future__ import annotations

import asyncio
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

from frontend_dash.api.client import api_get_async, as_mapping
from frontend_dash.config import DEFAULT_BARS, DEFAULT_SYMBOL, DEFAULT_TIMEFRAME


async def _safe_api_get(path: str, params: dict[str, Any] | None = None, timeout: float = 2) -> Any:
    try:
        return await api_get_async(path, params=params, timeout=timeout)
    except Exception:
        return {}


def _signal_dot_class(value: str) -> str:
    if value == "buy":
        return "status-dot pill-signal-buy"
    if value == "sell":
        return "status-dot pill-signal-sell"
    return "status-dot pill-signal-wait"


def _sync_status_dot_class(value: str) -> str:
    normalized = str(value or "idle").lower()
    if normalized in {"failed", "error"}:
        return "status-dot pill-sync-failed"
    if normalized == "running":
        return "status-dot pill-sync-running"
    if normalized == "queued":
        return "status-dot pill-sync-queued"
    if normalized == "completed":
        return "status-dot pill-sync-completed"
    return "status-dot pill-sync-idle"


def _accent_class(index: int) -> str:
    accents = ["accent-blue", "accent-green", "accent-amber", "accent-pink"]
    return accents[index % len(accents)]


def _format_money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "-"


def _format_number(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):,.{digits}f}"
    except Exception:
        return "-"


def _safe_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
        return max(1, parsed)
    except (TypeError, ValueError):
        return default


def _resolve_default_broker_record(rows: list[Any]) -> dict[str, Any]:
    if not rows:
        return {}
    for row in rows:
        payload = as_mapping(row)
        if bool(payload.get("is_default")):
            return payload
    return as_mapping(rows[0])


def _compute_signal_insight(candles: list[dict[str, Any]], signal_status: str, last_price: float) -> tuple[str, list[str], dict[str, float]]:
    if not candles:
        return (
            "Data candle belum cukup untuk menjelaskan sinyal secara teknikal.",
            ["Belum ada area support/resistance yang bisa dipetakan."],
            {},
        )

    df = pd.DataFrame(candles)
    required = {"high", "low", "close"}
    if not required.issubset(set(df.columns)):
        return (
            "Data candle tidak lengkap untuk analisa sinyal.",
            ["Periksa feed OHLCV dari backend market data."],
            {},
        )

    close = pd.to_numeric(df["close"], errors="coerce")
    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")
    valid = pd.DataFrame({"close": close, "high": high, "low": low}).dropna()
    if valid.empty:
        return (
            "Data candle tidak valid untuk analisa sinyal.",
            ["Tidak bisa membentuk area teknikal dari candle kosong."],
            {},
        )

    close = valid["close"]
    high = valid["high"]
    low = valid["low"]

    ema_fast = float(close.ewm(span=9, adjust=False).mean().iloc[-1])
    ema_slow = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
    momentum_window = 5 if len(close) > 5 else 1
    momentum = float(close.iloc[-1] - close.iloc[-(momentum_window + 1)]) if len(close) > momentum_window else 0.0
    avg_range = float((high - low).tail(14).mean()) if len(high) > 1 else 0.0

    window = min(20, len(close))
    support = float(low.tail(window).min())
    resistance = float(high.tail(window).max())
    mid_zone = (support + resistance) / 2

    trend_up = ema_fast > ema_slow
    price_ref = last_price if last_price else float(close.iloc[-1])
    dist_support = price_ref - support
    dist_resistance = resistance - price_ref
    spread_zone = max(resistance - support, 1e-9)
    near_support = dist_support / spread_zone < 0.25
    near_resistance = dist_resistance / spread_zone < 0.25

    if signal_status == "BUY":
        reason = "BUY karena momentum jangka pendek naik dan harga bergerak dengan bias bullish."
        if not trend_up:
            reason = "BUY agresif: sinyal mencoba reversal, tetapi tren menengah belum sepenuhnya bullish."
    elif signal_status == "SELL":
        reason = "SELL karena momentum jangka pendek melemah dan harga cenderung bearish."
        if trend_up:
            reason = "SELL agresif: sinyal mencoba rejection di area atas saat tren menengah masih bullish."
    else:
        reason = "WAIT karena struktur harga masih netral, konfirmasi arah belum kuat."
        if trend_up and not near_resistance:
            reason = "WAIT meski bias bullish, harga belum memberi trigger breakout yang bersih."
        elif (not trend_up) and not near_support:
            reason = "WAIT meski bias bearish, harga belum memberi trigger breakdown yang bersih."

    areas = [
        f"Support minor: {_format_number(support)} | area pantul bawah.",
        f"Resistance minor: {_format_number(resistance)} | area potensi penolakan atas.",
        f"Mid-zone: {_format_number(mid_zone)} | penyeimbang arah intraday.",
    ]
    if near_support:
        areas.append("Harga sedang dekat support: perhatikan potensi bounce atau breakdown.")
    if near_resistance:
        areas.append("Harga sedang dekat resistance: perhatikan potensi reject atau breakout.")
    if avg_range > 0:
        areas.append(f"Rata-rata range 14 candle: {_format_number(avg_range)} (volatilitas saat ini).")

    areas_map = {
        "support": support,
        "resistance": resistance,
        "mid_zone": mid_zone,
        "ema_fast": ema_fast,
        "ema_slow": ema_slow,
        "momentum": momentum,
    }
    return reason, areas[:5], areas_map


def _build_figure(candles: list[dict[str, Any]], areas_map: dict[str, float] | None = None) -> go.Figure:
    if not candles:
        fig = go.Figure()
        fig.update_layout(
            template="plotly",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
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
        template="plotly",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(title="Time", rangeslider=dict(visible=False), showgrid=False),
        yaxis=dict(title="Price", showgrid=True, gridcolor="#243248"),
        font=dict(color="#475569"),
    )

    if areas_map:
        support = areas_map.get("support")
        resistance = areas_map.get("resistance")
        mid_zone = areas_map.get("mid_zone")
        if isinstance(support, float):
            fig.add_hline(y=support, line_width=1, line_dash="dot", line_color="#22c55e", annotation_text="Support", annotation_position="bottom right")
        if isinstance(resistance, float):
            fig.add_hline(y=resistance, line_width=1, line_dash="dot", line_color="#ef4444", annotation_text="Resistance", annotation_position="top right")
        if isinstance(mid_zone, float):
            fig.add_hline(y=mid_zone, line_width=1, line_dash="dash", line_color="#38bdf8", annotation_text="Mid-zone", annotation_position="top left")
    return fig


def render_overview_page(symbol: str | None, timeframe: str | None, bars: Any):
    symbol = (symbol or DEFAULT_SYMBOL).upper()
    timeframe = timeframe or DEFAULT_TIMEFRAME
    bars = _safe_int(bars, DEFAULT_BARS)

    async def _load_data() -> html.Div:
        try:
            summary, account, positions, signal, candles, default_broker, mt5_status, background_sync, auto_trade_health, auto_trade_runtime, brokers, auto_trade_constraints, auto_trade_stats, auto_trade_events, mt5_error_log, mt5_error_log_summary = await asyncio.gather(
                _safe_api_get("/dashboard/summary"),
                _safe_api_get("/account/state"),
                _safe_api_get("/positions"),
                _safe_api_get("/signal", {"symbol": symbol, "mode": "real"}),
                _safe_api_get("/ohlcv", {"symbol": symbol, "timeframe": timeframe, "bars": bars}),
                _safe_api_get("/brokers/default"),
                _safe_api_get("/mt5/status"),
                _safe_api_get("/mt5/background_sync_status"),
                _safe_api_get("/account/auto_trade_health"),
                _safe_api_get("/account/auto_trade_runtime"),
                _safe_api_get("/brokers", {"include_inactive": "true"}),
                _safe_api_get("/account/auto_trade_constraints"),
                _safe_api_get("/account/auto_trade_stats", {"window_days": 30}),
                _safe_api_get("/account/auto_trade_events", {"limit": 10}),
                _safe_api_get("/mt5/error_log", {"limit": 8}),
                _safe_api_get("/mt5/error_log_summary", {"limit": 200}),
            )
        except Exception:
            summary = {"brokers": []}
            account = {"balance": 0.0, "equity": 0.0, "auto_trade_enabled": False, "enable_real_trade": False}
            positions = []
            signal = {"signal": "wait", "indicators": {"last": 0.0, "source": "market-data"}, "status": "degraded", "notice": "Backend unavailable; showing offline fallback."}
            candles = []
            default_broker = {}
            mt5_status = {"connected": False}
            background_sync = {"sync_status": "idle"}
            auto_trade_health = {"auto_trade_enabled": False, "checks": []}
            auto_trade_runtime = {}
            brokers = []
            auto_trade_constraints = {"constraints": {}}
            auto_trade_stats = {"stats": {}}
            auto_trade_events = {"events": []}
            mt5_error_log = {"errors": []}
            mt5_error_log_summary = {"errors": []}

        signal_data = as_mapping(signal)
        account_data = as_mapping(account)
        summary_data = as_mapping(summary)
        summary_broker_rows = summary_data.get("brokers") if isinstance(summary_data.get("brokers"), list) else []
        broker_rows = brokers if isinstance(brokers, list) and brokers else summary_broker_rows
        default_broker_data = as_mapping(default_broker)
        if not default_broker_data:
            default_broker_data = _resolve_default_broker_record(broker_rows)
        mt5_status_data = as_mapping(mt5_status)
        background_sync_data = as_mapping(background_sync)
        auto_trade_health_map = as_mapping(auto_trade_health)
        auto_trade_runtime_map = as_mapping(auto_trade_runtime)
        constraints_map = as_mapping(auto_trade_constraints.get("constraints") if isinstance(auto_trade_constraints, dict) else auto_trade_constraints)
        stats_map = as_mapping(auto_trade_stats.get("stats") if isinstance(auto_trade_stats, dict) else auto_trade_stats)
        events_payload = as_mapping(auto_trade_events)
        event_rows = events_payload.get("events") if isinstance(events_payload.get("events"), list) else []
        mt5_error_log_data = as_mapping(mt5_error_log)
        mt5_error_summary_data = as_mapping(mt5_error_log_summary)
        mt5_error_rows = mt5_error_log_data.get("errors") if isinstance(mt5_error_log_data.get("errors"), list) else []

        positions_data = positions if isinstance(positions, list) else []
        position_rows: list[dict[str, Any]] = []
        for item in positions_data:
            if not isinstance(item, dict):
                continue
            nested = item.get("positions") if isinstance(item.get("positions"), list) else []
            if nested:
                for row in nested:
                    if isinstance(row, dict):
                        row_copy = dict(row)
                        row_copy.setdefault("broker", item.get("broker") or item.get("broker_name") or "mt5")
                        row_copy.setdefault("broker_name", row_copy.get("broker") or item.get("broker_name") or "mt5")
                        position_rows.append(row_copy)
            elif item.get("symbol"):
                position_rows.append(item)
        candles_rows = candles if isinstance(candles, list) else []

        last_signal = str(signal_data.get("signal", "wait")).lower()
        indicators = signal_data.get("indicators") if isinstance(signal_data.get("indicators"), dict) else {}
        def _as_float(value: Any, default: float = 0.0) -> float:
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        signal_last_price = _as_float(indicators.get("last"), 0.0)
        ohlcv_last_price = _as_float((candles_rows[-1] or {}).get("close"), signal_last_price) if candles_rows else signal_last_price
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
            {"label": "Account Balance", "value": _format_money(account_balance)},
            {"label": "Open Positions", "value": str(open_count)},
            {"label": "Last Price", "value": _format_number(last_price)},
            {"label": "P/L Open", "value": _format_money(total_pnl)},
        ]

        broker_summary = summary_data.get("brokers", []) if isinstance(summary_data.get("brokers", []), list) else []
        mt5_connected = bool(mt5_status_data.get("connected", False) or mt5_status_data.get("ready", False))
        background_sync_state = str(background_sync_data.get("sync_status", background_sync_data.get("status", "idle")) or "idle").lower()
        sync_status_label = background_sync_state.upper() if background_sync_state else "IDLE"

        metric_cards = [
            html.Div(
                [
                    html.Div(item["label"], className="metric-label"),
                    html.Div(item["value"], className="metric-value"),
                ],
                className=f"metric-card {_accent_class(i)}",
            )
            for i, item in enumerate(metrics)
        ]

        signal_status = last_signal.upper() if last_signal in {"buy", "sell", "wait"} else "WAIT"
        signal_reason, key_areas, areas_map = _compute_signal_insight(candles_rows, signal_status, last_price)
        market_fig = _build_figure(candles_rows, areas_map)

        stream_mode = str(signal_data.get("status", "degraded")).lower()
        stream_notice = str(signal_data.get("notice") or "Stream running in safe mode.")
        if not signal_data.get("notice") and not mt5_connected:
            stream_notice = "MT5 Keep Alive is off. Stream is using cached/non-terminal data only."
        degraded_banner = html.Div(
            [
                html.Div("Stream Status", className="subsection-label"),
                html.Div(
                    [
                        html.Span("DEGRADED MODE" if stream_mode == "degraded" else "LIVE STREAM", className="status-dot pill-sync-queued" if stream_mode == "degraded" else "status-dot pill-sync-running"),
                        html.Span(stream_notice),
                    ],
                    className="status-pill",
                    id="stream-status",
                ),
            ],
            className="panel",
        )

        status_summary_panel = html.Div(
            [
                html.Div("System Status", className="section-label"),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Span("MT5", className="summary-badge summary-badge-blue"),
                                html.Div(
                                    [
                                        html.Div("Terminal", className="summary-label"),
                                        html.Div("Connected" if mt5_connected else "Offline", className="summary-value"),
                                    ],
                                    className="summary-item",
                                ),
                            ],
                            className="summary-tile",
                        ),
                        html.Div(
                            [
                                html.Span("Stream", className="summary-badge summary-badge-green" if stream_mode != "degraded" else "summary-badge summary-badge-orange"),
                                html.Div(
                                    [
                                        html.Div("Mode", className="summary-label"),
                                        html.Div("Live" if stream_mode != "degraded" else "Degraded", className="summary-value"),
                                    ],
                                    className="summary-item",
                                ),
                            ],
                            className="summary-tile",
                        ),
                        html.Div(
                            [
                                html.Span("Broker", className="summary-badge summary-badge-sky"),
                                html.Div(
                                    [
                                        html.Div("Default Broker", className="summary-label"),
                                        html.Div(default_broker_data.get("name", "-") if default_broker_data else "-", className="summary-value"),
                                    ],
                                    className="summary-item",
                                ),
                            ],
                            className="summary-tile",
                        ),
                        html.Div(
                            [
                                html.Span("Data", className="summary-badge summary-badge-purple"),
                                html.Div(
                                    [
                                        html.Div("Source", className="summary-label"),
                                        html.Div(indicators.get("source", "market-data"), className="summary-value"),
                                    ],
                                    className="summary-item",
                                ),
                            ],
                            className="summary-tile",
                        ),
                    ],
                    className="status-summary-grid",
                ),
                html.Div(stream_notice, className="status-summary-note"),
            ],
            className="panel",
            id="status-summary-panel",
        )

        stream_badge_text = "DEGRADED" if stream_mode == "degraded" else "LIVE"
        stream_badge_class = "pill-sync-queued" if stream_mode == "degraded" else "pill-sync-running"
        global_badge_state = {
            "text": stream_badge_text,
            "class": stream_badge_class,
            "notice": stream_notice,
        }

        auto_trade_checks = auto_trade_health_map.get("checks", []) if isinstance(auto_trade_health_map.get("checks", []), list) else []
        auto_trade_enabled = bool(
            auto_trade_health_map.get("auto_trade_enabled")
            if "auto_trade_enabled" in auto_trade_health_map
            else any(as_mapping(item).get("key") == "auto_trade_enabled" and bool(as_mapping(item).get("ok", False)) for item in auto_trade_checks)
        )
        signal_panel = html.Div(
            [
                html.Div("Signal", className="section-label"),
                html.Div(signal_status, className="signal-value"),
                html.Div(f"Last Price: {_format_number(last_price)}", className="kv-line"),
                html.Div(f"Mode: {signal_data.get('mode', 'real')}", className="kv-line"),
                html.Div("Alasan Signal", className="subsection-label"),
                html.P(signal_reason, className="signal-reason"),
                html.Div("Area Penting Chart", className="subsection-label"),
                html.Ul([html.Li(item) for item in key_areas], className="analysis-list"),
            ],
            className="panel",
        )

        runtime_payload = as_mapping(auto_trade_runtime_map.get("runtime"))
        runtime_loop_started = bool(runtime_payload.get("loop_started", False))
        runtime_last_decision = str(runtime_payload.get("last_decision") or "unknown")
        runtime_last_reason = str(runtime_payload.get("last_reason") or "idle")
        runtime_last_signal = str(runtime_payload.get("last_signal") or "wait")
        runtime_last_symbol = str(runtime_payload.get("last_symbol") or "-")
        runtime_last_signal_score = _format_number(runtime_payload.get("last_signal_score", 0.0), 3)
        runtime_last_open_attempt = as_mapping(runtime_payload.get("last_open_attempt"))
        runtime_last_open_status = str(runtime_last_open_attempt.get("status") or runtime_payload.get("last_open_error") or "no_attempt")
        runtime_last_open_error = str(runtime_payload.get("last_open_error") or runtime_last_open_attempt.get("error") or "none")
        recent_runtime_events = runtime_payload.get("recent_events") if isinstance(runtime_payload.get("recent_events"), list) else []
        skip_counts = runtime_payload.get("skip_counts") if isinstance(runtime_payload.get("skip_counts"), dict) else {}
        runtime_events_list = []
        for item in recent_runtime_events[:5]:
            event = as_mapping(item)
            ts = event.get("ts")
            label = f"{event.get('decision', 'event')} • {event.get('reason', 'unknown')}"
            if ts is not None:
                label = f"{label} • {int(ts)}"
            runtime_events_list.append(html.Li(label))
        if not runtime_events_list:
            runtime_events_list = [html.Li("No recent auto-trade events recorded yet.")]

        runtime_panel = html.Div(
            [
                html.Div("Auto-Trade Runtime", className="section-label"),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Span("Loop", className="status-dot pill-sync-running" if runtime_loop_started else "status-dot pill-sync-idle"),
                                html.Span("Running" if runtime_loop_started else "Idle"),
                            ],
                            className="status-pill",
                        ),
                        html.Div(
                            [
                                html.Span("Decision", className="status-dot pill-broker"),
                                html.Span(runtime_last_decision.upper()),
                            ],
                            className="status-pill",
                        ),
                    ],
                    className="status-row",
                ),
                html.Div(f"Reason: {runtime_last_reason}", className="kv-line"),
                html.Div(f"Signal: {runtime_last_signal.upper()}", className="kv-line"),
                html.Div(f"Signal Score: {runtime_last_signal_score}", className="kv-line"),
                html.Div(f"Last Symbol: {runtime_last_symbol}", className="kv-line"),
                html.Div(f"Open Attempt: {runtime_last_open_status.upper()}", className="kv-line"),
                html.Div(f"Open Error: {runtime_last_open_error}", className="kv-line"),
                html.Div("Skip Counts", className="subsection-label"),
                html.Div(
                    ", ".join(f"{key}={value}" for key, value in sorted(skip_counts.items())) if skip_counts else "No skips recorded.",
                    className="kv-line",
                ),
                html.Div("Recent Events", className="subsection-label"),
                html.Ul(runtime_events_list, className="analysis-list"),
            ],
            id="auto-trade-runtime-panel",
            className="panel",
        )

        broker_items = []
        for broker in broker_rows[:6]:
            b = as_mapping(broker)
            broker_items.append(
                html.Div(
                    [
                        html.Div(b.get("name", "Broker"), className="broker-panel-name"),
                        html.Div(
                            [
                                html.Span(f"{b.get('platform', '-')} • symbol {b.get('default_symbol', '-')}", className="kv-line"),
                                html.Span("Default" if bool(b.get("is_default")) else "Available", className="status-dot pill-sync-running" if bool(b.get("is_default")) else "status-dot pill-sync-idle"),
                            ],
                            className="broker-panel-row",
                        ),
                    ],
                    className="broker-panel-item",
                )
            )
        if not broker_items:
            broker_items = [html.Div("No broker definitions found.", className="kv-line")]

        broker_panel = html.Div(
            [
                html.Div("Broker Snapshot", className="section-label"),
                html.Div(
                    [
                        html.Div(f"Default Broker: {default_broker_data.get('name', '-') if default_broker_data else '-'}", className="kv-line"),
                        html.Div(f"Broker Count: {len(broker_rows)}", className="kv-line"),
                        html.Div(f"Active Brokers: {sum(1 for row in broker_rows if bool(as_mapping(row).get('is_active')))}", className="kv-line"),
                    ],
                    className="kv-stack",
                ),
                html.Div(broker_items, className="broker-panel-list"),
                html.Div(
                    "Managed centrally in Settings > Broker CRUD.",
                    className="kv-line",
                ),
            ],
            id="broker-management-panel",
            className="panel",
        )

        constraint_summary = [
            ["Broker", str(constraints_map.get("broker") or default_broker_data.get("name") or "-")],
            ["Symbol", str(constraints_map.get("symbol") or account_data.get("auto_trade_symbol") or symbol)],
            ["Lot", str(constraints_map.get("lot") or account_data.get("lot") or 0.01)],
            ["Max Open Trades", str(constraints_map.get("max_open_trades") or account_data.get("max_open_trades") or 1)],
            ["Risk %", str(constraints_map.get("risk_percent") or account_data.get("auto_trade_risk_percent") or 1.0)],
        ]
        blockers = auto_trade_health_map.get("blockers") if isinstance(auto_trade_health_map.get("blockers"), list) else []
        blocker_items = [html.Li(str(item)) for item in blockers] if blockers else [html.Li("No active blockers.")]

        stats_rows = stats_map if isinstance(stats_map, dict) else {}
        stats_cards = [
            html.Div([html.Div("Closed", className="metric-label"), html.Div(str(stats_rows.get("closed_trades", 0)), className="metric-value")], className="metric-card accent-blue"),
            html.Div([html.Div("Winrate", className="metric-label"), html.Div(f"{float(stats_rows.get('winrate', 0.0) or 0.0):.1f}%", className="metric-value")], className="metric-card accent-green"),
            html.Div([html.Div("Net P/L", className="metric-label"), html.Div(_format_money(stats_rows.get("net_profit", 0.0)), className="metric-value")], className="metric-card accent-amber"),
            html.Div([html.Div("Max DD", className="metric-label"), html.Div(_format_money(stats_rows.get("max_drawdown", 0.0)), className="metric-value")], className="metric-card accent-pink"),
        ]
        latest_events = []
        for item in event_rows[:5]:
            event = as_mapping(item)
            latest_events.append(
                html.Li(f"{event.get('event_type', 'event')} • {event.get('reason', 'n/a')} • {event.get('decision', '') or 'decision'}")
            )
        if not latest_events:
            latest_events = [html.Li("No recent auto-trade events.")]

        constraints_panel = html.Div(
            [
                html.Div("Auto-Trade Constraints & Stats", className="section-label"),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div("Constraint Snapshot", className="subsection-label"),
                                html.Table(
                                    [
                                        html.Tr([html.Td(label, className="constraint-key"), html.Td(value, className="constraint-value")])
                                        for label, value in constraint_summary
                                    ],
                                    className="constraint-table",
                                ),
                            ],
                            className="constraint-block",
                        ),
                        html.Div(
                            [
                                html.Div("Blockers", className="subsection-label"),
                                html.Ul(blocker_items, className="analysis-list"),
                            ],
                            className="constraint-block",
                        ),
                    ],
                    className="constraint-stack",
                ),
                html.Div(stats_cards, className="metrics-grid"),
                html.Div(
                    [
                        html.Div("Recent Decisions", className="subsection-label"),
                        html.Ul(latest_events, className="analysis-list"),
                    ],
                    className="constraint-block",
                ),
            ],
            id="auto-trade-constraints-panel",
            className="panel",
        )

        mt5_error_summary = mt5_error_summary_data.get("total", len(mt5_error_rows))
        mt5_error_latest = mt5_error_summary_data.get("latest") if isinstance(mt5_error_summary_data.get("latest"), dict) else None
        mt5_error_by_broker = mt5_error_summary_data.get("by_broker") if isinstance(mt5_error_summary_data.get("by_broker"), dict) else {}
        mt5_error_card_items = [
            html.Div([html.Div("Total Errors", className="metric-label"), html.Div(str(mt5_error_summary), className="metric-value")], className="metric-card accent-blue"),
            html.Div([html.Div("Latest", className="metric-label"), html.Div(str((mt5_error_latest or {}).get("broker_name") or (mt5_error_latest or {}).get("broker_id") or "-"), className="metric-value")], className="metric-card accent-amber"),
            html.Div([html.Div("Brokers", className="metric-label"), html.Div(str(len(mt5_error_by_broker)), className="metric-value")], className="metric-card accent-green"),
        ]
        mt5_error_lines = []
        for item in mt5_error_rows[:6]:
            row = as_mapping(item)
            msg = str(row.get("message") or row.get("error") or row.get("details") or "MT5 error without message")
            broker = str(row.get("broker_name") or row.get("broker_id") or "unknown")
            when = row.get("timestamp") or row.get("created_at") or row.get("time") or row.get("ts")
            mt5_error_lines.append(html.Li(f"{broker} • {when} • {msg}"))
        if not mt5_error_lines:
            mt5_error_lines = [html.Li("No MT5 error logs recorded.")]

        mt5_diagnostics_panel = html.Div(
            [
                html.Div("MT5 Diagnostics", className="section-label"),
                html.Div("Read-only overview for terminal health; operational controls live in the top toolbar and Settings.", className="kv-line"),
                html.Div(mt5_error_card_items, className="metrics-grid"),
                html.Div(
                    [
                        html.Div("Recent MT5 Error Log", className="subsection-label"),
                        html.Ul(mt5_error_lines, className="analysis-list"),
                    ],
                    className="constraint-block",
                ),
                html.Div(
                    [
                        html.Button("Clear MT5 Error Log", id="clear-mt5-log-button", className="action-button neutral", n_clicks=0),
                        html.Div("No new MT5 errors recently.", id="mt5-diagnostics-panel-status", className="kv-line"),
                    ],
                    className="broker-panel-actions",
                ),
            ],
            id="mt5-diagnostics-panel",
            className="panel",
        )

        decision_event_rows = []
        for item in event_rows[:8]:
            event = as_mapping(item)
            decision_type = str(event.get("event_type") or event.get("decision") or "event")
            reason = str(event.get("reason") or event.get("message") or "n/a")
            ts = event.get("timestamp") or event.get("ts") or event.get("created_at")
            decision_event_rows.append(html.Li(f"{decision_type} • {reason} • {ts}"))
        if not decision_event_rows:
            decision_event_rows = [html.Li("No recent decisions available.")]

        event_log_panel = html.Div(
            [
                html.Div("Decision Event Log", className="section-label"),
                html.Ul(decision_event_rows, className="analysis-list"),
            ],
            id="event-log-panel",
            className="panel",
        )

        operational_panel = html.Div(
            [
                html.Div("Operational Overview", className="section-label"),
                html.Div(
                    [
                        html.Div([html.Span("Signal ", className=_signal_dot_class(last_signal)), html.Span(f"{signal_status}")], className="status-pill"),
                        html.Div(
                            [
                                html.Span("Broker ", className="status-dot pill-broker"),
                                html.Span(f"{len(broker_summary)} active"),
                            ],
                            className="status-pill",
                        ),
                        html.Div(
                            [
                                html.Span("MT5 ", className="status-dot pill-mt5-on" if mt5_connected else "status-dot pill-mt5-off"),
                                html.Span("Connected" if mt5_connected else "Offline"),
                            ],
                            className="status-pill",
                        ),
                        html.Div(
                            [
                                html.Span("Sync ", className=_sync_status_dot_class(background_sync_state)),
                                html.Span(sync_status_label),
                            ],
                            className="status-pill",
                        ),
                    ],
                    className="status-row",
                ),
                html.Div(
                    [
                        html.Div(f"Source: {indicators.get('source', 'market-data')}", className="kv-line"),
                        html.Div(f"Bid / Ask: {_format_number(indicators.get('bid', 0.0))} / {_format_number(indicators.get('ask', 0.0))}", className="kv-line"),
                        html.Div(f"Default Broker: {default_broker_data.get('name', '-') if default_broker_data else '-'}"),
                        html.Div(f"MT5 Sync Status: {sync_status_label}", className="kv-line"),
                    ],
                    className="kv-stack",
                ),
                html.Div(
                    [
                        html.Button("BUY", className="action-button buy"),
                        html.Button("SELL", className="action-button sell"),
                        html.Button("REFRESH", className="action-button neutral"),
                    ],
                    className="action-row",
                ),
                html.Div(
                    children=f"Auto Trade State: {'Enabled' if auto_trade_enabled else 'Disabled'}",
                    className="state-line",
                ),
            ],
            className="panel",
        )

        chart_panel = html.Div(
            [
                html.Div(
                    [
                        html.Div("Market Chart", className="section-label"),
                        html.Div(f"{symbol} • {timeframe} • {bars} bars", className="small-muted"),
                    ],
                    className="panel-header-row",
                ),
                dcc.Graph(
                    id="market-chart-live",
                    figure=market_fig,
                    config={"displayModeBar": False, "responsive": True},
                    style={"height": "520px", "width": "100%"},
                    className="panel-wide live-chart",
                ),
                html.Script(src="/assets/market_live_ws.js"),
            ],
            className="panel panel-wide panel-chart",
        )

        return html.Div(
            [
                degraded_banner,
                status_summary_panel,
                html.Div(metric_cards, className="metrics-grid"),
                chart_panel,
                html.Div(
                    [
                        signal_panel,
                        operational_panel,
                        runtime_panel,
                        broker_panel,
                        constraints_panel,
                        event_log_panel,
                        mt5_diagnostics_panel,
                    ],
                    className="overview-bottom-grid",
                ),
            ],
            className="page-layout",
        )

    try:
        return asyncio.run(_load_data())
    except Exception as exc:
        return html.Div([
            html.H3("Backend unavailable"),
            html.P(str(exc), className="error-text"),
        ], className="error-panel")
