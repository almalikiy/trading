export function toNullableNumber(value) {
  if (value === "" || value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function formatPrice(value, digits = 2) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "-";
  return parsed.toFixed(digits);
}

export function formatTradeTime(epochSeconds) {
  if (!epochSeconds) return "-";
  const value = Number(epochSeconds);
  if (!Number.isFinite(value) || value <= 0) return "-";
  const epochMs = value > 1_000_000_000_000 ? value : value * 1000;
  return new Date(epochMs).toLocaleString();
}

export function parseAutoOpenConfidence(reason) {
  const text = String(reason || "");
  const match = text.match(/auto_open:([0-9]+(?:\.[0-9]+)?)/i);
  if (!match) return null;
  const value = Number(match[1]);
  return Number.isFinite(value) ? value : null;
}

export function calcTradeFloatingPnl(trade, lastPrice) {
  if (!trade || lastPrice === null || lastPrice === undefined) return 0;

  const entry = Number(trade.entry);
  const lot = Number(trade.lot || 0);
  if (!Number.isFinite(entry) || !Number.isFinite(lot)) return 0;

  const scale = 100 * lot;
  const t = String(trade.type || "").toUpperCase();
  if (t === "BUY") return (lastPrice - entry) * scale;
  if (t === "SELL") return (entry - lastPrice) * scale;
  return 0;
}

export function canLateFollow({ signal, signalTime, signalPrice, currentPrice, maxDelaySec = 60, maxPriceDrift = 0.5 }) {
  if (!signal || signal === "wait" || !signalTime || currentPrice === null || currentPrice === undefined) return false;

  const nowEpoch = Math.floor(Date.now() / 1000);
  const delay = nowEpoch - signalTime;
  if (delay > maxDelaySec) return false;
  if (signalPrice === null || signalPrice === undefined) return true;

  return Math.abs(Number(currentPrice) - Number(signalPrice)) <= maxPriceDrift;
}

export function getSignalColor(signal) {
  if (signal === "buy") return "#1b5e20";
  if (signal === "sell") return "#b71c1c";
  return "#424242";
}
