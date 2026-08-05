import React, { useEffect, useState } from "react";
import {
  Box,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Alert,
  CircularProgress,
  Button,
  Snackbar,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  TextField,
  MenuItem,
  Grid,
  Chip,
  TableSortLabel,
} from "@mui/material";

const API_BASE = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

function compareValues(a, b, direction = "asc") {
  if (a === b) return 0;
  const order = direction === "asc" ? 1 : -1;

  if (a === null || a === undefined) return 1;
  if (b === null || b === undefined) return -1;

  if (typeof a === "number" && typeof b === "number") {
    return a > b ? order : -order;
  }

  const av = String(a).toLowerCase();
  const bv = String(b).toLowerCase();
  if (av === bv) return 0;
  return av > bv ? order : -order;
}

function getTradeSortValue(row, key) {
  if (key === "entryTime" || key === "exitTime") return Number(row[key] || 0);
  if (key === "profit" || key === "entry" || key === "exit") return Number(row[key] || 0);
  return row[key] ?? "";
}

function getErrorSortValue(row, key) {
  if (key === "timestamp") return Number(row.timestamp || 0);
  return row[key] ?? "";
}

function parseHistoryStatusChips(reason, executionMode) {
  const text = String(reason || "");
  const chips = [];

  const confMatch = text.match(/auto_open:([0-9]+(?:\.[0-9]+)?)/i);
  if (confMatch) {
    const conf = Number(confMatch[1]);
    if (Number.isFinite(conf)) {
      chips.push({ label: `Conf ${(conf * 100).toFixed(0)}%`, color: conf >= 0.65 ? "success" : "warning" });
    }
  }

  if (text.includes("partial_take_profit_stage1")) chips.push({ label: "PTP S1", color: "primary" });
  if (text.includes("partial_take_profit_stage2")) chips.push({ label: "PTP S2", color: "primary" });
  if (text.includes("break_even_lock")) chips.push({ label: "BE Lock", color: "info" });
  if (text.includes("trail_update")) chips.push({ label: "Trailing", color: "secondary" });

  const exec = String(executionMode || "").toLowerCase();
  if (exec === "mouse") chips.push({ label: "Mouse", color: "warning" });
  if (exec === "direct") chips.push({ label: "Direct", color: "success" });

  return chips;
}

