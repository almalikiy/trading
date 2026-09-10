const LEGACY_ENDPOINT_MAP = {
  "/account/state": "/account/state",
  "/account/auto_trade_health": "/account/auto_trade_health",
  "/account/auto_trade_constraints": "/account/auto_trade_constraints",
  "/account/set_auto_trade_enabled": "/account/set_auto_trade_enabled",
  "/account/set_keep_terminal_alive": "/account/set_keep_terminal_alive",
  "/account/set_enable_real_trade": "/account/set_enable_real_trade",
  "/brokers": "/brokers",
  "/brokers/default": "/brokers/default",
  "/trade/open_count": "/trade/open_count",
  "/trade/open_positions": "/trade/open_positions",
  "/trade/history": "/trade/history",
  "/trade/sync_history": "/trade/sync_history",
  "/mt5/error_log": "/mt5/error_log",
  "/mt5/status": "/mt5/status",
  "/signal": "/signal",
  "/ohlcv": "/ohlcv",
  "/dashboard/summary": "/dashboard/summary",
  "/orders": "/orders",
};

export function resolveApiUrl(url) {
  if (!url) return url;

  const parsed = new URL(url, window.location.origin);
  const pathname = parsed.pathname;
  const mapped = LEGACY_ENDPOINT_MAP[pathname] || pathname;

  if (mapped === pathname) {
    return url;
  }

  parsed.pathname = mapped;
  return parsed.toString();
}

export async function fetchJson(url, options = {}) {
  const resolvedUrl = resolveApiUrl(url);

  const response = await fetch(resolvedUrl, {
    headers: {
      Accept: "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const headerBag = response && response.headers ? response.headers : { get: () => "" };
  const contentType = headerBag.get("content-type") || "";
  const hasJson = typeof response.json === "function";
  const hasText = typeof response.text === "function";

  const payload = hasJson && (contentType.includes("application/json") || !hasText)
    ? await response.json()
    : hasText
      ? await response.text()
      : null;

  if (!response.ok) {
    const errorDetail =
      typeof payload === "object" && payload !== null
        ? payload.detail || payload.message || payload.error || (payload.status === "error" ? payload.message : null)
        : null;

    throw new Error(
      typeof errorDetail === "string" && errorDetail
        ? errorDetail
        : typeof payload === "string" && payload
          ? payload
          : "Request failed"
    );
  }

  return payload;
}

export async function getJson(url, init = {}) {
  return fetchJson(url, { method: "GET", ...init });
}

export async function postJson(url, body, init = {}) {
  return fetchJson(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
    ...init,
  });
}

export { LEGACY_ENDPOINT_MAP };
