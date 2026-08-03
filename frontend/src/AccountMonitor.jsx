import React, { useEffect, useState } from "react";
import {
  Box,
  Typography,
  Paper,
  Button,
  TextField,
  Grid,
  Switch,
  FormControlLabel,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  MenuItem,
  Chip,
  Snackbar,
  Alert,
} from "@mui/material";

const API_BASE = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";
const BROKERS_CACHE_KEY = "dashboard_brokers_cache_v1";


export default function AccountMonitor() {
  const [state, setState] = useState({ balance: 0, initial_balance: 0, lot: 0.01, max_open_trades: 1, history: [] });
  const [deposit, setDeposit] = useState(0);
  const [withdraw, setWithdraw] = useState(0);
  const [adjust, setAdjust] = useState(0);
  const [adjustNote, setAdjustNote] = useState("");
  const [initBalance, setInitBalance] = useState(0);
  const [lot, setLot] = useState(0.01);
  const [maxOpen, setMaxOpen] = useState(1);
  const [enableMT5, setEnableMT5] = useState(() => {
    // Use backend value if available, fallback to localStorage
    const stored = localStorage.getItem('enableMT5');
    return stored === null ? false : stored === 'true';
  });  

  const [brokers, setBrokers] = useState([]);
  const [editingBroker, setEditingBroker] = useState(null);
  const handleEditBroker = (broker) => {
    setEditingBroker(broker);
    setBrokerForm({
      name: broker.name || "",
      platform: broker.platform || "mt5",
      execution_mode: broker.execution_mode || "mouse",
      default_symbol: broker.default_symbol || "",
      terminal_path: broker.terminal_path || "",
      window_hint: broker.window_hint || "",
    });
  };

  const [autoTradeEnabled, setAutoTradeEnabled] = useState(false);
  const [keepTerminalAlive, setKeepTerminalAlive] = useState(true);
  const [dataFeedBrokerId, setDataFeedBrokerId] = useState("");
  const [autoTradeSymbol, setAutoTradeSymbol] = useState("XAUUSD");
  const [autoTradeIntervalSec, setAutoTradeIntervalSec] = useState(2);
  const [autoAnalyticTpSl, setAutoAnalyticTpSl] = useState(false);
  const [autoTradeTpValue, setAutoTradeTpValue] = useState(0.5);
  const [autoTradeSlValue, setAutoTradeSlValue] = useState(0.5);
  const [autoTradeConfigSaving, setAutoTradeConfigSaving] = useState(false);
  const [autoTradeConstraints, setAutoTradeConstraints] = useState(null);
  const [autoTradeConstraintsLoading, setAutoTradeConstraintsLoading] = useState(false);
  const [tradeHistorySyncMode, setTradeHistorySyncMode] = useState("days");
  const [tradeHistorySyncDays, setTradeHistorySyncDays] = useState(90);
  const [tradeHistorySyncSaving, setTradeHistorySyncSaving] = useState(false);
  const [tradeHistorySyncRunning, setTradeHistorySyncRunning] = useState(false);
  const [runtimeLoaded, setRuntimeLoaded] = useState(false);
  const [addingBroker, setAddingBroker] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, severity: "info", message: "" });
  const [brokerForm, setBrokerForm] = useState({
    name: "",
    platform: "mt5",
    execution_mode: "mouse",
    terminal_path: "",
    window_hint: "FinexBisnisSolusi",
  });

  // Fetch enable_real_trade from backend on mount
  useEffect(() => {
    fetch(`${API_BASE}/account/state`)
      .then(res => res.json())
      .then(data => {
        setState(data);
        if (typeof data.enable_real_trade === 'boolean') {
          setEnableMT5(data.enable_real_trade);
        }
        setAutoTradeEnabled(!!data.auto_trade_enabled);
        setKeepTerminalAlive(data.keep_terminal_alive !== false);
        setDataFeedBrokerId(data.data_feed_broker_id ? String(data.data_feed_broker_id) : "");
        setAutoTradeSymbol(String(data.auto_trade_symbol || "XAUUSD"));
        setAutoTradeIntervalSec(Number(data.auto_trade_interval_sec || 2));
        setAutoAnalyticTpSl(!!data.auto_analytic_tpsl);
        setAutoTradeTpValue(Number(data.tp_value ?? 0.5));
        setAutoTradeSlValue(Number(data.sl_value ?? 0.5));
        setTradeHistorySyncMode(data.trade_history_sync_all ? "all" : "days");
        setTradeHistorySyncDays(Number(data.trade_history_sync_days || 90));
        setRuntimeLoaded(true);
      });
  }, []);

  useEffect(() => {
    fetch(`${API_BASE}/account/state`)
      .then(res => res.json())
      .then(data => setState(data));
  }, []);

  const loadBrokers = () => {
    fetch(`${API_BASE}/brokers?include_inactive=true`)
      .then(res => res.json())
      .then(data => {
        const items = Array.isArray(data) ? data : [];
        if (items.length > 0) {
          localStorage.setItem(BROKERS_CACHE_KEY, JSON.stringify(items));
        }
        setBrokers(prev => (items.length > 0 ? items : prev));
      })
      .catch(() => {
        try {
          const raw = localStorage.getItem(BROKERS_CACHE_KEY);
          const cached = raw ? JSON.parse(raw) : [];
          if (Array.isArray(cached) && cached.length > 0) {
            setBrokers(prev => (prev.length > 0 ? prev : cached));
          }
        } catch {
          // Ignore cache parse failures.
        }
      });
  };

  useEffect(() => {
    try {
      const raw = localStorage.getItem(BROKERS_CACHE_KEY);
      const cached = raw ? JSON.parse(raw) : [];
      if (Array.isArray(cached) && cached.length > 0) {
        setBrokers(prev => (prev.length > 0 ? prev : cached));
      }
    } catch {
      // Ignore cache parse failures.
    }
  }, []);

  useEffect(() => {
    loadBrokers();
  }, []);

  useEffect(() => {
    const timer = setInterval(() => {
      loadBrokers();
    }, 30000);
    return () => clearInterval(timer);
  }, []);

  // Persist enableMT5 to localStorage and backend whenever it changes
  useEffect(() => {
    localStorage.setItem('enableMT5', enableMT5);
    fetch(`${API_BASE}/account/set_enable_real_trade`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(enableMT5)
    });
  }, [enableMT5]);

  useEffect(() => {
    if (!runtimeLoaded) return;
    fetch(`${API_BASE}/account/set_auto_trade_enabled`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(autoTradeEnabled)
    });
  }, [autoTradeEnabled, runtimeLoaded]);

  useEffect(() => {
    if (!runtimeLoaded) return;
    fetch(`${API_BASE}/account/set_keep_terminal_alive`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(keepTerminalAlive)
    });
  }, [keepTerminalAlive, runtimeLoaded]);

  useEffect(() => {
    if (!runtimeLoaded || !dataFeedBrokerId) return;
    fetch(`${API_BASE}/account/set_data_feed_broker`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Number(dataFeedBrokerId))
    })
      .then((res) => res.json())
      .then((data) => {
        if (data && data.status === "ok" && data.auto_trade_symbol) {
          setAutoTradeSymbol(String(data.auto_trade_symbol));
        }
        return refreshAccountState();
      })
      .catch(() => {
        // Ignore transient update errors; UI will refresh on next poll/manual save.
      });
  }, [dataFeedBrokerId, runtimeLoaded]);

  const handleDeposit = () => {
    fetch(`${API_BASE}/account/deposit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(deposit)
    }).then(() => window.location.reload());
  };
  const handleWithdraw = () => {
    fetch(`${API_BASE}/account/withdraw`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(withdraw)
    }).then(() => window.location.reload());
  };
  const handleAdjust = () => {
    fetch(`${API_BASE}/account/adjustment`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount: adjust, note: adjustNote })
    }).then(() => window.location.reload());
  };
  const handleInitBalance = () => {
    fetch(`${API_BASE}/account/set_initial_balance`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(initBalance)
    }).then(() => window.location.reload());
  };
  const handleLot = () => {
    fetch(`${API_BASE}/account/set_lot`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(lot)
    }).then(() => window.location.reload());
  };
  const handleMaxOpen = () => {
    fetch(`${API_BASE}/account/set_max_open_trades`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(maxOpen)
    }).then(() => window.location.reload());
  };

  const refreshAccountState = async () => {
    const res = await fetch(`${API_BASE}/account/state`);
    const data = await res.json();
    setState(data);
    setAutoTradeSymbol(String(data.auto_trade_symbol || "XAUUSD"));
    setAutoTradeIntervalSec(Number(data.auto_trade_interval_sec || 2));
    setAutoAnalyticTpSl(!!data.auto_analytic_tpsl);
    setAutoTradeTpValue(Number(data.tp_value ?? 0.5));
    setAutoTradeSlValue(Number(data.sl_value ?? 0.5));
    setTradeHistorySyncMode(data.trade_history_sync_all ? "all" : "days");
    setTradeHistorySyncDays(Number(data.trade_history_sync_days || 90));
  };

  const normalizeLotByConstraints = (rawLot, constraintsPayload) => {
    const constraints = constraintsPayload?.constraints;
    const value = Number(rawLot || 0);
    if (!Number.isFinite(value) || value <= 0) return Number(lot || 0.01);
    if (!constraints || !constraints.can_open_order || !constraints.volume_step) {
      return Math.max(0.01, value);
    }

    const min = Number(constraints.volume_min || 0.01);
    const max = Number(constraints.volume_max || value);
    const step = Number(constraints.volume_step || 0);
    let next = Math.min(Math.max(value, min), max);
    if (step > 0) {
      const n = Math.round((next - min) / step);
      next = min + (n * step);
      next = Math.min(Math.max(next, min), max);
      const decimals = String(step).includes(".") ? String(step).split(".")[1].length : 0;
      next = Number(next.toFixed(Math.min(Math.max(decimals, 2), 8)));
    }
    return next;
  };

  const loadAutoTradeConstraints = async ({ normalizeLot = true } = {}) => {
    setAutoTradeConstraintsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/account/auto_trade_constraints`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.status === "error") {
        throw new Error(data.message || data.detail || "Gagal mengambil batasan auto-trade.");
      }
      setAutoTradeConstraints(data);
      if (data?.symbol) {
        setAutoTradeSymbol(String(data.symbol));
      }
      if (normalizeLot) {
        const normalizedLot = Number(data?.normalized?.lot);
        if (Number.isFinite(normalizedLot) && Math.abs(normalizedLot - Number(lot || 0)) > 1e-9) {
          setLot(normalizedLot);
        }
      }
    } catch (err) {
      setAutoTradeConstraints(null);
    } finally {
      setAutoTradeConstraintsLoading(false);
    }
  };

  useEffect(() => {
    if (!runtimeLoaded || !autoTradeEnabled) return;
    loadAutoTradeConstraints();
  }, [runtimeLoaded, autoTradeEnabled, dataFeedBrokerId]);

  const saveAutoTradeConfig = async () => {
    const safeInterval = Math.max(1, Math.min(60, Number(autoTradeIntervalSec || 2)));
    const safeLot = Math.max(0.01, Number(lot || 0.01));
    const safeMaxOpen = Math.max(1, Number(maxOpen || 1));
    setAutoTradeConfigSaving(true);
    try {
      const res = await fetch(`${API_BASE}/account/set_auto_trade_config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          interval_sec: safeInterval,
          auto_analytic_tpsl: autoAnalyticTpSl,
          tp_value: Number(autoTradeTpValue || 0),
          sl_value: Number(autoTradeSlValue || 0),
          lot: safeLot,
          max_open_trades: safeMaxOpen,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.status === "error") {
        throw new Error(data.message || data.detail || "Gagal menyimpan konfigurasi auto-trade.");
      }
      await refreshAccountState();
      setLot(Number(data.lot ?? safeLot));
      setMaxOpen(Number(data.max_open_trades ?? safeMaxOpen));
      if (data.constraints) {
        setAutoTradeConstraints((prev) => ({
          ...(prev || {}),
          constraints: data.constraints,
          symbol: data.constraints.symbol || autoTradeSymbol,
        }));
      }
      await loadAutoTradeConstraints();
      setSnackbar({ open: true, severity: "success", message: "Detail auto-trade berhasil disimpan." });
    } catch (err) {
      setSnackbar({ open: true, severity: "error", message: err.message || "Tidak bisa menyimpan detail auto-trade." });
    } finally {
      setAutoTradeConfigSaving(false);
    }
  };

  const saveTradeHistorySync = async () => {
    const days = Math.max(1, Number(tradeHistorySyncDays || 90));
    setTradeHistorySyncSaving(true);
    try {
      const res = await fetch(`${API_BASE}/account/set_trade_history_sync`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sync_all: tradeHistorySyncMode === "all",
          days,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.status === "error") {
        throw new Error(data.message || data.detail || "Gagal menyimpan konfigurasi sync history.");
      }
      await refreshAccountState();
      setSnackbar({ open: true, severity: "success", message: "Konfigurasi sync history tersimpan." });
    } catch (err) {
      setSnackbar({ open: true, severity: "error", message: err.message || "Tidak bisa menyimpan konfigurasi sync history." });
    } finally {
      setTradeHistorySyncSaving(false);
    }
  };

  const runTradeHistorySync = async () => {
    setTradeHistorySyncRunning(true);
    try {
      const res = await fetch(`${API_BASE}/trade/sync_history`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.status === "error") {
        throw new Error(data.message || data.detail || "Sinkronisasi history gagal.");
      }
      const label = data.trade_history_sync_all ? "semua history" : `${data.trade_history_sync_days} hari`;
      setSnackbar({ open: true, severity: "success", message: `Sinkronisasi history selesai untuk ${label}.` });
    } catch (err) {
      setSnackbar({ open: true, severity: "error", message: err.message || "Tidak bisa menjalankan sinkronisasi history." });
    } finally {
      setTradeHistorySyncRunning(false);
    }
  };

  const createBroker = async () => {
    const name = brokerForm.name.trim();
    if (!name) {
      setSnackbar({ open: true, severity: "warning", message: "Broker name wajib diisi." });
      return;
    }

    const payload = {
      ...brokerForm,
      name,
      execution_mode: brokerForm.platform === "mt4" ? "mouse" : brokerForm.execution_mode,
      terminal_path: brokerForm.terminal_path?.trim() || null,
      window_hint: brokerForm.window_hint?.trim() || null,
      default_symbol: brokerForm.default_symbol?.trim() || null,
    };

    setAddingBroker(true);
    try {
      const res = await fetch(`${API_BASE}/brokers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const msg = data?.detail || "Gagal menambah broker.";
        setSnackbar({ open: true, severity: "error", message: String(msg) });
        return;
      }

      setBrokerForm({
        name: "",
        platform: "mt5",
        execution_mode: "mouse",
        terminal_path: "",
        window_hint: "FinexBisnisSolusi",
      });
      await loadBrokers();
      setSnackbar({ open: true, severity: "success", message: "Broker berhasil ditambahkan." });
    } catch (err) {
      setSnackbar({ open: true, severity: "error", message: "Tidak bisa terhubung ke backend." });
    } finally {
      setAddingBroker(false);
    }
  };

