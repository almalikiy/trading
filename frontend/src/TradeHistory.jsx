import React, { useEffect, useState } from "react";
import { Box, Typography, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Alert, CircularProgress, Divider, Button, Snackbar, Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions } from "@mui/material";

const API_BASE = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

export default function TradeHistory() {
  const [history, setHistory] = useState([]);
  const [mt5Status, setMt5Status] = useState(null);
  const [errorLog, setErrorLog] = useState([]);
  const [loading, setLoading] = useState(true);
  const [forceCloseLoading, setForceCloseLoading] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'info' });
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/trade/history`)
      .then(res => res.json())
      .then(data => setHistory(Array.isArray(data) ? data : []));

    fetch(`${API_BASE}/mt5/status`)
      .then(res => res.json())
      .then(data => setMt5Status(data.connected))
      .catch(() => setMt5Status(false));

    fetch(`${API_BASE}/mt5/error_log`)
      .then(res => res.json())
      .then(data => setErrorLog(Array.isArray(data) ? data : []))
      .finally(() => setLoading(false));
  }, []);

  const handleForceClose = () => {
    setForceCloseLoading(true);
    fetch(`${API_BASE}/trade/force_close`, { method: "POST" })
      .then(res => res.json())
      .then(data => {
        setSnackbar({ open: true, message: `Closed: ${data.closed.length}, Errors: ${data.errors.length}`, severity: 'success' });
      fetch(`${API_BASE}/trade/history`)
        // Optionally refresh history after force close
        fetch(`${API_BASE}/trade/history`)
          .then(res => res.json())
          .then(data => setHistory(Array.isArray(data) ? data : []));
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
          {(!loading && errorLog.length > 0) && (
            <span style={{ color: '#d32f2f', fontWeight: 400, marginLeft: 12, fontSize: 14 }}>
              {errorLog[0].message}
            </span>
          )}
        </Typography>
        {loading ? <CircularProgress size={20} /> : (
          errorLog.length === 0 ? (
            <Typography variant="body2" color="text.secondary">No MT5 errors recorded.</Typography>
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell width={160}>Time</TableCell>
                    <TableCell width={180}>Broker</TableCell>
                    <TableCell>Error Message</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {errorLog.map((row, idx) => (
                    <TableRow key={idx}>
                      <TableCell>{new Date(row.timestamp * 1000).toLocaleString()}</TableCell>
                      <TableCell>{row.broker_name || "-"}</TableCell>
                      <TableCell>{row.message}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )
        )}
      </Paper>

      <Paper>
        <TableContainer>
          <Table size="small">
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
                <TableCell>Exec</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {history.map((row, idx) => (
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
                  <TableCell>{row.execution_mode || '-'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>
    </Box>
  );
}
