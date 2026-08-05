import React from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AccountMonitor from "../AccountMonitor";

const API_BASE = "http://localhost:8000";

function jsonResponse(payload, ok = true, status = 200) {
  return Promise.resolve({
    ok,
    status,
    json: () => Promise.resolve(payload),
  });
}

function createFetchMock({ trainShouldFail = false } = {}) {
  return vi.fn((url, options = {}) => {
    const method = String(options.method || "GET").toUpperCase();
    const fullUrl = String(url || "");

    if (fullUrl === `${API_BASE}/account/state`) {
      return jsonResponse({
        balance: 1000,
        initial_balance: 1000,
        lot: 0.01,
        max_open_trades: 1,
        history: [],
        enable_real_trade: false,
        auto_trade_enabled: false,
        keep_terminal_alive: true,
      });
    }

    if (fullUrl.startsWith(`${API_BASE}/brokers?`)) {
      return jsonResponse([
        { id: 1, name: "Default Broker", platform: "mt5", execution_mode: "direct", is_active: true },
      ]);
    }

    if (fullUrl === `${API_BASE}/account/auto_trade_constraints`) {
      return jsonResponse({
        status: "ok",
        symbol: "XAUUSD",
        constraints: { can_open_order: true, volume_step: 0.01, volume_min: 0.01, volume_max: 1 },
      });
    }

    if (fullUrl.includes("/account/set_enable_real_trade") || fullUrl.includes("/account/set_auto_trade_enabled") || fullUrl.includes("/account/set_keep_terminal_alive")) {
      return jsonResponse({ status: "ok" });
    }

    if (fullUrl.startsWith(`${API_BASE}/account/auto_trade_ml_dataset`) && method === "GET") {
      return jsonResponse({
        status: "ok",
        rows: 1,
        dataset: [
          {
            trade_id: "ml-ds-1",
            symbol: "XAUUSD",
            risk_mode: "risk_percent",
            features: { atr: 11.2, spread_points: 48, signal_score: 0.72 },
            result: { profit: 23.5 },
          },
        ],
      });
    }

    if (fullUrl.startsWith(`${API_BASE}/account/auto_trade_ml_train`) && method === "POST") {
      if (trainShouldFail) {
        return jsonResponse({ status: "error", message: "train failed" }, false, 500);
      }
      return jsonResponse({
        status: "ok",
        dataset_rows: 30,
        result: { trained: true, model_type: "random_forest", rows: 30, trained_trade_count: 120 },
      });
    }

    if (fullUrl === `${API_BASE}/account/auto_trade_ml_export` && method === "POST") {
      return jsonResponse({
        status: "ok",
        export: {
          format: "json",
          rows: 100,
          path: "exports/auto_trade_dataset.json",
          filename: "auto_trade_dataset.json",
          download_url: "/account/auto_trade_ml_export_download?file=auto_trade_dataset.json",
        },
      });
    }

    if (fullUrl.includes("/account/set_trade_history_sync") || fullUrl.includes("/trade/sync_history")) {
      return jsonResponse({ status: "ok" });
    }

    if (fullUrl.startsWith(`${API_BASE}/brokers`)) {
      return jsonResponse({ status: "ok" });
    }

    return jsonResponse({ status: "ok" });
  });
}

describe("AccountMonitor adaptive ML toolkit", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("calls dataset/train/export endpoints from ML buttons", async () => {
    global.fetch = createFetchMock();
    const user = userEvent.setup();

    render(<AccountMonitor />);

    const datasetBtn = await screen.findByTestId("ml-dataset-btn");
    const trainBtn = screen.getByTestId("ml-train-btn");
    const exportBtn = screen.getByTestId("ml-export-btn");

    await user.click(datasetBtn);
    await user.click(trainBtn);
    await user.click(exportBtn);

    await waitFor(() => {
      const calls = global.fetch.mock.calls.map(([url, options]) => ({
        url: String(url),
        method: String(options?.method || "GET").toUpperCase(),
      }));
      expect(calls.some((c) => c.url.includes("/account/auto_trade_ml_dataset?limit=") && c.method === "GET")).toBe(true);
      expect(calls.some((c) => c.url.includes("/account/auto_trade_ml_train?limit=") && c.method === "POST")).toBe(true);
      expect(calls.some((c) => c.url.includes("/account/auto_trade_ml_export") && c.method === "POST")).toBe(true);
    });

    const downloadBtn = screen.getByTestId("ml-download-btn");
    expect(downloadBtn).toHaveAttribute("href", `${API_BASE}/account/auto_trade_ml_export_download?file=auto_trade_dataset.json`);
  });

  it("renders dataset preview rows after loading dataset", async () => {
    global.fetch = createFetchMock();
    const user = userEvent.setup();

    render(<AccountMonitor />);

    await user.click(await screen.findByTestId("ml-dataset-btn"));

    const tableBody = await screen.findByTestId("ml-dataset-table-body");
    expect(within(tableBody).getByText("ml-ds-1")).toBeInTheDocument();
    expect(within(tableBody).getByText("risk_percent")).toBeInTheDocument();
  });

  it("shows success notification when retrain succeeds", async () => {
    global.fetch = createFetchMock({ trainShouldFail: false });
    const user = userEvent.setup();

    render(<AccountMonitor />);

    await user.click(await screen.findByTestId("ml-train-btn"));

    expect(await screen.findByText(/Retrain berhasil/i)).toBeInTheDocument();
  });

  it("shows error notification when retrain fails", async () => {
    global.fetch = createFetchMock({ trainShouldFail: true });
    const user = userEvent.setup();

    render(<AccountMonitor />);

    await user.click(await screen.findByTestId("ml-train-btn"));

    expect(await screen.findByText(/train failed|Retrain model gagal/i)).toBeInTheDocument();
  });
});