export default function TradeHistory() {
  const [history, setHistory] = useState([]);
  const [mt5Status, setMt5Status] = useState(null);
  const [errorLog, setErrorLog] = useState([]);
  const [loading, setLoading] = useState(true);
  const [forceCloseLoading, setForceCloseLoading] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'info' });
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [tradeFilters, setTradeFilters] = useState({
    search: "",
    type: "all",
    broker: "all",
    executionMode: "all",
    accountId: "",
  });
  const [errorFilters, setErrorFilters] = useState({
    search: "",
    broker: "all",
    accountId: "",
  });
  const [tradeSort, setTradeSort] = useState({ key: "entryTime", direction: "desc" });
  const [errorSort, setErrorSort] = useState({ key: "timestamp", direction: "desc" });

  const loadTradeHistory = () =>
    fetch(`${API_BASE}/trade/history`)
      .then((res) => res.json())
      .then((data) => setHistory(Array.isArray(data) ? data : []));

  const loadErrorLog = () =>
    fetch(`${API_BASE}/mt5/error_log`)
      .then((res) => res.json())
      .then((data) => setErrorLog(Array.isArray(data) ? data : []));

  useEffect(() => {
    loadTradeHistory();

    fetch(`${API_BASE}/mt5/status`)
      .then(res => res.json())
      .then(data => setMt5Status(data.connected))
      .catch(() => setMt5Status(false));

    loadErrorLog()
      .finally(() => setLoading(false));
  }, []);

  const tradeBrokerOptions = Array.from(new Set(history.map((row) => row.broker_name || "-").filter(Boolean))).sort();
  const errorBrokerOptions = Array.from(new Set(errorLog.map((row) => row.broker_name || "-").filter(Boolean))).sort();

  const filteredTradeHistory = history.filter((row) => {
    const search = tradeFilters.search.trim().toLowerCase();
    const haystack = [
      row.type,
      row.symbol,
      row.reason,
      row.broker_name,
      row.execution_mode,
      row.account_id,
      row.ticket,
    ]
      .filter((value) => value !== null && value !== undefined)
      .join(" ")
      .toLowerCase();

    const matchesSearch = !search || haystack.includes(search);
    const matchesType = tradeFilters.type === "all" || String(row.type || "").toLowerCase() === tradeFilters.type;
    const matchesBroker = tradeFilters.broker === "all" || (row.broker_name || "-") === tradeFilters.broker;
    const matchesExecutionMode = tradeFilters.executionMode === "all" || String(row.execution_mode || "").toLowerCase() === tradeFilters.executionMode;
    const matchesAccount = !tradeFilters.accountId || String(row.account_id || "").includes(tradeFilters.accountId.trim());

    return matchesSearch && matchesType && matchesBroker && matchesExecutionMode && matchesAccount;
  });

  const filteredErrorLog = errorLog.filter((row) => {
    const search = errorFilters.search.trim().toLowerCase();
    const haystack = [row.message, row.broker_name, row.account_id]
      .filter((value) => value !== null && value !== undefined)
      .join(" ")
      .toLowerCase();

    const matchesSearch = !search || haystack.includes(search);
    const matchesBroker = errorFilters.broker === "all" || (row.broker_name || "-") === errorFilters.broker;
    const matchesAccount = !errorFilters.accountId || String(row.account_id || "").includes(errorFilters.accountId.trim());
    return matchesSearch && matchesBroker && matchesAccount;
  });

  const sortedTradeHistory = [...filteredTradeHistory].sort((a, b) => {
    const av = getTradeSortValue(a, tradeSort.key);
    const bv = getTradeSortValue(b, tradeSort.key);
    return compareValues(av, bv, tradeSort.direction);
  });

  const sortedErrorLog = [...filteredErrorLog].sort((a, b) => {
    const av = getErrorSortValue(a, errorSort.key);
    const bv = getErrorSortValue(b, errorSort.key);
    return compareValues(av, bv, errorSort.direction);
  });

  const toggleTradeSort = (key) => {
    setTradeSort((prev) => ({
      key,
      direction: prev.key === key && prev.direction === "asc" ? "desc" : "asc",
    }));
  };

  const toggleErrorSort = (key) => {
    setErrorSort((prev) => ({
      key,
      direction: prev.key === key && prev.direction === "asc" ? "desc" : "asc",
    }));
  };

  const handleForceClose = () => {
    setForceCloseLoading(true);
    fetch(`${API_BASE}/trade/force_close`, { method: "POST" })
      .then(res => res.json())
      .then(data => {
        setSnackbar({ open: true, message: `Closed: ${data.closed.length}, Errors: ${data.errors.length}`, severity: 'success' });
        return Promise.all([loadTradeHistory(), loadErrorLog()]);
      })
      .catch(() => {
        setSnackbar({ open: true, message: 'Failed to force close trades.', severity: 'error' });
      })
      .finally(() => setForceCloseLoading(false));
  };


  return (
    <Box sx={{ p: 2, maxWidth: 1000, mx: 'auto' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h5">Trade History</Typography>
        <Button
          variant="contained"
          color="error"
          onClick={() => setConfirmDialogOpen(true)}
          disabled={forceCloseLoading}
        >
          {forceCloseLoading ? 'Processing...' : 'Force Close All Trades'}
        </Button>
      </Box>
      {/* Confirm Dialog */}
      <Dialog open={confirmDialogOpen} onClose={() => setConfirmDialogOpen(false)}>
        <DialogTitle>Force Close All Trades?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to force close all open trades? This action is irreversible and should only be used if trades are stuck or backend error occurs.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDialogOpen(false)} color="primary">Cancel</Button>
          <Button onClick={() => { setConfirmDialogOpen(false); handleForceClose(); }} color="error" autoFocus disabled={forceCloseLoading}>
            Yes, Force Close
          </Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar for feedback */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={3000}
        onClose={() => setSnackbar(s => ({ ...s, open: false }))}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        message={snackbar.message}
      />

      {/* Panel Status Koneksi MT5 */}
      <Paper sx={{ mb: 2, p: 2 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 'bold', mb: 1 }}>MT5 Connection Status</Typography>
        {mt5Status === null ? (
          <CircularProgress size={20} />
        ) : mt5Status ? (
          <Alert severity="success">Connected to MT5 terminal</Alert>
        ) : (
          <Alert severity="error">Not connected to MT5 terminal</Alert>
        )}
      </Paper>

      {/* Panel Error Log MT5 */}
      <Paper sx={{ mb: 2, p: 2 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 'bold', mb: 1 }}>
          MT5 Error Log
          {(!loading && filteredErrorLog.length > 0) && (
            <span style={{ color: '#d32f2f', fontWeight: 400, marginLeft: 12, fontSize: 14 }}>
              {filteredErrorLog[0].message}
            </span>
          )}
        </Typography>
        <Grid container spacing={1} sx={{ mb: 2 }}>
          <Grid item xs={12} md={5}>
            <TextField
              fullWidth
              size="small"
              label="Cari error"
              value={errorFilters.search}
              onChange={(e) => setErrorFilters((prev) => ({ ...prev, search: e.target.value }))}
              placeholder="Pesan error, broker, account"
            />
          </Grid>
          <Grid item xs={12} md={3}>
            <TextField
              select
              fullWidth
              size="small"
              label="Broker"
              value={errorFilters.broker}
              onChange={(e) => setErrorFilters((prev) => ({ ...prev, broker: e.target.value }))}
            >
              <MenuItem value="all">Semua broker</MenuItem>
              {errorBrokerOptions.map((broker) => (
                <MenuItem key={broker} value={broker}>{broker}</MenuItem>
              ))}
            </TextField>
          </Grid>
          <Grid item xs={12} md={2}>
            <TextField
              fullWidth
              size="small"
              label="Account ID"
              value={errorFilters.accountId}
              onChange={(e) => setErrorFilters((prev) => ({ ...prev, accountId: e.target.value }))}
            />
          </Grid>
          <Grid item xs={12} md={2}>
            <Button
              fullWidth
              variant="outlined"
              onClick={() => setErrorFilters({ search: "", broker: "all", accountId: "" })}
            >
              Reset Filter
            </Button>
          </Grid>
        </Grid>
        {loading ? <CircularProgress size={20} /> : (
          filteredErrorLog.length === 0 ? (
            <Typography variant="body2" color="text.secondary">No MT5 errors recorded.</Typography>
          ) : (
            <TableContainer sx={{ maxHeight: 320, overflow: 'auto' }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell width={160}>
                      <TableSortLabel
                        active={errorSort.key === "timestamp"}
                        direction={errorSort.key === "timestamp" ? errorSort.direction : "asc"}
                        onClick={() => toggleErrorSort("timestamp")}
                      >
                        Time
                      </TableSortLabel>
                    </TableCell>
                    <TableCell width={180}>
                      <TableSortLabel
                        active={errorSort.key === "broker_name"}
                        direction={errorSort.key === "broker_name" ? errorSort.direction : "asc"}
                        onClick={() => toggleErrorSort("broker_name")}
                      >
                        Broker
                      </TableSortLabel>
                    </TableCell>
                    <TableCell width={140}>
                      <TableSortLabel
                        active={errorSort.key === "account_id"}
                        direction={errorSort.key === "account_id" ? errorSort.direction : "asc"}
                        onClick={() => toggleErrorSort("account_id")}
                      >
                        Account
                      </TableSortLabel>
                    </TableCell>
                    <TableCell>
                      <TableSortLabel
                        active={errorSort.key === "message"}
                        direction={errorSort.key === "message" ? errorSort.direction : "asc"}
                        onClick={() => toggleErrorSort("message")}
                      >
                        Error Message
                      </TableSortLabel>
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {sortedErrorLog.map((row, idx) => (
                    <TableRow key={idx}>
                      <TableCell>{new Date(row.timestamp * 1000).toLocaleString()}</TableCell>
                      <TableCell>{row.broker_name || "-"}</TableCell>
                      <TableCell>{row.account_id || "-"}</TableCell>
                      <TableCell>{row.message}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )
        )}
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 'bold', mb: 1 }}>Trade History Records</Typography>
        <Grid container spacing={1} sx={{ mb: 2 }}>
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              size="small"
              label="Cari trade"
              value={tradeFilters.search}
              onChange={(e) => setTradeFilters((prev) => ({ ...prev, search: e.target.value }))}
              placeholder="Symbol, reason, broker, ticket"
            />
          </Grid>
          <Grid item xs={12} md={2}>
            <TextField
              select
              fullWidth
              size="small"
              label="Type"
              value={tradeFilters.type}
              onChange={(e) => setTradeFilters((prev) => ({ ...prev, type: e.target.value }))}
            >
              <MenuItem value="all">Semua type</MenuItem>
              <MenuItem value="buy">BUY</MenuItem>
              <MenuItem value="sell">SELL</MenuItem>
            </TextField>
          </Grid>
          <Grid item xs={12} md={2}>
            <TextField
              select
              fullWidth
              size="small"
              label="Broker"
              value={tradeFilters.broker}
              onChange={(e) => setTradeFilters((prev) => ({ ...prev, broker: e.target.value }))}
            >
              <MenuItem value="all">Semua broker</MenuItem>
              {tradeBrokerOptions.map((broker) => (
                <MenuItem key={broker} value={broker}>{broker}</MenuItem>
              ))}
            </TextField>
          </Grid>
          <Grid item xs={12} md={2}>
            <TextField
              select
              fullWidth
              size="small"
              label="Execution"
              value={tradeFilters.executionMode}
              onChange={(e) => setTradeFilters((prev) => ({ ...prev, executionMode: e.target.value }))}
            >
              <MenuItem value="all">Semua exec</MenuItem>
              <MenuItem value="direct">direct</MenuItem>
              <MenuItem value="mouse">mouse</MenuItem>
              <MenuItem value="simulation">simulation</MenuItem>
            </TextField>
          </Grid>
          <Grid item xs={12} md={1}>
            <TextField
              fullWidth
              size="small"
              label="Acct"
              value={tradeFilters.accountId}
              onChange={(e) => setTradeFilters((prev) => ({ ...prev, accountId: e.target.value }))}
            />
          </Grid>
          <Grid item xs={12} md={1}>
            <Button
              fullWidth
              variant="outlined"
              onClick={() => setTradeFilters({ search: "", type: "all", broker: "all", executionMode: "all", accountId: "" })}
            >
              Reset
            </Button>
          </Grid>
        </Grid>
        <TableContainer sx={{ maxHeight: 420, overflow: 'auto' }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell>No</TableCell>
                <TableCell>
                  <TableSortLabel
                    active={tradeSort.key === "type"}
                    direction={tradeSort.key === "type" ? tradeSort.direction : "asc"}
                    onClick={() => toggleTradeSort("type")}
                  >
                    Type
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={tradeSort.key === "entry"}
                    direction={tradeSort.key === "entry" ? tradeSort.direction : "asc"}
                    onClick={() => toggleTradeSort("entry")}
                  >
                    Entry
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={tradeSort.key === "exit"}
                    direction={tradeSort.key === "exit" ? tradeSort.direction : "asc"}
                    onClick={() => toggleTradeSort("exit")}
                  >
                    Exit
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={tradeSort.key === "profit"}
                    direction={tradeSort.key === "profit" ? tradeSort.direction : "asc"}
                    onClick={() => toggleTradeSort("profit")}
                  >
                    Profit
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={tradeSort.key === "entryTime"}
                    direction={tradeSort.key === "entryTime" ? tradeSort.direction : "asc"}
                    onClick={() => toggleTradeSort("entryTime")}
                  >
                    Entry Time
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={tradeSort.key === "exitTime"}
                    direction={tradeSort.key === "exitTime" ? tradeSort.direction : "asc"}
                    onClick={() => toggleTradeSort("exitTime")}
                  >
                    Exit Time
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={tradeSort.key === "reason"}
                    direction={tradeSort.key === "reason" ? tradeSort.direction : "asc"}
                    onClick={() => toggleTradeSort("reason")}
                  >
                    Reason
                  </TableSortLabel>
                </TableCell>
                <TableCell>Status</TableCell>
                <TableCell>
                  <TableSortLabel
                    active={tradeSort.key === "broker_name"}
                    direction={tradeSort.key === "broker_name" ? tradeSort.direction : "asc"}
                    onClick={() => toggleTradeSort("broker_name")}
                  >
                    Broker
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={tradeSort.key === "account_id"}
                    direction={tradeSort.key === "account_id" ? tradeSort.direction : "asc"}
                    onClick={() => toggleTradeSort("account_id")}
                  >
                    Account
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={tradeSort.key === "execution_mode"}
                    direction={tradeSort.key === "execution_mode" ? tradeSort.direction : "asc"}
                    onClick={() => toggleTradeSort("execution_mode")}
                  >
                    Exec
                  </TableSortLabel>
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {sortedTradeHistory.map((row, idx) => {
                const statusChips = parseHistoryStatusChips(row.reason, row.execution_mode);
                return (
                  <TableRow key={idx}>
                    <TableCell>{idx + 1}</TableCell>
                    <TableCell>{row.type}</TableCell>
                    <TableCell>{row.entry}</TableCell>
                    <TableCell>{row.exit}</TableCell>
                    <TableCell style={{color: row.profit < 0 ? 'red' : 'green'}}>{row.profit?.toFixed(2)}</TableCell>
                    <TableCell>{row.entryTime ? new Date(row.entryTime * 1000).toLocaleString() : '-'}</TableCell>
                    <TableCell>{row.exitTime ? new Date(row.exitTime * 1000).toLocaleString() : '-'}</TableCell>
                    <TableCell>{row.reason || '-'}</TableCell>
                    <TableCell>
                      <Box sx={{ display: "flex", gap: 0.5, flexWrap: "wrap", minWidth: 140 }}>
                        {statusChips.map((chip, chipIdx) => (
                          <Chip key={`${idx}-${chip.label}-${chipIdx}`} size="small" label={chip.label} color={chip.color} variant="outlined" />
                        ))}
                      </Box>
                    </TableCell>
                    <TableCell>{row.broker_name || '-'}</TableCell>
                    <TableCell>{row.account_id || '-'}</TableCell>
                    <TableCell>{row.execution_mode || '-'}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
        {!loading && filteredTradeHistory.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            Tidak ada trade yang cocok dengan filter.
          </Typography>
        ) : null}
      </Paper>
    </Box>
  );
}