const saveBroker = async () => {
  if (!editingBroker) return;
  const name = brokerForm.name.trim();
  if (!name) {
    setSnackbar({ open: true, severity: "warning", message: "Broker name wajib diisi." });
    return;
  }

  const payload = {
    ...brokerForm,
    name,
    execution_mode: brokerForm.platform === "mt4" ? "mouse" : brokerForm.execution_mode,
    terminal_path: brokerForm.terminal_path?.trim() || null,
    window_hint: brokerForm.window_hint?.trim() || null,
    default_symbol: brokerForm.default_symbol?.trim() || null,
  };

  try {
    const res = await fetch(`${API_BASE}/brokers/${editingBroker.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const msg = data?.detail || "Gagal update broker.";
      setSnackbar({ open: true, severity: "error", message: String(msg) });
      return;
    }

    setEditingBroker(null);
    setBrokerForm({
      name: "",
      platform: "mt5",
      execution_mode: "mouse",
      terminal_path: "",
      default_symbol: "XAUUSD",
      window_hint: "FinexBisnisSolusi",
    });
    await loadBrokers();
    setSnackbar({ open: true, severity: "success", message: "Broker berhasil diupdate." });
  } catch (err) {
    setSnackbar({ open: true, severity: "error", message: "Tidak bisa terhubung ke backend." });
  }
};

const setDefaultBroker = async (id) => {
    await fetch(`${API_BASE}/brokers/${id}/set_default`, { method: "POST" });
    loadBrokers();
  };

  const toggleBrokerActive = async (broker) => {
    await fetch(`${API_BASE}/brokers/${broker.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: !broker.is_active }),
    });
    loadBrokers();
  };

  const deleteBroker = async (id) => {
    await fetch(`${API_BASE}/brokers/${id}`, { method: "DELETE" });
    loadBrokers();
  };

  const updateBrokerMode = async (broker, mode) => {
    const safeMode = String(broker.platform || "").toLowerCase() === "mt4" ? "mouse" : mode;
    await fetch(`${API_BASE}/brokers/${broker.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ execution_mode: safeMode }),
    });
    loadBrokers();
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" sx={{ mb: 2 }}>Account Monitor</Typography>
      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle1">Balance: ${state.balance?.toFixed(2)}</Typography>
        <Typography variant="subtitle2">Initial Balance: ${state.initial_balance?.toFixed(2)}</Typography>
        <Typography variant="subtitle2">Lot: {state.lot}</Typography>
        <Typography variant="subtitle2">Max Open Trades: {state.max_open_trades}</Typography>
        <FormControlLabel control={<Switch checked={enableMT5} onChange={e => setEnableMT5(e.target.checked)} />} label="Enable Trading on MT5" />
        <FormControlLabel control={<Switch checked={autoTradeEnabled} onChange={e => setAutoTradeEnabled(e.target.checked)} />} label="Auto Trade Backend" />
        <FormControlLabel control={<Switch checked={keepTerminalAlive} onChange={e => setKeepTerminalAlive(e.target.checked)} />} label="Keep Terminal Alive" />
        <TextField
          select
          label="Data Feed Broker"
          value={dataFeedBrokerId}
          onChange={(e) => setDataFeedBrokerId(e.target.value)}
          size="small"
          sx={{ mt: 1, minWidth: 280 }}
          helperText="Broker ini dipakai untuk feed chart/signal backend."
        >
          {brokers.map((b) => (
            <MenuItem key={b.id} value={String(b.id)}>
              {b.name} ({String(b.platform || "").toUpperCase()})
            </MenuItem>
          ))}
        </TextField>

        <Box sx={{ mt: 2 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>Auto Trade Detail</Typography>
          <Grid container spacing={1} alignItems="center" sx={{ mb: 2 }}>
            <Grid item xs={12} md={2}>
              <TextField
                fullWidth
                size="small"
                label="Symbol"
                value={autoTradeSymbol}
                InputProps={{ readOnly: true }}
                placeholder="XAUUSD"
                helperText="Mengikuti default symbol broker aktif"
              />
            </Grid>
            <Grid item xs={12} md={2}>
              <TextField
                fullWidth
                size="small"
                label="Cycle (sec)"
                type="number"
                value={autoTradeIntervalSec}
                onChange={(e) => setAutoTradeIntervalSec(Number(e.target.value))}
                inputProps={{ min: 1, max: 60, step: 1 }}
                helperText="1 - 60 detik"
              />
            </Grid>
            <Grid item xs={12} md={2}>
              <TextField
                fullWidth
                size="small"
                label="Lot"
                type="number"
                value={lot}
                onChange={(e) => setLot(Number(e.target.value))}
                onBlur={() => {
                  const corrected = normalizeLotByConstraints(lot, autoTradeConstraints);
                  if (Math.abs(corrected - Number(lot || 0)) > 1e-9) {
                    setLot(corrected);
                    setSnackbar({
                      open: true,
                      severity: "info",
                      message: `Lot disesuaikan ke nilai valid broker: ${corrected}`,
                    });
                  }
                }}
                inputProps={{ min: 0.01, step: 0.01 }}
                helperText={autoTradeConstraints?.constraints?.can_open_order
                  ? `Min ${autoTradeConstraints.constraints.volume_min} | Step ${autoTradeConstraints.constraints.volume_step} | Max ${autoTradeConstraints.constraints.volume_max}`
                  : "Lot akan divalidasi saat constraints broker tersedia."}
              />
            </Grid>
            <Grid item xs={12} md={2}>
              <TextField
                fullWidth
                size="small"
                label="Max Open"
                type="number"
                value={maxOpen}
                onChange={(e) => setMaxOpen(Number(e.target.value))}
                inputProps={{ min: 1, step: 1 }}
              />
            </Grid>
            <Grid item xs={12} md={2}>
              <TextField
                fullWidth
                size="small"
                label="TP Value"
                type="number"
                value={autoTradeTpValue}
                onChange={(e) => setAutoTradeTpValue(Number(e.target.value))}
                disabled={autoAnalyticTpSl}
                inputProps={{ min: 0, step: 0.1 }}
              />
            </Grid>
            <Grid item xs={12} md={2}>
              <TextField
                fullWidth
                size="small"
                label="SL Value"
                type="number"
                value={autoTradeSlValue}
                onChange={(e) => setAutoTradeSlValue(Number(e.target.value))}
                disabled={autoAnalyticTpSl}
                inputProps={{ min: 0, step: 0.1 }}
              />
            </Grid>
            <Grid item xs={12} md={4}>
              <FormControlLabel
                control={<Switch checked={autoAnalyticTpSl} onChange={(e) => setAutoAnalyticTpSl(e.target.checked)} />}
                label="Auto Analytic TP/SL"
              />
            </Grid>
            <Grid item xs={12} md={8}>
              <Button variant="contained" onClick={saveAutoTradeConfig} disabled={autoTradeConfigSaving}>
                {autoTradeConfigSaving ? "Saving..." : "Save Auto Trade Detail"}
              </Button>
              <Button
                variant="outlined"
                sx={{ ml: 1 }}
                onClick={() => loadAutoTradeConstraints()}
                disabled={autoTradeConstraintsLoading}
              >
                {autoTradeConstraintsLoading ? "Checking..." : "Refresh Constraints"}
              </Button>
            </Grid>
            <Grid item xs={12}>
              <Alert severity="info" sx={{ mt: 0.5 }}>
                Auto-trade hanya berlaku untuk default symbol broker yang aktif dipilih. Jika satu broker punya banyak symbol aktif, backend tetap eksekusi auto-trade hanya pada default symbol broker tersebut.
              </Alert>
            </Grid>
            <Grid item xs={12}>
              <Paper variant="outlined" sx={{ p: 1.5, mt: 0.5, bgcolor: "background.default" }}>
                <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5 }}>
                  Open Trade Constraints {autoTradeConstraints?.symbol ? `(${autoTradeConstraints.symbol})` : ""}
                </Typography>
                {!autoTradeConstraints ? (
                  <Typography variant="caption" color="text.secondary">
                    Constraint belum tersedia. Aktifkan Auto Trade dan klik Refresh Constraints.
                  </Typography>
                ) : (
                  <Grid container spacing={1}>
                    <Grid item xs={12} md={3}><Typography variant="caption">Broker: {autoTradeConstraints?.broker?.name || autoTradeConstraints?.constraints?.broker_name || "-"}</Typography></Grid>
                    <Grid item xs={12} md={3}><Typography variant="caption">Account: {autoTradeConstraints?.constraints?.account_id || "-"}</Typography></Grid>
                    <Grid item xs={12} md={3}><Typography variant="caption">Can Open: {autoTradeConstraints?.constraints?.can_open_order ? "Yes" : "No"}</Typography></Grid>
                    <Grid item xs={12} md={3}><Typography variant="caption">Reason: {autoTradeConstraints?.constraints?.reason || "-"}</Typography></Grid>
                    <Grid item xs={12} md={3}><Typography variant="caption">Lot Min: {autoTradeConstraints?.constraints?.volume_min ?? "-"}</Typography></Grid>
                    <Grid item xs={12} md={3}><Typography variant="caption">Lot Step: {autoTradeConstraints?.constraints?.volume_step ?? "-"}</Typography></Grid>
                    <Grid item xs={12} md={3}><Typography variant="caption">Lot Max: {autoTradeConstraints?.constraints?.volume_max ?? "-"}</Typography></Grid>
                    <Grid item xs={12} md={3}><Typography variant="caption">Volume Limit: {autoTradeConstraints?.constraints?.volume_limit ?? "-"}</Typography></Grid>
                    <Grid item xs={12} md={3}><Typography variant="caption">Digits: {autoTradeConstraints?.constraints?.digits ?? "-"}</Typography></Grid>
                    <Grid item xs={12} md={3}><Typography variant="caption">Point: {autoTradeConstraints?.constraints?.point ?? "-"}</Typography></Grid>
                    <Grid item xs={12} md={3}><Typography variant="caption">Stops Level: {autoTradeConstraints?.constraints?.trade_stops_level ?? "-"}</Typography></Grid>
                    <Grid item xs={12} md={3}><Typography variant="caption">Freeze Level: {autoTradeConstraints?.constraints?.trade_freeze_level ?? "-"}</Typography></Grid>
                  </Grid>
                )}
              </Paper>
            </Grid>
          </Grid>

          <Typography variant="subtitle2" sx={{ mb: 1 }}>Trade History Sync</Typography>
          <Grid container spacing={1} alignItems="center">
            <Grid item xs={12} md={3}>
              <TextField
                select
                fullWidth
                label="Sync Range"
                value={tradeHistorySyncMode}
                onChange={(e) => setTradeHistorySyncMode(e.target.value)}
                size="small"
              >
                <MenuItem value="days">Berdasarkan jumlah hari</MenuItem>
                <MenuItem value="all">Semua history terminal</MenuItem>
              </TextField>
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                label="Jumlah Hari"
                type="number"
                value={tradeHistorySyncDays}
                onChange={(e) => setTradeHistorySyncDays(Number(e.target.value))}
                size="small"
                disabled={tradeHistorySyncMode === "all"}
                helperText={tradeHistorySyncMode === "all" ? "Diabaikan saat mode semua history aktif." : "Contoh: 30, 90, 365, 1000."}
                inputProps={{ min: 1, step: 1 }}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
                <Button variant="contained" onClick={saveTradeHistorySync} disabled={tradeHistorySyncSaving}>
                  {tradeHistorySyncSaving ? "Saving..." : "Save Sync Setting"}
                </Button>
                <Button variant="outlined" onClick={runTradeHistorySync} disabled={tradeHistorySyncRunning}>
                  {tradeHistorySyncRunning ? "Syncing..." : "Sync Now"}
                </Button>
              </Box>
            </Grid>
          </Grid>
        </Box>
      </Paper>
      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2, mb: 2 }}>
            <Typography variant="subtitle2">Deposit</Typography>
            <TextField label="Amount" type="number" value={deposit} onChange={e => setDeposit(Number(e.target.value))} size="small" sx={{ mr: 1 }} />
            <Button variant="contained" onClick={handleDeposit}>Deposit</Button>
          </Paper>
          <Paper sx={{ p: 2, mb: 2 }}>
            <Typography variant="subtitle2">Withdraw</Typography>
            <TextField label="Amount" type="number" value={withdraw} onChange={e => setWithdraw(Number(e.target.value))} size="small" sx={{ mr: 1 }} />
            <Button variant="contained" color="warning" onClick={handleWithdraw}>Withdraw</Button>
          </Paper>
          <Paper sx={{ p: 2, mb: 2 }}>
            <Typography variant="subtitle2">Adjustment</Typography>
            <TextField label="Amount" type="number" value={adjust} onChange={e => setAdjust(Number(e.target.value))} size="small" sx={{ mr: 1 }} />
            <TextField label="Note" value={adjustNote} onChange={e => setAdjustNote(e.target.value)} size="small" sx={{ mr: 1 }} />
            <Button variant="contained" color="secondary" onClick={handleAdjust}>Adjust</Button>
          </Paper>
        </Grid>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2, mb: 2 }}>
            <Typography variant="subtitle2">Set Initial Balance</Typography>
            <TextField label="Initial Balance" type="number" value={initBalance} onChange={e => setInitBalance(Number(e.target.value))} size="small" sx={{ mr: 1 }} />
            <Button variant="contained" onClick={handleInitBalance}>Set</Button>
          </Paper>
          <Paper sx={{ p: 2, mb: 2 }}>
            <Typography variant="subtitle2">Set Lot</Typography>
            <TextField label="Lot" type="number" value={lot} onChange={e => setLot(Number(e.target.value))} size="small" sx={{ mr: 1 }} />
            <Button variant="contained" onClick={handleLot}>Set</Button>
          </Paper>
          <Paper sx={{ p: 2, mb: 2 }}>
            <Typography variant="subtitle2">Set Max Open Trades</Typography>
            <TextField label="Max Open Trades" type="number" value={maxOpen} onChange={e => setMaxOpen(Number(e.target.value))} size="small" sx={{ mr: 1 }} />
            <Button variant="contained" onClick={handleMaxOpen}>Set</Button>
          </Paper>
        </Grid>
      </Grid>
      <Paper sx={{ p: 2, mt: 2 }}>
        <Typography variant="subtitle1">History</Typography>
        <ul>
          {state.history && state.history.length > 0 ? state.history.map((h, i) => (
            <li key={i}>{h.type} {h.amount} {h.note ? `(${h.note})` : ""}</li>
          )) : <li>No history yet (deposit, withdrawal, adjustment).</li>}
        </ul>
      </Paper>

      <Paper sx={{ p: 2, mt: 2 }}>
        <Typography variant="h6" sx={{ mb: 1 }}>Broker Settings</Typography>
        <Typography variant="body2" sx={{ mb: 2 }}>
          Setiap broker bisa punya path terminal berbeda dan mode eksekusi berbeda: <b>mouse</b> atau <b>direct</b>.
        </Typography>

        <Grid container spacing={1} sx={{ mb: 2 }}>
          <Grid item xs={12} md={3}>
            <TextField
              fullWidth
              label="Broker Name"
              value={brokerForm.name}
              onChange={(e) => setBrokerForm((s) => ({ ...s, name: e.target.value }))}
              size="small"
            />
          </Grid>
          <Grid item xs={12} md={2}>
            <TextField
              fullWidth
              select
              label="Platform"
              value={brokerForm.platform}
              onChange={(e) => {
                const platform = e.target.value;
                setBrokerForm((s) => ({
                  ...s,
                  platform,
                  execution_mode: platform === "mt4" ? "mouse" : s.execution_mode,
                }));
              }}
              size="small"
            >
              <MenuItem value="mt5">MT5</MenuItem>
              <MenuItem value="mt4">MT4</MenuItem>
            </TextField>
          </Grid>
          <Grid item xs={12} md={2}>
            <TextField
              fullWidth
              select
              label="Execution"
              value={brokerForm.execution_mode}
              onChange={(e) => setBrokerForm((s) => ({ ...s, execution_mode: e.target.value }))}
              size="small"
            >
              <MenuItem value="mouse">EA mouse python</MenuItem>
              {brokerForm.platform !== "mt4" ? <MenuItem value="direct">EA direct interface</MenuItem> : null}
            </TextField>
          </Grid>
          <Grid item xs={12} md={2}>
            <TextField
              fullWidth
              label="Default Symbol"
              value={brokerForm.default_symbol}
              onChange={(e) => setBrokerForm((s) => ({ ...s, default_symbol: e.target.value }))}
              size="small"
              placeholder="XAUUSD"
            />
          </Grid>
          <Grid item xs={12} md={3}>
            <TextField
              fullWidth
              label="Terminal Path"
              value={brokerForm.terminal_path}
              onChange={(e) => setBrokerForm((s) => ({ ...s, terminal_path: e.target.value }))}
              size="small"
              placeholder="C:\\Broker\\terminal64.exe"
            />
          </Grid>
          <Grid item xs={12} md={2}>
            <TextField
              fullWidth
              label="Window Hint"
              value={brokerForm.window_hint}
              onChange={(e) => setBrokerForm((s) => ({ ...s, window_hint: e.target.value }))}
              size="small"
            />
          </Grid>
          <Grid item xs={12}>
            <Button 
              variant="contained" 
              onClick={editingBroker ? saveBroker : createBroker}
                 disabled={!brokerForm.name.trim() || addingBroker}>
              {editingBroker ? "Save Broker" : addingBroker ? "Adding..." : "Add Broker"}
            </Button>
          </Grid>
        </Grid>

        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>Platform</TableCell>
                <TableCell>Execution</TableCell>
                <TableCell>Symbol</TableCell>
                <TableCell>Terminal Path</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {brokers.map((b) => (
                <TableRow key={b.id}>
                  <TableCell>
                    {b.name} {b.is_default ? <Chip size="small" color="primary" label="Default" sx={{ ml: 1 }} /> : null}
                  </TableCell>
                  <TableCell>{String(b.platform || "").toUpperCase()}</TableCell>
                  <TableCell>
                    <TextField
                      select
                      size="small"
                      value={b.execution_mode || "mouse"}
                      onChange={(e) => updateBrokerMode(b, e.target.value)}
                    >
                      <MenuItem value="mouse">mouse</MenuItem>
                      {String(b.platform || "").toLowerCase() !== "mt4" ? <MenuItem value="direct">direct</MenuItem> : null}
                    </TextField>
                  </TableCell>
                  <TableCell>{b.default_symbol || "-"}</TableCell>
                  <TableCell sx={{ maxWidth: 320, wordBreak: "break-all" }}>{b.terminal_path || "-"}</TableCell>
                  <TableCell>{b.is_active ? "Active" : "Inactive"}</TableCell>
                  <TableCell align="right">
                    <Button size="small" onClick={() => setDefaultBroker(b.id)} disabled={b.is_default}>Default</Button>
                    <Button size="small" onClick={() => toggleBrokerActive(b)}>{b.is_active ? "Disable" : "Enable"}</Button>
                    <Button size="small" onClick={() => handleEditBroker(b)}>Edit</Button>
                    <Button size="small" color="error" onClick={() => deleteBroker(b.id)}>Delete</Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={3000}
        onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
        anchorOrigin={{ vertical: "top", horizontal: "center" }}
      >
        <Alert
          onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
          severity={snackbar.severity}
          sx={{ width: "100%" }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
