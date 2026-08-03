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
} from "@mui/material";

const API_BASE = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

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
                    <TableCell width={160}>Time</TableCell>
                    <TableCell width={180}>Broker</TableCell>
                    <TableCell width={140}>Account</TableCell>
                    <TableCell>Error Message</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredErrorLog.map((row, idx) => (
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
                <TableCell>Type</TableCell>
                <TableCell>Entry</TableCell>
                <TableCell>Exit</TableCell>
                <TableCell>Profit</TableCell>
                <TableCell>Entry Time</TableCell>
                <TableCell>Exit Time</TableCell>
                <TableCell>Reason</TableCell>
                <TableCell>Broker</TableCell>
                <TableCell>Account</TableCell>
                <TableCell>Exec</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredTradeHistory.map((row, idx) => (
                <TableRow key={idx}>
                  <TableCell>{idx + 1}</TableCell>
                  <TableCell>{row.type}</TableCell>
                  <TableCell>{row.entry}</TableCell>
                  <TableCell>{row.exit}</TableCell>
                  <TableCell style={{color: row.profit < 0 ? 'red' : 'green'}}>{row.profit?.toFixed(2)}</TableCell>
                  <TableCell>{row.entryTime ? new Date(row.entryTime * 1000).toLocaleString() : '-'}</TableCell>
                  <TableCell>{row.exitTime ? new Date(row.exitTime * 1000).toLocaleString() : '-'}</TableCell>
                  <TableCell>{row.reason || '-'}</TableCell>
                  <TableCell>{row.broker_name || '-'}</TableCell>
                  <TableCell>{row.account_id || '-'}</TableCell>
                  <TableCell>{row.execution_mode || '-'}</TableCell>
                </TableRow>
              ))}
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
