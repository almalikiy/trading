import React, { useEffect, useState } from "react";
import { Box, Typography, Paper, Button, TextField, Grid, Switch, FormControlLabel } from "@mui/material";


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

  // Fetch enable_real_trade from backend on mount
  useEffect(() => {
    fetch("http://localhost:8000/account/state")
      .then(res => res.json())
      .then(data => {
        setState(data);
        if (typeof data.enable_real_trade === 'boolean') {
          setEnableMT5(data.enable_real_trade);
        }
      });
  }, []);

  useEffect(() => {
    fetch("http://localhost:8000/account/state")
      .then(res => res.json())
      .then(data => setState(data));
  }, []);

  // Persist enableMT5 to localStorage and backend whenever it changes
  useEffect(() => {
    localStorage.setItem('enableMT5', enableMT5);
    fetch("http://localhost:8000/account/set_enable_real_trade", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(enableMT5)
    });
  }, [enableMT5]);

  const handleDeposit = () => {
    fetch("http://localhost:8000/account/deposit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(deposit)
    }).then(() => window.location.reload());
  };
  const handleWithdraw = () => {
    fetch("http://localhost:8000/account/withdraw", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(withdraw)
    }).then(() => window.location.reload());
  };
  const handleAdjust = () => {
    fetch("http://localhost:8000/account/adjustment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount: adjust, note: adjustNote })
    }).then(() => window.location.reload());
  };
  const handleInitBalance = () => {
    fetch("http://localhost:8000/account/set_initial_balance", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(initBalance)
    }).then(() => window.location.reload());
  };
  const handleLot = () => {
    fetch("http://localhost:8000/account/set_lot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(lot)
    }).then(() => window.location.reload());
  };
  const handleMaxOpen = () => {
    fetch("http://localhost:8000/account/set_max_open_trades", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(maxOpen)
    }).then(() => window.location.reload());
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
    </Box>
  );
}
