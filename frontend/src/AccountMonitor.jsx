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
  const [autoTradeEnabled, setAutoTradeEnabled] = useState(false);
  const [keepTerminalAlive, setKeepTerminalAlive] = useState(true);
  const [dataFeedBrokerId, setDataFeedBrokerId] = useState("");
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
          )) : <li>No history yet.</li>}
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
            <Button variant="contained" onClick={createBroker} disabled={!brokerForm.name.trim() || addingBroker}>
              {addingBroker ? "Adding..." : "Add Broker"}
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
                  <TableCell sx={{ maxWidth: 320, wordBreak: "break-all" }}>{b.terminal_path || "-"}</TableCell>
                  <TableCell>{b.is_active ? "Active" : "Inactive"}</TableCell>
                  <TableCell align="right">
                    <Button size="small" onClick={() => setDefaultBroker(b.id)} disabled={b.is_default}>Default</Button>
                    <Button size="small" onClick={() => toggleBrokerActive(b)}>{b.is_active ? "Disable" : "Enable"}</Button>
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
