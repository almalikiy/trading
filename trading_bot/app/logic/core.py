from __future__ import annotations

from typing import Any

SUPPORTED_TIMEFRAMES = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")
DEFAULT_SIGNAL_TIMEFRAMES = ("M1", "M5", "M15", "M30")


def normalize_timeframes(timeframes: list[str] | tuple[str, ...] | None) -> list[str]:
    if not timeframes:
        return list(DEFAULT_SIGNAL_TIMEFRAMES)
    normalized: list[str] = []
    for item in timeframes:
        value = str(item or "").strip().upper()
        if value in SUPPORTED_TIMEFRAMES and value not in normalized:
            normalized.append(value)
    if len(normalized) < 2:
        return list(DEFAULT_SIGNAL_TIMEFRAMES)
    return normalized


def calculate_indicators(rows: list[dict[str, Any]], atr_period: int = 14) -> dict[str, float]:
    if not rows:
        raise RuntimeError("No OHLCV rows")

    closes = [float(item.get("close") or 0.0) for item in rows]
    highs = [float(item.get("high") or 0.0) for item in rows]
    lows = [float(item.get("low") or 0.0) for item in rows]

    window = min(14, len(closes))
    recent = closes[-window:]
    sma = sum(recent) / max(1, len(recent))

    bb_window = min(20, len(closes))
    bb_recent = closes[-bb_window:]
    bb_mid = sum(bb_recent) / max(1, len(bb_recent))
    variance = sum((v - bb_mid) ** 2 for v in bb_recent) / max(1, len(bb_recent))
    std = variance ** 0.5

    gains = 0.0
    losses = 0.0
    for idx in range(1, len(recent)):
        delta = recent[idx] - recent[idx - 1]
        if delta >= 0:
            gains += delta
        else:
            losses -= delta
    avg_gain = gains / max(1, len(recent) - 1)
    avg_loss = losses / max(1, len(recent) - 1)
    if avg_loss == 0:
        rsi = 100.0 if avg_gain > 0 else 50.0
    else:
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))

    macd_fast = sum(closes[-min(12, len(closes)):]) / max(1, min(12, len(closes)))
    macd_slow = sum(closes[-min(26, len(closes)):]) / max(1, min(26, len(closes)))
    macd = macd_fast - macd_slow
    macd_signal = macd * 0.8

    atr_window = max(2, min(int(atr_period or 14), len(rows)))
    trs: list[float] = []
    for idx in range(1, len(rows)):
        prev_close = closes[idx - 1]
        tr = max(highs[idx] - lows[idx], abs(highs[idx] - prev_close), abs(lows[idx] - prev_close))
        trs.append(tr)
    atr = (sum(trs[-atr_window:]) / max(1, min(atr_window, len(trs)))) if trs else 0.0

    last_close = closes[-1]
    span = max(1e-9, (max(highs[-window:]) - min(lows[-window:])))
    stoch_k = ((last_close - min(lows[-window:])) / span) * 100.0
    stoch_d = (stoch_k + 50.0) / 2.0

    return {
        "bb_upper": bb_mid + (2 * std),
        "bb_lower": bb_mid - (2 * std),
        "bb_mid": bb_mid,
        "rsi": rsi,
        "macd": macd,
        "macd_signal": macd_signal,
        "stoch_k": stoch_k,
        "stoch_d": stoch_d,
        "sma": sma,
        "atr": atr,
    }


def generate_signal(indicators: dict[str, dict[str, float]], mode: str = "real") -> str:
    if not indicators:
        return "wait"

    if mode == "scalp":
        tfs = [tf for tf in indicators if tf in {"M1", "M5"}]
        if not tfs:
            return "wait"
        if all(indicators[tf]["macd"] > indicators[tf]["macd_signal"] for tf in tfs) and all(indicators[tf]["rsi"] < 80 for tf in tfs):
            return "buy"
        return "wait"

    if (
        all(v["rsi"] < 70 for v in indicators.values())
        and all(v["macd"] > v["macd_signal"] for v in indicators.values())
        and all(v["bb_lower"] < v["sma"] < v["bb_upper"] for v in indicators.values())
    ):
        return "buy"
    return "wait"


class SignalSimulator:
    def __init__(self) -> None:
        self.balance = 1000.0
        self.last_price: float | None = None
        self.open_trade = False
        self.pnl = 0.0

    def update(self, price: float, signal: str) -> dict[str, Any]:
        if signal == "buy" and not self.open_trade:
            self.last_price = price
            self.open_trade = True
        elif signal == "wait" and self.open_trade and self.last_price is not None:
            self.pnl = price - self.last_price
            self.balance += self.pnl
            self.open_trade = False
        return {"balance": self.balance, "open_trade": self.open_trade, "pnl": self.pnl}
