import React, { useEffect, useState } from "react";
import CandlestickChart from "./CandlestickChart";
import LineChart from "./LineChart";
import {
  Box,
  Typography,
  Paper,
  Grid,
  Button,
  TextField,
  Alert,
  ButtonGroup,
  Snackbar,
  Alert as MuiAlert,
  Select,
  MenuItem,
  InputLabel,
  FormControl,
  Switch,
  FormControlLabel,
  CssBaseline,
  Checkbox,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  CircularProgress,
  Chip,
} from "@mui/material";
import { ThemeProvider, createTheme, useTheme } from "@mui/material/styles";

const BACKEND_URLS = {
  mt5: {
    http: import.meta.env.VITE_BACKEND_URL,
    ws: import.meta.env.VITE_BACKEND_WS_URL,
  },
  sim: {
    http: "http://localhost:8002",
    ws: "ws://localhost:8002/ws/signal",
  },
};

const BROKERS_CACHE_KEY = "dashboard_brokers_cache_v1";
const DEFAULT_BROKER_CACHE_KEY = "dashboard_default_broker_cache_v1";

function getBackendUrl(engine, type = "http") {
  return BACKEND_URLS[engine]?.[type] || BACKEND_URLS.mt5[type];
}

function toNullableNumber(value) {
  if (value === "" || value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function calcTradeFloatingPnl(trade, lastPrice) {
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

function canLateFollow({ signal, signalTime, signalPrice, currentPrice, maxDelaySec = 60, maxPriceDrift = 0.5 }) {
  if (!signal || signal === "wait" || !signalTime || currentPrice === null || currentPrice === undefined) return false;
  const nowEpoch = Math.floor(Date.now() / 1000);
  const delay = nowEpoch - signalTime;
  if (delay > maxDelaySec) return false;
  if (signalPrice === null || signalPrice === undefined) return true;
  return Math.abs(Number(currentPrice) - Number(signalPrice)) <= maxPriceDrift;
}

function getSignalColor(signal) {
  if (signal === "buy") return "#1b5e20";
  if (signal === "sell") return "#b71c1c";
  return "#424242";
}

function parseAutoOpenConfidence(reason) {
  const text = String(reason || "");
  const match = text.match(/auto_open:([0-9]+(?:\.[0-9]+)?)/i);
  if (!match) return null;
  const value = Number(match[1]);
  return Number.isFinite(value) ? value : null;
}

function buildTradeStatusChips(trade) {
  const chips = [];
  const badges = Array.isArray(trade.strategy_badges) ? trade.strategy_badges : [];
  badges.forEach((b) => chips.push({ label: b, color: "primary", variant: "outlined" }));

  const conf = parseAutoOpenConfidence(trade.reason);
  if (conf !== null) {
    chips.push({
      label: `Conf ${(conf * 100).toFixed(0)}%`,
      color: conf >= 0.65 ? "success" : conf >= 0.55 ? "warning" : "default",
      variant: "filled",
    });
  }

  const exec = String(trade.execution_mode || "").toLowerCase();
  if (exec === "mouse") {
    chips.push({ label: "Manual/Mouse", color: "warning", variant: "filled" });
  } else if (exec === "direct") {
    chips.push({ label: "Direct", color: "success", variant: "outlined" });
  }

  return chips;
}

function formatTradeTime(epochSeconds) {
  if (!epochSeconds) return "-";
  const value = Number(epochSeconds);
  if (!Number.isFinite(value) || value <= 0) return "-";
  const epochMs = value > 1_000_000_000_000 ? value : value * 1000;
  return new Date(epochMs).toLocaleString();
}

function getClientTimeZoneLabel() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "Local";
  } catch {
    return "Local";
  }
}

export default function App( { darkMode, setDarkMode }) {
  const [engine, setEngine] = useState("mt5");
  const [tradeMode, setTradeMode] = useState("scalp");
  // const [darkMode, setDarkMode] = useState(false);

  const [symbol, setSymbol] = useState("XAUUSD");
  const [tf, setTf] = useState("M1");
  const [barCount, setBarCount] = useState(60);
  const [chartMode, setChartMode] = useState("candlestick");

  const [signal, setSignal] = useState("wait");
  const [prevSignal, setPrevSignal] = useState("wait");
  const [indicators, setIndicators] = useState({});
  const [signalError, setSignalError] = useState(null);

  const [ohlcv, setOhlcv] = useState([]);
  const [ohlcvError, setOhlcvError] = useState(false);
  const [ohlcvWarning, setOhlcvWarning] = useState("");

  const [accountState, setAccountState] = useState({
    balance: 0,
    lot: 0.01,
    auto_trade_enabled: false,
    keep_terminal_alive: true,
    auto_analytic_tpsl: false,
    tp_value: 0.5,
    sl_value: null,
  });
  const [accountSettingsLoaded, setAccountSettingsLoaded] = useState(false);
  const [autoTradeEnabled, setAutoTradeEnabled] = useState(false);
  const [keepTerminalAlive, setKeepTerminalAlive] = useState(true);

  const [brokers, setBrokers] = useState([]);
  const [defaultBroker, setDefaultBroker] = useState(null);
  const [selectedBrokerId, setSelectedBrokerId] = useState("");
  const [selectedOrderMethod, setSelectedOrderMethod] = useState("mouse");
  const [manualLot, setManualLot] = useState(0.01);
  const [manualTradeLoading, setManualTradeLoading] = useState(false);
  const [brokerOrderStatus, setBrokerOrderStatus] = useState(null);

  const [lastSignalTime, setLastSignalTime] = useState(null);
  const [lastSignalPrice, setLastSignalPrice] = useState(null);
  const [lastActionableSignal, setLastActionableSignal] = useState("wait");
  const [lateFollowMsg, setLateFollowMsg] = useState("");

  const [openTradeCount, setOpenTradeCount] = useState(0);
  const [openPositions, setOpenPositions] = useState([]);
  const [positionsLoading, setPositionsLoading] = useState(true);
  const [tpSlDrafts, setTpSlDrafts] = useState({});
  const [tradeActionLoading, setTradeActionLoading] = useState({});
  const [autoTradeHealth, setAutoTradeHealth] = useState(null);

  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMsg, setSnackbarMsg] = useState("");

  const lastPrice = ohlcv && ohlcv.length > 0 ? Number(ohlcv[ohlcv.length - 1].close) : null;
  const totalFloatingPnl = openPositions.reduce((sum, trade) => sum + calcTradeFloatingPnl(trade, lastPrice), 0);

  const theme = useTheme();
  const clientTimeZone = getClientTimeZoneLabel();

  const refreshAccountState = () => {
    fetch(`${getBackendUrl("mt5", "http")}/account/state`)
      .then((res) => res.json())
      .then((data) => {
        setAccountState(data);
        setAutoTradeEnabled(!!data.auto_trade_enabled);
        setKeepTerminalAlive(data.keep_terminal_alive !== false);
        setManualLot(Math.max(0.01, Number(data.lot || 0.01)));
        setAccountSettingsLoaded(true);
      })
      .catch(() => {});
  };

  const refreshBrokers = () => {
    fetch(`${getBackendUrl("mt5", "http")}/brokers?include_inactive=true`)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load brokers");
        return res.json();
      })
      .then((data) => {
        const items = Array.isArray(data) ? data : [];
        if (items.length > 0) {
          localStorage.setItem(BROKERS_CACHE_KEY, JSON.stringify(items));
        }
        setBrokers((prev) => {
          if (items.length > 0) return items;
          return prev;
        });
      })
      .catch(() => {
        try {
          const raw = localStorage.getItem(BROKERS_CACHE_KEY);
          const cached = raw ? JSON.parse(raw) : [];
          if (Array.isArray(cached) && cached.length > 0) {
            setBrokers((prev) => (prev.length > 0 ? prev : cached));
          }
        } catch {
          // Ignore cache parse failures.
        }
      });

    fetch(`${getBackendUrl("mt5", "http")}/brokers/default`)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load default broker");
        return res.json();
      })
      .then((data) => {
        if (data && data.id) {
          localStorage.setItem(DEFAULT_BROKER_CACHE_KEY, JSON.stringify(data));
          setDefaultBroker(data);
          setSelectedBrokerId(String(data.id));
          if (data.execution_mode) setSelectedOrderMethod(data.execution_mode);
     
          if (data.default_symbol) {
            setSymbol(data.default_symbol);
          }
          
          setBrokers((prev) => {
            const exists = prev.some((b) => String(b.id) === String(data.id));
            return exists ? prev : [data, ...prev];
          });
        }
      })
      .catch(() => {
        try {
          const raw = localStorage.getItem(DEFAULT_BROKER_CACHE_KEY);
          const cached = raw ? JSON.parse(raw) : null;
          if (cached && cached.id) {
            setDefaultBroker(cached);
            setSelectedBrokerId((prev) => prev || String(cached.id));
            if (cached.execution_mode) setSelectedOrderMethod((prev) => prev || cached.execution_mode);
            if (cached.default_symbol) {
              setSymbol(cached.default_symbol);
            }
            setBrokers((prev) => {
              const exists = prev.some((b) => String(b.id) === String(cached.id));
              return exists ? prev : [cached, ...prev];
            });
          }
        } catch {
          // Ignore cache parse failures.
        }
      });
  };

  useEffect(() => {
    try {
      const rawBrokers = localStorage.getItem(BROKERS_CACHE_KEY);
      const cachedBrokers = rawBrokers ? JSON.parse(rawBrokers) : [];
      if (Array.isArray(cachedBrokers) && cachedBrokers.length > 0) {
        setBrokers((prev) => (prev.length > 0 ? prev : cachedBrokers));
      }

      const rawDefault = localStorage.getItem(DEFAULT_BROKER_CACHE_KEY);
      const cachedDefault = rawDefault ? JSON.parse(rawDefault) : null;
      if (cachedDefault && cachedDefault.id) {
        setDefaultBroker((prev) => prev || cachedDefault);
        setSelectedBrokerId((prev) => prev || String(cachedDefault.id));
        if (cachedDefault.execution_mode) {
          setSelectedOrderMethod((prev) => prev || cachedDefault.execution_mode);
        }
      }
    } catch {
      // Ignore cache parse failures.
    }
  }, []);

  const refreshOpenCount = () => {
    fetch(`${getBackendUrl("mt5", "http")}/trade/open_count`)
      .then((res) => res.json())
      .then((data) => setOpenTradeCount(Number(data.open_count || 0)))
      .catch(() => setOpenTradeCount(0));
  };

  const refreshOpenPositions = () => {
    fetch(`${getBackendUrl("mt5", "http")}/trade/open_positions`)
      .then((res) => res.json())
      .then((rows) => {
        const items = Array.isArray(rows) ? rows : [];
        setOpenPositions(items);
        setTpSlDrafts((prev) => {
          const next = { ...prev };
          const activeIds = new Set(items.map((t) => String(t.trade_id)));
          items.forEach((t) => {
            const id = String(t.trade_id);
            if (!next[id]) {
              next[id] = {
                tpValue: t.tpValue ?? "",
                slValue: t.slValue ?? "",
              };
            }
          });
          Object.keys(next).forEach((id) => {
            if (!activeIds.has(id)) delete next[id];
          });
          return next;
        });
      })
      .catch(() => setOpenPositions([]))
      .finally(() => setPositionsLoading(false));
  };

  const refreshAutoTradeHealth = () => {
    fetch(`${getBackendUrl("mt5", "http")}/account/auto_trade_health`)
      .then((res) => res.json())
      .then((data) => setAutoTradeHealth(data))
      .catch(() => setAutoTradeHealth(null));
  };

  useEffect(() => {
    let inFlight = false;
    refreshAccountState();
    refreshOpenCount();
    refreshOpenPositions();
    refreshAutoTradeHealth();
    refreshBrokers();
    const timer = setInterval(() => {
      if (inFlight) return;
      inFlight = true;
      refreshAccountState();
      refreshOpenCount();
      refreshOpenPositions();
      refreshAutoTradeHealth();
      inFlight = false;
    }, 5000);
    return () => {
      clearInterval(timer);
      inFlight = false;
    };
  }, []);

  useEffect(() => {
    const timer = setInterval(() => {
      refreshBrokers();
    }, 30000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!accountSettingsLoaded) return;
    fetch(`${getBackendUrl("mt5", "http")}/account/set_auto_trade_enabled`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(autoTradeEnabled),
    });
  }, [autoTradeEnabled, accountSettingsLoaded]);

  useEffect(() => {
    if (!accountSettingsLoaded) return;
    fetch(`${getBackendUrl("mt5", "http")}/account/set_keep_terminal_alive`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(keepTerminalAlive),
    });
  }, [keepTerminalAlive, accountSettingsLoaded]);

  useEffect(() => {
    const baseUrl = getBackendUrl(engine, "http");
    let inFlight = false;
    const fetchSignal = () => {
      if (inFlight) return;
      inFlight = true;
      fetch(`${baseUrl}/signal?symbol=${symbol}&mode=${tradeMode}`)
        .then((res) => res.json())
        .then((data) => {
          if (data.error) {
            setSignalError(data.error + (data.details ? `: ${JSON.stringify(data.details)}` : ""));
            setSignal("wait");
            setIndicators({});
            return;
          }
          setSignalError(null);
          setPrevSignal(signal);
          setSignal(data.signal || "wait");
          setIndicators(data.indicators || {});
        })
        .catch(() => {})
        .finally(() => {
          inFlight = false;
        });
    };
    fetchSignal();
    const timer = setInterval(fetchSignal, 3000);
    return () => {
      clearInterval(timer);
      inFlight = false;
    };
  }, [symbol, tradeMode, engine]);

  useEffect(() => {
    const baseUrl = getBackendUrl(engine, "http");
    let inFlight = false;
    const fetchOhlcv = () => {
      if (inFlight) return;
      inFlight = true;
      fetch(`${baseUrl}/ohlcv?symbol=${symbol}&timeframe=${tf}&bars=${barCount}`)
        .then((res) => {
          if (!res.ok) throw new Error("Backend not active");
          return res.json();
        })
        .then((data) => {
          if (!Array.isArray(data)) {
            setOhlcv([]);
            setOhlcvWarning("Format data OHLCV tidak valid dari backend.");
            setOhlcvError(true);
            return;
          }
          if (data.length < barCount) {
            setOhlcv([]);
            setOhlcvWarning(`Data tidak cukup untuk menampilkan ${barCount} bar. Hanya tersedia ${data.length} bar.`);
            setOhlcvError(true);
            return;
          }
          setOhlcv(data);
          setOhlcvError(false);
          setOhlcvWarning("");
        })
        .catch(() => {
          setOhlcv([]);
          setOhlcvError(true);
          setOhlcvWarning("");
        })
        .finally(() => {
          inFlight = false;
        });
    };
    fetchOhlcv();
    const timer = setInterval(fetchOhlcv, 5000);
    return () => {
      clearInterval(timer);
      inFlight = false;
    };
  }, [symbol, tf, barCount, engine]);

  useEffect(() => {
    if (prevSignal && signal && prevSignal !== signal) {
      setSnackbarMsg(`Signal berubah dari ${prevSignal.toUpperCase()} ke ${signal.toUpperCase()}`);
      setSnackbarOpen(true);
    }
    if (signal === "buy" || signal === "sell") {
      setLastSignalTime(Math.floor(Date.now() / 1000));
      setLastSignalPrice(lastPrice);
      setLastActionableSignal(signal);
    }
  }, [signal, prevSignal, lastPrice]);

  const activeBroker =
    brokers.find((b) => String(b.id) === String(selectedBrokerId)) ||
    (defaultBroker && String(defaultBroker.id) === String(selectedBrokerId) ? defaultBroker : null) ||
    defaultBroker ||
    brokers.find((b) => b.is_default) ||
    brokers[0] ||
    null;

  const selectedBroker = brokers.find((b) => String(b.id) === String(selectedBrokerId)) || activeBroker || null;
  const selectedBrokerIsMt4 = String(selectedBroker?.platform || "").toLowerCase() === "mt4";

  useEffect(() => {
    if (!selectedBrokerId && activeBroker) {
      setSelectedBrokerId(String(activeBroker.id));
      if (activeBroker.execution_mode) {
        const nextMode = String(activeBroker.platform || "").toLowerCase() === "mt4" ? "mouse" : activeBroker.execution_mode;
        setSelectedOrderMethod(nextMode);
      }
      if (activeBroker.default_symbol) {
        setSymbol(activeBroker.default_symbol);
      }
    }
  }, [selectedBrokerId, activeBroker]);

  useEffect(() => {
    if (selectedBrokerIsMt4 && selectedOrderMethod === "direct") {
      setSelectedOrderMethod("mouse");
    }
  }, [selectedBrokerIsMt4, selectedOrderMethod]);

  useEffect(() => {
    const brokerId = selectedBrokerId || (activeBroker ? String(activeBroker.id) : "") || (defaultBroker ? String(defaultBroker.id) : "");
    if (!brokerId) {
      setBrokerOrderStatus(null);
      return;
    }

    let inFlight = false;
    const fetchBrokerOrderStatus = () => {
      if (inFlight) return;
      inFlight = true;
      fetch(`${getBackendUrl("mt5", "http")}/brokers/${brokerId}/order_status?symbol=${symbol}`)
        .then((res) => {
          if (!res.ok) throw new Error("Failed");
          return res.json();
        })
        .then((data) => setBrokerOrderStatus(data))
        .catch(() => setBrokerOrderStatus({ can_open_order: false, reason: "status_endpoint_unavailable" }))
        .finally(() => {
          inFlight = false;
        });
    };

    fetchBrokerOrderStatus();
    const timer = setInterval(fetchBrokerOrderStatus, 15000);
    return () => {
      clearInterval(timer);
      inFlight = false;
    };
  }, [selectedBrokerId, activeBroker, defaultBroker, symbol]);

  const mapBrokerOrderStatusText = (status) => {
    if (!status) return "status tidak tersedia";
    if (status.can_open_order) return "New Order: enabled";

    const reasonMap = {
      terminal_path_missing: "terminal path belum diisi",
      mt5_initialize_failed: "gagal init MT5 terminal",
      terminal_disconnected: "terminal tidak terkoneksi",
      terminal_trade_disabled: "AutoTrading terminal OFF (New Order disabled)",
      account_trade_disabled: "akun tidak mengizinkan trade",
      symbol_not_visible: `symbol ${symbol} tidak visible`,
      no_tick_data: `tick ${symbol} belum tersedia`,
      no_broker_available: "broker tidak tersedia",
      status_endpoint_unavailable: "status endpoint tidak tersedia",
    };
    return reasonMap[status.reason] || `New Order: disabled (${status.reason || "unknown"})`;
  };

  const handleManualOpen = async (tradeType) => {
    const lot = Math.max(0.01, Number(manualLot || 0.01));
    setManualTradeLoading(true);
    try {
      const res = await fetch(`${getBackendUrl("mt5", "http")}/trade/open_v2`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol,
          lot,
          trade_type: tradeType,
          signal_time: Math.floor(Date.now() / 1000),
          broker_id: selectedBrokerId ? Number(selectedBrokerId) : null,
          order_method: selectedOrderMethod,
        }),
      });
      const data = await res.json();
      if (!res.ok || data.status === "error") {
        throw new Error(data.message || "Failed to open trade.");
      }
      setSnackbarMsg(`Manual ${tradeType.toUpperCase()} order sent.`);
      setSnackbarOpen(true);
      refreshOpenPositions();
      refreshOpenCount();
    } catch (err) {
      setSnackbarMsg(String(err.message || "Failed to open trade."));
      setSnackbarOpen(true);
    } finally {
      setManualTradeLoading(false);
    }
  };

  const handleSaveTradeTPSL = async (tradeId) => {
    const id = String(tradeId);
    const draft = tpSlDrafts[id] || { tpValue: "", slValue: "" };
    setTradeActionLoading((prev) => ({ ...prev, [id]: true }));
    try {
      const res = await fetch(`${getBackendUrl("mt5", "http")}/trade/update_tpsl`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          trade_id: id,
          tp_value: toNullableNumber(draft.tpValue),
          sl_value: toNullableNumber(draft.slValue),
        }),
      });
      const data = await res.json();
      if (!res.ok || data.status !== "ok") {
        throw new Error(data.message || "Failed to update TP/SL.");
      }
      setSnackbarMsg("TP/SL updated from backend.");
      setSnackbarOpen(true);
      refreshOpenPositions();
    } catch (err) {
      setSnackbarMsg(String(err.message || "Failed to update TP/SL."));
      setSnackbarOpen(true);
    } finally {
      setTradeActionLoading((prev) => ({ ...prev, [id]: false }));
    }
  };

  const handleCloseTrade = async (trade, index) => {
    const id = String(trade.trade_id || trade.ticket || index);
    setTradeActionLoading((prev) => ({ ...prev, [id]: true }));
    try {
      let res;
      if (String(trade.execution_mode || "").toLowerCase() === "mouse") {
        res = await fetch(`${getBackendUrl("mt5", "http")}/trade/close_by_index`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ index }),
        });
      } else {
        res = await fetch(`${getBackendUrl("mt5", "http")}/trade/close`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            symbol: trade.symbol,
            lot: trade.lot,
            ticket: trade.ticket,
          }),
        });
      }
      const data = await res.json();
      if (!res.ok || data.status === "error") {
        throw new Error(data.message || "Failed to close trade.");
      }
      setSnackbarMsg("Trade close request sent to backend.");
      setSnackbarOpen(true);
      refreshOpenPositions();
      refreshOpenCount();
      refreshAccountState();
    } catch (err) {
      setSnackbarMsg(String(err.message || "Failed to close trade."));
      setSnackbarOpen(true);
    } finally {
      setTradeActionLoading((prev) => ({ ...prev, [id]: false }));
    }
  };

  return (
      <Box sx={{ p: { xs: 1, sm: 2 }, maxWidth: 1200, mx: "auto", width: "100%" ,
                bgcolor: "background.default",
                minHeight: "100vh", 
              }}>
        <Snackbar
          open={snackbarOpen}
          autoHideDuration={2500}
          onClose={() => setSnackbarOpen(false)}
          anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
        >
          <MuiAlert onClose={() => setSnackbarOpen(false)} severity={snackbarMsg.includes("error") ? "error" : "success"} sx={{ width: "100%" }}>
            {snackbarMsg}
          </MuiAlert>
        </Snackbar>

        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 1, gap: 2, flexWrap: "wrap" }}>
          <Typography variant="h4">Trading Signal Dashboard</Typography>
          <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel id="engine-label">Engine</InputLabel>
              <Select labelId="engine-label" value={engine} label="Engine" onChange={(e) => setEngine(e.target.value)}>
                <MenuItem value="mt5">MT5 (Live)</MenuItem>
                <MenuItem value="sim">Simulation</MenuItem>
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel id="trade-mode-label">Mode</InputLabel>
              <Select labelId="trade-mode-label" value={tradeMode} label="Mode" onChange={(e) => setTradeMode(e.target.value)}>
                <MenuItem value="normal">Normal</MenuItem>
                <MenuItem value="scalp">Scalp</MenuItem>
              </Select>
            </FormControl>
          </Box>
        </Box>

        {signalError && <Alert severity="error" sx={{ mb: 2 }}>{signalError}</Alert>}
        {ohlcvError && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            {ohlcvWarning || "Candlestick data not available."}
          </Alert>
        )}

        <Paper
          sx={{
            p: { xs: 1, sm: 2 },
            mb: 2,
            overflowX: "auto",
            width: "100%",
            border: `2px solid ${signal === "wait" ? "#bdbdbd" : getSignalColor(signal)}`,
            animation: signal === "wait" ? "none" : "tradePanelPulse 1s infinite",
            "@keyframes tradePanelPulse": {
              "0%": { backgroundColor: "transparent" },
              "50%": { backgroundColor: signal === "buy" ? "rgba(56,142,60,0.10)" : "rgba(211,47,47,0.10)" },
              "100%": { backgroundColor: "transparent" },
            },
          }}
        >
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} sm={3}>
              <TextField label="Symbol" value={symbol} onChange={(e) => setSymbol(e.target.value)} size="small" fullWidth />
            </Grid>
            <Grid item xs={12} sm={4}>
              <ButtonGroup variant="outlined" color="primary" size="small">
                {["M1", "M5", "M15", "M30"].map((opt) => (
                  <Button key={opt} variant={tf === opt ? "contained" : "outlined"} onClick={() => setTf(opt)}>{opt}</Button>
                ))}
              </ButtonGroup>
            </Grid>
            <Grid item xs={12} sm={3}>
              <FormControl size="small" fullWidth>
                <InputLabel id="bar-count-label">Range</InputLabel>
                <Select labelId="bar-count-label" value={barCount} label="Range" onChange={(e) => setBarCount(Number(e.target.value))}>
                  <MenuItem value={30}>30 Bars</MenuItem>
                  <MenuItem value={60}>60 Bars</MenuItem>
                  <MenuItem value={120}>120 Bars</MenuItem>
                  <MenuItem value={240}>240 Bars</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={2}>
              <Button variant="contained" color="primary" fullWidth onClick={() => { setSymbol(symbol); setTf(tf); }}>
                Update
              </Button>
            </Grid>
          </Grid>
        </Paper>

        <Paper sx={{ p: { xs: 1, sm: 2 }, mb: 2, overflowX: "auto", width: "100%" }}>
          <Box sx={{ display: "flex", flexDirection: { xs: "column", md: "row" }, gap: 2 }}>
            {/* Panel Signal */}
            <Box sx={{ flex: 1, minWidth: 0, borderRight: { md: "1px solid #eee" }, 
              borderRadius: 1, border: `2px solid ${signal === "wait" ? "#bdbdbd" : getSignalColor(signal)}`, p: 2,
              animation: signal === "wait" ? "none" : "signalPulse 1s infinite",
              "@keyframes signalPulse": {
                "0%": { backgroundColor: "transparent" },
                "50%": {
                  backgroundColor:
                    signal === "buy"
                      ? "rgba(56,142,60,0.10)"
                      : "rgba(211,47,47,0.10)",
                },
                "100%": { backgroundColor: "transparent" },
              },
            }}>
              <Typography variant="h6" sx={{ fontWeight: "bold", letterSpacing: 2 }}>
                Signal: <b style={{ color: signal === "buy" ? "#1b5e20" : "#424242" }}>{signal ? signal.toUpperCase() : "-"}</b>
              </Typography>
              {lastPrice !== null && (
                <Typography variant="body2" sx={{ mt: 1, fontWeight: "bold", color: "#1976d2" }}>
                  Current Price: {lastPrice.toFixed(2)}
                </Typography>
              )}
              {indicators && indicators[tf] ? (
                <Box sx={{ mt: 1 }}>
                  <Typography variant="subtitle2">Summary {symbol} {tf}:</Typography>
                  <ul style={{ margin: 0, paddingLeft: 18, fontSize: 14 }}>
                    <li>RSI: {indicators[tf].rsi?.toFixed(2)}</li>
                    <li>MACD: {indicators[tf].macd?.toFixed(2)} | Signal: {indicators[tf].macd_signal?.toFixed(2)}</li>
                    <li>Bollinger: {indicators[tf].bb_lower?.toFixed(2)} - {indicators[tf].bb_mid?.toFixed(2)} - {indicators[tf].bb_upper?.toFixed(2)}</li>
                    <li>SMA: {indicators[tf].sma?.toFixed(2)}</li>
                    <li>Stoch K/D: {indicators[tf].stoch_k?.toFixed(2)} / {indicators[tf].stoch_d?.toFixed(2)}</li>
                  </ul>
                </Box>
              ) : null}
            </Box>

            {/* Panel Trading */}
            <Box sx={{ flex: 1, minWidth: 0, borderLeft: { md: "1px solid #eee" }, pl: { md: 2, xs: 0 }, mt: { xs: 2, md: 0 },
                borderRadius: 1,
                border: `2px solid ${signal === "wait" ? "#bdbdbd" : getSignalColor(signal)}`,
                animation: signal === "wait" ? "none" : "tradePanelPulse 1s infinite",
                "@keyframes tradePanelPulse": {
                  "0%": { backgroundColor: "transparent" },
                  "50%": { backgroundColor: signal === "buy" ? "rgba(56,142,60,0.10)" : "rgba(211,47,47,0.10)" },
                  "100%": { backgroundColor: "transparent" },
                },
              }}
            >
              <Typography variant="subtitle1" sx={{ fontWeight: "bold", letterSpacing: 1, mb: 1 }}>Trading Panel</Typography>
              <Typography variant="body2">
                Total Balance: <span style={{ color: accountState.balance < 0 ? "red" : undefined }}>${Number(accountState.balance || 0).toFixed(2)}</span>
                {" | "}Mode: <b style={{ color: accountState.enable_real_trade ? "#1b5e20" : "#888" }}>{accountState.enable_real_trade ? "REAL (MT5)" : "SIMULATION"}</b>
                {" | "}Total Floating P/L: <span style={{ color: totalFloatingPnl < 0 ? "red" : "#1b5e20" }}>{Number(totalFloatingPnl || 0).toFixed(2)}</span>
                {" | "}Open Count(DB): {openTradeCount}
              </Typography>

              <Typography variant="body2" sx={{ mt: 0.5 }}>
                Broker: <b>{activeBroker ? (activeBroker.name.length > 24 ? `${activeBroker.name.slice(0, 24)}...` : activeBroker.name) : "-"}</b>
                {" | "}
                <span
                  style={{
                    color: brokerOrderStatus?.can_open_order ? "#1b5e20" : "#b71c1c",
                    fontWeight: 600,
                  }}
                >
                  {mapBrokerOrderStatusText(brokerOrderStatus)}
                </span>
              </Typography>

              <Box sx={{ mt: 1 }}>
                <Typography variant="caption" sx={{ fontWeight: 700, mr: 1 }}>
                  Auto-Trade Health:
                </Typography>
                {autoTradeHealth?.active ? (
                  <Chip size="small" color="success" label="ACTIVE" />
                ) : (
                  <Chip size="small" color="error" label="BLOCKED" />
                )}
                <Button
                  size="small"
                  variant="text"
                  sx={{ ml: 1 }}
                  onClick={refreshAutoTradeHealth}
                >
                  refresh health
                </Button>

                {Array.isArray(autoTradeHealth?.blockers) && autoTradeHealth.blockers.length > 0 ? (
                  <Box sx={{ mt: 0.5 }}>
                    {autoTradeHealth.blockers.slice(0, 3).map((msg, idx) => (
                      <Typography key={`${msg}-${idx}`} variant="caption" color="error.main" sx={{ display: "block" }}>
                        - {msg}
                      </Typography>
                    ))}
                  </Box>
                ) : (
                  <Typography variant="caption" color="success.main" sx={{ display: "block", mt: 0.5 }}>
                    Semua gate utama lolos. Auto-trader siap eksekusi.
                  </Typography>
                )}
              </Box>

              <Box sx={{ display: "flex", alignItems: "center", mt: 1, gap: 2, flexWrap: "wrap" }}>
                <FormControlLabel
                  control={<Switch checked={autoTradeEnabled} onChange={(e) => setAutoTradeEnabled(e.target.checked)} />}
                  label="Auto Trade Backend"
                />
                <FormControlLabel
                  control={<Switch checked={keepTerminalAlive} onChange={(e) => setKeepTerminalAlive(e.target.checked)} />}
                  label="Keep Terminal Alive"
                />
              </Box>

              <Box sx={{ display: "flex", alignItems: "center", mt: 1, gap: 2, flexWrap: "wrap" }}>
                <FormControl size="small" sx={{ minWidth: 180 }}>
                  <InputLabel id="manual-broker-label">Broker</InputLabel>
                  <Select
                    labelId="manual-broker-label"
                    label="Broker"
                    value={selectedBrokerId}
                    onChange={(e) => {
                      const nextId = e.target.value;
                      setSelectedBrokerId(nextId);
                      const broker = brokers.find((b) => String(b.id) === String(nextId));
                      if (broker?.execution_mode) {
                        const nextMode = String(broker.platform || "").toLowerCase() === "mt4" ? "mouse" : broker.execution_mode;
                        setSelectedOrderMethod(nextMode);
                      }
                    }}
                  >
                    {brokers.map((b) => (
                      <MenuItem key={b.id} value={String(b.id)}>
                        {b.name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <FormControl size="small" sx={{ minWidth: 150 }}>
                  <InputLabel id="manual-exec-label">Exec</InputLabel>
                  <Select
                    labelId="manual-exec-label"
                    label="Exec"
                    value={selectedOrderMethod}
                    onChange={(e) => setSelectedOrderMethod(e.target.value)}
                  >
                    <MenuItem value="mouse">mouse</MenuItem>
                    {!selectedBrokerIsMt4 ? <MenuItem value="direct">direct</MenuItem> : null}
                  </Select>
                </FormControl>
                <TextField
                  label="Lot"
                  size="small"
                  type="number"
                  value={manualLot}
                  onChange={(e) => setManualLot(Math.max(0.01, Number(e.target.value || 0.01)))}
                  sx={{ width: 110 }}
                  inputProps={{ min: 0.01, step: 0.01 }}
                />
                <Button
                  variant="contained"
                  color="success"
                  disabled={manualTradeLoading}
                  onClick={() => handleManualOpen("buy")}
                >
                  Buy
                </Button>
                <Button
                  variant="contained"
                  color="error"
                  disabled={manualTradeLoading}
                  onClick={() => handleManualOpen("sell")}
                >
                  Sell
                </Button>
              </Box>

              <Box sx={{ display: "flex", alignItems: "center", mt: 1, gap: 2, flexWrap: "wrap" }}>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => {
                    const ok = canLateFollow({
                      signal: lastActionableSignal,
                      signalTime: lastSignalTime,
                      signalPrice: lastSignalPrice,
                      currentPrice: lastPrice,
                      maxDelaySec: 60,
                      maxPriceDrift: 0.5,
                    });
                    if (ok) {
                      setLateFollowMsg(`Sinyal ${String(lastActionableSignal).toUpperCase()} masih relevan untuk late entry.`);
                    } else {
                      setLateFollowMsg("Late entry sudah tidak relevan untuk sinyal terakhir.");
                    }
                  }}
                >
                  Check Late Entry
                </Button>
                {lateFollowMsg ? (
                  <Typography variant="caption" color={lateFollowMsg.includes("masih relevan") ? "success.main" : "error.main"}>
                    {lateFollowMsg}
                  </Typography>
                ) : null}
              </Box>
              {openTradeCount > 1 ? (
                <Typography variant="caption" color="warning.main" sx={{ display: "block", mt: 0.5 }}>
                  Trade aktif lebih dari satu: gunakan tombol Close per row pada panel Active Trades.
                </Typography>
              ) : null}

              <Box sx={{ display: "flex", alignItems: "center", mt: 0.5, gap: 2, flexWrap: "wrap" }}>
                <FormControlLabel
                  control={<Checkbox checked={accountState.auto_analytic_tpsl === true} disabled />}
                  label={<Typography variant="caption" color="text.secondary">Auto Analytic TP/SL dikontrol backend</Typography>}
                />
              </Box>
            </Box>
          </Box>
        </Paper>

        <Paper sx={{ p: { xs: 1, sm: 2 }, mb: 2, overflowX: "auto", width: "100%" }}>
          <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 1 }}>
            <Typography variant="h6">Active Trades</Typography>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap" }}>
              <Chip size="small" variant="outlined" label={`Time Zone: ${clientTimeZone}`} />
              <Button size="small" variant="outlined" onClick={() => { refreshOpenPositions(); refreshOpenCount(); }}>
                Refresh
              </Button>
            </Box>
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
            Nilai TP/SL di tabel adalah jarak harga dari entry untuk auto-close backend (bukan nilai floating P/L langsung), dan dapat menyesuaikan dinamis saat trailing/break-even aktif.
          </Typography>

          {positionsLoading ? (
            <Box sx={{ py: 2, display: "flex", justifyContent: "center" }}>
              <CircularProgress size={22} />
            </Box>
          ) : openPositions.length === 0 ? (
            <Typography variant="body2" color="text.secondary">Tidak ada trade aktif di backend.</Typography>
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Type</TableCell>
                    <TableCell>Symbol</TableCell>
                    <TableCell>Ticket</TableCell>
                    <TableCell>Lot</TableCell>
                    <TableCell>Entry</TableCell>
                    <TableCell>Open Time (Local)</TableCell>
                    <TableCell>Current</TableCell>
                    <TableCell>Floating (Est.)</TableCell>
                    <TableCell>TP</TableCell>
                    <TableCell>SL</TableCell>
                    <TableCell>Broker</TableCell>
                    <TableCell>Account</TableCell>
                    <TableCell>Exec</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Reason</TableCell>
                    <TableCell align="right">Action</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {openPositions.map((trade, index) => {
                    const id = String(trade.trade_id);
                    const draft = tpSlDrafts[id] || { tpValue: trade.tpValue ?? "", slValue: trade.slValue ?? "" };
                    const rowLoading = !!tradeActionLoading[id];
                    const floating = calcTradeFloatingPnl(trade, lastPrice);
                    return (
                      <TableRow key={id}>
                        <TableCell>{String(trade.type || "-").toUpperCase()}</TableCell>
                        <TableCell>{trade.symbol || "-"}</TableCell>
                        <TableCell>{trade.ticket || "-"}</TableCell>
                        <TableCell>{trade.lot ?? "-"}</TableCell>
                        <TableCell>{trade.entry ?? "-"}</TableCell>
                        <TableCell>{formatTradeTime(trade.entryTime)}</TableCell>
                        <TableCell>{lastPrice ?? "-"}</TableCell>
                        <TableCell sx={{ color: floating < 0 ? "error.main" : "success.main", fontWeight: 700 }}>
                          {Number(floating).toFixed(2)}
                        </TableCell>
                        <TableCell sx={{ minWidth: 110 }}>
                          <TextField
                            size="small"
                            variant="filled"
                            type="number"
                            value={draft.tpValue}
                            onChange={(e) => setTpSlDrafts((prev) => ({ ...prev, [id]: { ...draft, tpValue: e.target.value } }))}
                            inputProps={{ step: 0.1 }}
                            sx={{
                              "& .MuiFilledInput-root": { bgcolor: "action.disabledBackground" },
                              "& .MuiInputBase-input": { color: "text.secondary" },
                            }}
                          />
                        </TableCell>
                        <TableCell sx={{ minWidth: 110 }}>
                          <TextField
                            size="small"
                            variant="filled"
                            type="number"
                            value={draft.slValue}
                            onChange={(e) => setTpSlDrafts((prev) => ({ ...prev, [id]: { ...draft, slValue: e.target.value } }))}
                            inputProps={{ step: 0.1 }}
                            sx={{
                              "& .MuiFilledInput-root": { bgcolor: "action.disabledBackground" },
                              "& .MuiInputBase-input": { color: "text.secondary" },
                            }}
                          />
                        </TableCell>
                        <TableCell>{trade.broker_name || "-"}</TableCell>
                        <TableCell>{trade.account_id || "-"}</TableCell>
                        <TableCell>{trade.execution_mode || "-"}</TableCell>
                        <TableCell sx={{ minWidth: 200 }}>
                          <Box sx={{ display: "flex", gap: 0.5, flexWrap: "wrap" }}>
                            {buildTradeStatusChips(trade).map((chip, chipIdx) => (
                              <Chip
                                key={`${id}-chip-${chip.label}-${chipIdx}`}
                                size="small"
                                label={chip.label}
                                color={chip.color}
                                variant={chip.variant}
                              />
                            ))}
                          </Box>
                        </TableCell>
                        <TableCell sx={{ maxWidth: 220 }}>
                          <Typography variant="caption" color="text.secondary">
                            {trade.reason || "-"}
                          </Typography>
                        </TableCell>
                        <TableCell align="right" sx={{ whiteSpace: "nowrap" }}>
                          <Button size="small" variant="outlined" sx={{ mr: 1 }} disabled={rowLoading} onClick={() => handleSaveTradeTPSL(id)}>
                            Save TP/SL
                          </Button>
                          <Button size="small" color="error" variant="contained" disabled={rowLoading} onClick={() => handleCloseTrade(trade, index)}>
                            Close
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Paper>

        <Paper sx={{ p: { xs: 1, sm: 2 }, mb: 2, overflowX: "auto", width: "100%" }}>
          <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 1 }}>
            <Typography variant="h6">Chart</Typography>
            <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
              <Button size="small" variant={chartMode === "candlestick" ? "contained" : "outlined"} onClick={() => setChartMode("candlestick")}>
                Candlestick
              </Button>
              <Button size="small" variant={chartMode === "line" ? "contained" : "outlined"} onClick={() => setChartMode("line")}>
                Line
              </Button>
            </Box>
          </Box>

          {ohlcvError || !ohlcv || ohlcv.length === 0 ? (
            <Typography variant="body2" color="text.secondary">Chart not available.</Typography>
          ) : chartMode === "candlestick" ? (
            <CandlestickChart
              ohlcv={ohlcv}
              jumlahBar={barCount}
              spread={(() => {
                const last = ohlcv[ohlcv.length - 1];
                if (last && last.ask !== undefined && last.bid !== undefined) return Math.abs(last.ask - last.bid);
                return 2.0;
              })()}
            />
          ) : (
            <LineChart ohlcv={ohlcv} />
          )}
        </Paper>

        <Paper sx={{ p: { xs: 1, sm: 2 }, mb: 2, overflowX: "auto", width: "100%" }}>
          <Typography variant="h6">Informasi Setting Indikator</Typography>
          <Typography variant="body2" sx={{ mb: 1, color: darkMode ? "#90caf9" : "#1976d2", fontWeight: 500 }}>
            Referensi default: RSI (14), MACD (12,26,9), Bollinger Bands (20,2), SMA (20), Stochastic (14,3,3)
          </Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>TF</TableCell>
                  <TableCell align="right">RSI</TableCell>
                  <TableCell align="right">MACD</TableCell>
                  <TableCell align="right">MACD Sig</TableCell>
                  <TableCell align="right">BB Low</TableCell>
                  <TableCell align="right">BB Mid</TableCell>
                  <TableCell align="right">BB Up</TableCell>
                  <TableCell align="right">SMA</TableCell>
                  <TableCell align="right">Stoch K</TableCell>
                  <TableCell align="right">Stoch D</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {["M1", "M5", "M15", "M30"].map((timeframe) => {
                  const row = indicators?.[timeframe];
                  return (
                    <TableRow key={timeframe}>
                      <TableCell sx={{ fontWeight: 700 }}>{timeframe}</TableCell>
                      <TableCell align="right">{row?.rsi?.toFixed?.(2) ?? "-"}</TableCell>
                      <TableCell align="right">{row?.macd?.toFixed?.(2) ?? "-"}</TableCell>
                      <TableCell align="right">{row?.macd_signal?.toFixed?.(2) ?? "-"}</TableCell>
                      <TableCell align="right">{row?.bb_lower?.toFixed?.(2) ?? "-"}</TableCell>
                      <TableCell align="right">{row?.bb_mid?.toFixed?.(2) ?? "-"}</TableCell>
                      <TableCell align="right">{row?.bb_upper?.toFixed?.(2) ?? "-"}</TableCell>
                      <TableCell align="right">{row?.sma?.toFixed?.(2) ?? "-"}</TableCell>
                      <TableCell align="right">{row?.stoch_k?.toFixed?.(2) ?? "-"}</TableCell>
                      <TableCell align="right">{row?.stoch_d?.toFixed?.(2) ?? "-"}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>

        <Paper sx={{ p: { xs: 1, sm: 2 }, mb: 2, overflowX: "auto", width: "100%" }}>
          <Typography variant="h6" sx={{ mb: 1 }}>Referensi Preferensi Trade Mode</Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Profil</TableCell>
                  <TableCell>Trade Mode</TableCell>
                  <TableCell>TF Utama</TableCell>
                  <TableCell>Konfirmasi</TableCell>
                  <TableCell>Preferensi Setting</TableCell>
                  <TableCell>Catatan</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                <TableRow>
                  <TableCell>Santai</TableCell>
                  <TableCell>Normal</TableCell>
                  <TableCell>M15 - H1</TableCell>
                  <TableCell>H4</TableCell>
                  <TableCell>RSI 14, MACD 12/26/9, Stoch 14/3/3</TableCell>
                  <TableCell>Fokus tren lebih stabil, sinyal lebih sedikit.</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Santai</TableCell>
                  <TableCell>Scalp</TableCell>
                  <TableCell>M5 - M15</TableCell>
                  <TableCell>H1</TableCell>
                  <TableCell>RSI 14, BB 20/2, Stoch 5/3/3</TableCell>
                  <TableCell>Target kecil, hindari high-impact news.</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Agresif</TableCell>
                  <TableCell>Normal</TableCell>
                  <TableCell>M5 - M15</TableCell>
                  <TableCell>H1</TableCell>
                  <TableCell>RSI 7-10, MACD cepat, MA 20</TableCell>
                  <TableCell>Lebih responsif, false signal lebih tinggi.</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Agresif</TableCell>
                  <TableCell>Scalp</TableCell>
                  <TableCell>M1 - M5</TableCell>
                  <TableCell>M15</TableCell>
                  <TableCell>Stoch 3/1/1, MACD 5/13/9, MA 10/20</TableCell>
                  <TableCell>Butuh eksekusi cepat dan disiplin risk management.</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </TableContainer>
          <Alert severity="info" sx={{ mt: 1.5 }}>
            Panel ini bersifat referensi visual preferensi setup indikator. Eksekusi sinyal final tetap mengikuti logic backend.
          </Alert>
        </Paper>
      </Box>
  );
}
