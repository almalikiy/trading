



// Saat autoTPSL dinonaktifkan, set customTP/customSL ke nilai analytic terakhir
// (letakkan useEffect ini di dalam komponen App, bukan di luar file)



// Helper: Calculate ATR (Average True Range) for last N bars
function calcATR(ohlcv, period = 14) {
  if (!ohlcv || ohlcv.length < period + 1) return null;
  let trs = [];
  for (let i = ohlcv.length - period; i < ohlcv.length; ++i) {
    const high = ohlcv[i].high;
    const low = ohlcv[i].low;
    const prevClose = ohlcv[i - 1].close;
    trs.push(Math.max(
      high - low,
      Math.abs(high - prevClose),
      Math.abs(low - prevClose)
    ));
  }
  return trs.reduce((a, b) => a + b, 0) / trs.length;
}

// Helper: Find nearest support/resistance (simple: min/max of last N bars)
function findSupportResistance(ohlcv, period = 20) {
  if (!ohlcv || ohlcv.length < period) return { support: null, resistance: null };
  let lows = ohlcv.slice(-period).map(b => b.low);
  let highs = ohlcv.slice(-period).map(b => b.high);
  return {
    support: Math.min(...lows),
    resistance: Math.max(...highs)
  };
}

import React, { useEffect, useState, useRef } from "react";
import { v4 as uuidv4 } from 'uuid';
import { useNavigate } from "react-router-dom";
import CandlestickChart from "./CandlestickChart";
import LineChart from "./LineChart";
import { Box, Typography, Paper, Grid, Button, TextField, Alert, ButtonGroup, Snackbar, Alert as MuiAlert, Select, MenuItem, InputLabel, FormControl, Switch, FormControlLabel, CssBaseline, Checkbox } from "@mui/material";
import { ThemeProvider, createTheme } from '@mui/material/styles';
import ReconnectingWebSocket from "reconnecting-websocket";

// Helper: check if user can still late follow the signal
function canLateFollow(signal, lastSignalTime, ohlcv, maxDelaySec = 60) {
  if (!signal || signal === 'wait' || !lastSignalTime || !ohlcv || ohlcv.length === 0) return false;
  const nowEpoch = Math.floor(Date.now() / 1000);
  const delay = nowEpoch - lastSignalTime;
  if (delay > maxDelaySec) return false;
  // Check if price is still close to the open price when signal appeared
  // (can be improved according to strategy)
  return true;
}

// Preset strategi (boleh di luar komponen)
const strategyPresets = [
  {
    label: 'Scalp Cepat',
    value: 'scalp_cepat',
    params: { rsi: 14, rsiLevel: 20, macdFast: 12, macdSlow: 26, macdSignal: 9, stochK: 5, stochD: 3, stochS: 3, bbPeriod: 20, bbStd: 2, maPeriod: 20 }
  },
  {
    label: 'Scalp Konsolidasi (Range)',
    value: 'scalp_range',
    params: { rsi: 14, rsiLevel: 30, macdFast: 12, macdSlow: 26, macdSignal: 9, stochK: 5, stochD: 3, stochS: 3, bbPeriod: 20, bbStd: 2, maPeriod: 20 }
  },
  {
    label: 'Scalp Maksimal',
    value: 'scalp_maksimal',
    params: { rsi: 7, rsiLevel: 20, macdFast: 5, macdSlow: 13, macdSignal: 9, stochK: 3, stochD: 1, stochS: 1, bbPeriod: 20, bbStd: 2, maPeriod: 20 }
  },
  {
    label: 'Scalp Long (Momentum Panjang)',
    value: 'scalp_long',
    params: { rsi: 14, rsiLevel: 40, macdFast: 12, macdSlow: 26, macdSignal: 9, stochK: 5, stochD: 3, stochS: 3, bbPeriod: 20, bbStd: 2, maPeriod: 50 }
  }
  // Tambah preset lain sesuai kebutuhan
];


// === Backend URL Config ===
const BACKEND_URLS = {
  mt5: {
    http: "http://localhost:8000",
    ws: "ws://localhost:8000/ws/signal"
  },
  sim: {
    http: "http://localhost:8001",
    ws: "ws://localhost:8001/ws/signal"
  }
};

function getBackendUrl(engine, type = 'http') {
  return BACKEND_URLS[engine]?.[type] || BACKEND_URLS.mt5[type];
}

const WS_URL = getBackendUrl('mt5', 'ws');

export default function App() {
    const navigate = useNavigate();
    <Button variant="contained" color="primary" sx={{ml:2}} onClick={() => navigate("/history")}>Trade History</Button>
  // --- Strategy Preset & Indicator Params State ---
  const [selectedPreset, setSelectedPreset] = useState('scalp_cepat');
  const [indicatorParams, setIndicatorParams] = useState(strategyPresets[0].params);

  const [tradeMode, setTradeMode] = useState('scalp'); // default: scalp mode

  // --- Analytic TP/SL toggle state ---
  const [autoTPSL, setAutoTPSL] = useState(false);
  const [enableReversalWarning, setEnableReversalWarning] = useState(true);
  const [reversalWarning, setReversalWarning] = useState("");
  // State for checklist and custom TP/SL value
  const [useCustomTP, setUseCustomTP] = useState(true);
  const [customTP, setCustomTP] = useState(1.0); // default 10 pip (1.0 XAUUSD)
  const [customTPManuallySet, setCustomTPManuallySet] = useState(false);
  const [useCustomSL, setUseCustomSL] = useState(false);
  const [customSL, setCustomSL] = useState(5.0); // default SL 5 USD
  // Auto adjust TP when tradeMode changes (scalp: 0.5, normal: 1.0), but only if not manually set
  useEffect(() => {
    if (!customTPManuallySet) {
      if (tradeMode === 'scalp') {
        setCustomTP(0.5); // 5 pip
      } else {
        setCustomTP(1.0); // 10 pip
      }
    }
  }, [tradeMode, customTPManuallySet]);
  const [lastSignalTime, setLastSignalTime] = useState(null);
  const [lateFollowMsg, setLateFollowMsg] = useState("");
  const [signalError, setSignalError] = useState(null);
  const [chartMode, setChartMode] = useState('candlestick');
  const [signal, setSignal] = useState("wait");
  const [prevSignal, setPrevSignal] = useState("wait");
  const [indicators, setIndicators] = useState({});
  const [prevIndicators, setPrevIndicators] = useState({});
  const [sim, setSim] = useState({ balance: 1000, open_trade: false, pnl: 0 });
  const [ohlcv, setOhlcv] = useState([]);
  const [ohlcvWarning, setOhlcvWarning] = useState("");
  const [ohlcvError, setOhlcvError] = useState(false);
  const [symbol, setSymbol] = useState("XAUUSD");
  const [tf, setTf] = useState("M1");
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMsg, setSnackbarMsg] = useState("");
  const [barCount, setBarCount] = useState(60); // default: 60 bars
  const [darkMode, setDarkMode] = useState(false);
  // const [tradeMode, setTradeMode] = useState('scalp'); // default: scalp mode (duplicate, removed)
  const [engine, setEngine] = useState('mt5'); // mt5/sim

  // Automatic simulation: user always follows signal, lot 0.01
  // user_id: use UUID in localStorage if not logged in
  let USER_ID = localStorage.getItem('user_id');
  if (!USER_ID) {
    USER_ID = uuidv4();
    localStorage.setItem('user_id', USER_ID);
  }
  const [simu, setSimu] = useState({
    balance: 1000,
    openTrade: false,
    entryPrice: null,
    entryTime: null,
    direction: null, // 'buy' atau 'sell'
    pnl: 0,
    lastSignal: 'wait',
    tradeHistory: []
  });

  // Load open trade from backend user profile on page load (use engine utama)
  useEffect(() => {
    fetch(`${getBackendUrl(engine, 'http')}/user/open_trade?user_id=${USER_ID}`)
      .then(res => {
        if (!res.ok) throw new Error('Failed to fetch open trade');
        return res.json();
      })
      .then(data => {
        // Defensive: ensure tradeHistory is always an array
        if (!data || typeof data !== 'object') data = {};
        if (!Array.isArray(data.tradeHistory)) data.tradeHistory = [];
        // Defensive: fill missing fields with defaults
        setSimu({
          balance: typeof data.balance === 'number' ? data.balance : 1000,
          openTrade: !!data.openTrade,
          entryPrice: data.entryPrice ?? null,
          entryTime: data.entryTime ?? null,
          direction: data.direction ?? null,
          pnl: typeof data.pnl === 'number' ? data.pnl : 0,
          lastSignal: data.lastSignal ?? 'wait',
          tradeHistory: data.tradeHistory
        });
      })
      .catch(() => {
        // On error, reset to default state
        setSimu({
          balance: 1000,
          openTrade: false,
          entryPrice: null,
          entryTime: null,
          direction: null,
          pnl: 0,
          lastSignal: 'wait',
          tradeHistory: []
        });
      });
  }, [engine]);

  // Run simulation every time signal or price changes, and auto-close trade if TP hit
  useEffect(() => {
    if (!ohlcv || ohlcv.length < 20) return;
    const lastBar = ohlcv[ohlcv.length - 1];
    const prevBar = ohlcv[ohlcv.length - 2];

    // --- Analytic TP/SL calculation ---
    let analyticTP = customTP;
    let analyticSL = customSL;
    const direction = simu.direction;
    if (autoTPSL) {
      // ATR-based TP/SL
      const atr = calcATR(ohlcv, 14) || 1;
      // Support/resistance
      const { support, resistance } = findSupportResistance(ohlcv, 20);
      // Volatility (stddev of close)
      const closes = ohlcv.slice(-20).map(b => b.close);
      const mean = closes.reduce((a, b) => a + b, 0) / closes.length;
      const std = Math.sqrt(closes.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / closes.length);
      // TP: min(ATR*2, jarak ke resistance/support, 2*stddev)
      if (direction === 'buy') {
        const distRes = resistance ? resistance - lastBar.close : atr * 2;
        analyticTP = Math.max(0.1, Math.min(atr * 2, distRes, std * 2));
        const distSup = lastBar.close - support;
        analyticSL = Math.max(0.1, Math.min(atr, distSup, std));
      } else if (direction === 'sell') {
        const distSup = lastBar.close - support;
        analyticTP = Math.max(0.1, Math.min(atr * 2, distSup, std * 2));
        const distRes = resistance ? resistance - lastBar.close : atr * 2;
        analyticSL = Math.max(0.1, Math.min(atr, Math.abs(distRes), std));
      }
    }

    setSimu(prev => {
      let { balance, openTrade, entryPrice, entryTime, direction, pnl, lastSignal, tradeHistory } = prev;
      let newTradeHistory = [...tradeHistory];
      let tpHit = false;
      let slHit = false;
      let reversalHit = false;
      // Only process if signal changes (and not 'wait')
      if (signal !== lastSignal && signal !== 'wait') {
        if (signal === 'buy') {
          // Close sell position if any
          if (openTrade && direction === 'sell') {
            const closePrice = lastBar.open;
            const profit = (entryPrice - closePrice) * 100 * 0.01;
            balance += profit;
            newTradeHistory.push({
              type: 'SELL', entry: entryPrice, exit: closePrice, profit, entryTime, exitTime: lastBar.time,
              tpValue: prev.tpValue, slValue: prev.slValue
            });
            openTrade = false; entryPrice = null; entryTime = null; direction = null; pnl = 0;
          }
          // Open buy position if not already open
          if (!openTrade) {
            openTrade = true; entryPrice = lastBar.open; entryTime = lastBar.time; direction = 'buy'; pnl = 0;
            // Capture TP/SL at open
            prev.tpValue = autoTPSL ? analyticTP : (useCustomTP ? customTP : null);
            prev.slValue = autoTPSL ? analyticSL : (useCustomSL ? customSL : null);
          }
        } else if (signal === 'sell') {
          // Close buy position if any
          if (openTrade && direction === 'buy') {
            const closePrice = lastBar.open;
            const profit = (closePrice - entryPrice) * 100 * 0.01;
            balance += profit;
            newTradeHistory.push({
              type: 'BUY', entry: entryPrice, exit: closePrice, profit, entryTime, exitTime: lastBar.time,
              tpValue: prev.tpValue, slValue: prev.slValue
            });
            openTrade = false; entryPrice = null; entryTime = null; direction = null; pnl = 0;
          }
          // Open sell position if not already open
          if (!openTrade) {
            openTrade = true; entryPrice = lastBar.open; entryTime = lastBar.time; direction = 'sell'; pnl = 0;
            // Capture TP/SL at open
            prev.tpValue = autoTPSL ? analyticTP : (useCustomTP ? customTP : null);
            prev.slValue = autoTPSL ? analyticSL : (useCustomSL ? customSL : null);
          }
        }
      }
      // Auto-close trade if TP hit (when TP is enabled)
      if (openTrade && entryPrice != null && prev.tpValue && prev.tpValue > 0) {
        let tpPrice = null;
        if (direction === 'buy') tpPrice = entryPrice + prev.tpValue;
        else if (direction === 'sell') tpPrice = entryPrice - prev.tpValue;
        if ((direction === 'buy' && lastBar.close >= tpPrice) || (direction === 'sell' && lastBar.close <= tpPrice)) {
          // Close trade at TP
          const closePrice = tpPrice;
          const profit = direction === 'buy'
            ? (closePrice - entryPrice) * 100 * 0.01
            : (entryPrice - closePrice) * 100 * 0.01;
          balance += profit;
          newTradeHistory.push({
            type: direction === 'buy' ? 'BUY' : 'SELL',
            entry: entryPrice,
            exit: closePrice,
            profit,
            entryTime,
            exitTime: lastBar.time,
            tpValue: prev.tpValue, slValue: prev.slValue,
            analytic: autoTPSL ? true : undefined
          });
          openTrade = false; entryPrice = null; entryTime = null; direction = null; pnl = 0;
          tpHit = true;
        }
      }
      // Auto-close trade if SL hit (when SL is enabled)
      if (openTrade && entryPrice != null && prev.slValue && prev.slValue > 0) {
        let slPrice = null;
        if (direction === 'buy') slPrice = entryPrice - prev.slValue;
        else if (direction === 'sell') slPrice = entryPrice + prev.slValue;
        if ((direction === 'buy' && lastBar.close <= slPrice) || (direction === 'sell' && lastBar.close >= slPrice)) {
          // Close trade at SL
          const closePrice = slPrice;
          const profit = direction === 'buy'
            ? (closePrice - entryPrice) * 100 * 0.01
            : (entryPrice - closePrice) * 100 * 0.01;
          balance += profit;
          newTradeHistory.push({
            type: direction === 'buy' ? 'BUY' : 'SELL',
            entry: entryPrice,
            exit: closePrice,
            profit,
            entryTime,
            exitTime: lastBar.time,
            tpValue: prev.tpValue, slValue: prev.slValue,
            analytic: autoTPSL ? true : undefined
          });
          openTrade = false; entryPrice = null; entryTime = null; direction = null; pnl = 0;
          slHit = true;
        }
      }
      // Auto-close trade if reversal warning appears and enabled
      if (openTrade && entryPrice != null && enableReversalWarning && reversalWarning) {
        // Close trade at lastBar.close
        const closePrice = lastBar.close;
        const profit = direction === 'buy'
          ? (closePrice - entryPrice) * 100 * 0.01
          : (entryPrice - closePrice) * 100 * 0.01;
        balance += profit;
        newTradeHistory.push({
          type: direction === 'buy' ? 'BUY' : 'SELL',
          entry: entryPrice,
          exit: closePrice,
          profit,
          entryTime,
          exitTime: lastBar.time,
          reason: 'Reversal Warning'
        });
        openTrade = false; entryPrice = null; entryTime = null; direction = null; pnl = 0;
        reversalHit = true;
      }
      // Update floating PnL if there is an open position
      if (openTrade && entryPrice != null) {
        if (direction === 'buy') {
          pnl = (lastBar.close - entryPrice) * 100 * 0.01;
        } else if (direction === 'sell') {
          pnl = (entryPrice - lastBar.close) * 100 * 0.01;
        }
      } else {
        pnl = 0;
      }
      // Save to backend if openTrade, remove if not (use engine utama)
      if (openTrade && entryPrice != null) {
        fetch(`${getBackendUrl(engine, 'http')}/user/open_trade?user_id=${USER_ID}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            balance,
            openTrade,
            entryPrice,
            entryTime,
            direction,
            pnl,
            lastSignal: signal,
            tradeHistory: newTradeHistory
          })
        });
      } else {
        fetch(`${getBackendUrl(engine, 'http')}/user/open_trade?user_id=${USER_ID}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ openTrade: false })
        });
      }
      return {
        balance,
        openTrade,
        entryPrice,
        entryTime,
        direction,
        pnl,
        lastSignal: signal,
        tradeHistory: newTradeHistory
      };
    });
  }, [signal, ohlcv, useCustomTP, customTP, useCustomSL, customSL, enableReversalWarning, reversalWarning]);

  const theme = createTheme({
    palette: {
      mode: darkMode ? 'dark' : 'light',
      primary: { main: '#1976d2' },
      secondary: { main: '#43e97b' },
    },
    typography: {
      fontSize: 13,
      h4: { fontSize: '1.3rem', '@media (max-width:600px)': { fontSize: '1.1rem' } },
      h6: { fontSize: '1.1rem', '@media (max-width:600px)': { fontSize: '1rem' } },
      body2: { fontSize: '0.95rem', '@media (max-width:600px)': { fontSize: '0.85rem' } },
    },
    components: {
      MuiPaper: {
        styleOverrides: {
          root: {
            '@media (max-width:600px)': {
              padding: '8px !important',
              marginBottom: '10px',
            },
          },
        },
      },
    },
  });

  useEffect(() => {
    // Choose engine base URL
    const baseUrl = getBackendUrl(engine, 'http');
    const fetchSignal = () => {
      fetch(`${baseUrl}/signal?symbol=${symbol}&mode=${tradeMode}`)
        .then(res => res.json())
        .then(data => {
          if (data.error) {
            setSignalError(data.error + (data.details ? ': ' + JSON.stringify(data.details) : ''));
            setSignal('wait');
            setIndicators({});
            setSim({ balance: 1000, open_trade: false, pnl: 0 });
            return;
          } else {
            setSignalError(null);
          }
          setPrevSignal(signal);
          setSignal(data.signal);
          setPrevIndicators(indicators);
          setIndicators(data.indicators);
          setSim(data.simulator);
        });
    };
    fetchSignal();
    const timer = setInterval(fetchSignal, 1000);
    return () => clearInterval(timer);
  }, [symbol, tradeMode, engine]);

  useEffect(() => {
    if (prevSignal && signal && prevSignal !== signal) {
          setSnackbarMsg(`Signal changed from ${prevSignal.toUpperCase()} to ${signal.toUpperCase()}`);
      setSnackbarOpen(true);
    }
    if (signal && signal !== 'wait') {
      setLastSignalTime(Math.floor(Date.now() / 1000));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signal]);

  // Auto refresh OHLCV tiap detik
  useEffect(() => {
    const baseUrl = getBackendUrl(engine, 'http');
    let timer;
    let stopped = false;
    const fetchOhlcv = () => {
      fetch(`${baseUrl}/ohlcv?symbol=${symbol}&timeframe=${tf}&bars=${barCount}`)
        .then((res) => {
          if (!res.ok) throw new Error("Backend not active");
          return res.json();
        })
        .then((data) => {
          //console.log("OHLCV Response:", data); // DEBUG: tampilkan respons OHLCV
          if (!Array.isArray(data)) {
            setOhlcv([]);
            setOhlcvWarning("Format data OHLCV tidak valid dari backend.");
            setOhlcvError(true);
            stopped = true;
            return;
          }
          if (data.length < barCount) {
            setOhlcv([]);
            setOhlcvWarning(`Data tidak cukup untuk menampilkan ${barCount} bar. Hanya tersedia ${data.length} bar.`);
            setOhlcvError(true);
            stopped = true;
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
        });
      if (!stopped) timer = setTimeout(fetchOhlcv, 1000);
    };
    fetchOhlcv();
    return () => clearTimeout(timer);
  }, [symbol, tf, barCount, engine]);

  useEffect(() => {
    let ws;
    let pollingFallback;
    let wsActive = false;
    function startPolling() {
      const baseUrl = getBackendUrl(engine, 'http');
      const fetchSignal = () => {
        fetch(`${baseUrl}/signal?symbol=${symbol}&mode=${tradeMode}`)
          .then(res => res.json())
          .then(data => {
            if (data.error) {
              setSignalError(data.error + (data.details ? ': ' + JSON.stringify(data.details) : ''));
              setSignal('wait');
              setIndicators({});
              setSim({ balance: 1000, open_trade: false, pnl: 0 });
              return;
            } else {
              setSignalError(null);
            }
            setPrevSignal(signal);
            setSignal(data.signal);
            setPrevIndicators(indicators);
            setIndicators(data.indicators);
            setSim(data.simulator);
          });
      };
      fetchSignal();
      pollingFallback = setInterval(fetchSignal, 3000); // fallback polling setiap 3 detik
    }

    try {
      ws = new ReconnectingWebSocket(`${WS_URL}?symbol=${symbol}&mode=${tradeMode}&engine=${engine}`);
      ws.onopen = () => { wsActive = true; };
      ws.onmessage = (e) => {
        wsActive = true;
        const data = JSON.parse(e.data);
        if (data.error) {
          setSignalError(data.error + (data.details ? ': ' + JSON.stringify(data.details) : ''));
          setSignal('wait');
          setIndicators({});
          setSim({ balance: 1000, open_trade: false, pnl: 0 });
          return;
        } else {
          setSignalError(null);
        }
        setPrevSignal(signal);
        setSignal(data.signal);
        setPrevIndicators(indicators);
        setIndicators(data.indicators);
        setSim(data.simulator);
      };
      ws.onerror = () => {
        wsActive = false;
        if (!pollingFallback) startPolling();
      };
      ws.onclose = () => {
        wsActive = false;
        if (!pollingFallback) startPolling();
      };
    } catch (e) {
      startPolling();
    }
    // Fallback polling jika websocket tidak aktif
    setTimeout(() => { if (!wsActive && !pollingFallback) startPolling(); }, 2000);
    return () => {
      if (ws) ws.close();
      if (pollingFallback) clearInterval(pollingFallback);
    };
  }, [symbol, tradeMode, engine]);

  useEffect(() => {
    if (prevSignal && signal && prevSignal !== signal) {
      setSnackbarMsg(`Signal berubah dari ${prevSignal.toUpperCase()} ke ${signal.toUpperCase()}`);
      setSnackbarOpen(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signal]);


  // (Dihapus: useEffect fetch OHLCV dengan bars=60 yang menyebabkan konflik data)

  // Prepare candlestick data (placeholder)
  // const chartData = { ... };
  // const chartOptions = { ... };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ p: { xs: 1, sm: 2 }, maxWidth: 1200, mx: 'auto', width: '100%' }}>
      <Snackbar open={snackbarOpen} autoHideDuration={2500} onClose={() => setSnackbarOpen(false)} anchorOrigin={{vertical:'bottom',horizontal:'center'}}>
        <MuiAlert onClose={() => setSnackbarOpen(false)} severity={signal === 'buy' ? 'success' : 'info'} sx={{ width: '100%' }}>
          {snackbarMsg}
        </MuiAlert>
      </Snackbar>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
        <Typography variant="h4" gutterBottom>
          Trading Signal Dashboard
        </Typography>
        <Button variant="outlined" color="secondary" sx={{ml:2}} onClick={() => {
          if (canLateFollow(signal, lastSignalTime, ohlcv, 60)) {
            setLateFollowMsg('Still safe to late follow this signal (<= 60 seconds).');
          } else {
            setLateFollowMsg('Too late/not recommended to late follow.');
          }
        }}>
          Check for Late Follow
        </Button>
        {lateFollowMsg && (
          <Typography variant="body2" color={lateFollowMsg.includes('safe') ? 'green' : 'red'} sx={{ml:2, mt:1}}>
            {lateFollowMsg}
          </Typography>
        )}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel id="engine-label">Engine</InputLabel>
            <Select
              labelId="engine-label"
              value={engine}
              label="Engine"
              onChange={e => setEngine(e.target.value)}
            >
              <MenuItem value="mt5">MT5 (Live)</MenuItem>
              <MenuItem value="sim">Simulation</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel id="trade-mode-label">Mode</InputLabel>
            <Select
              labelId="trade-mode-label"
              value={tradeMode}
              label="Mode"
              onChange={e => setTradeMode(e.target.value)}
            >
              <MenuItem value="normal">Normal</MenuItem>
              <MenuItem value="scalp">Scalp</MenuItem>
            </Select>
          </FormControl>
          <FormControlLabel
            control={<Switch checked={darkMode} onChange={() => setDarkMode(v => !v)} color="primary" />}
            label={darkMode ? 'Dark Mode' : 'Light Mode'}
          />
        </Box>
      </Box>

      {/* Panel Preset Strategi & Parameter */}
      <Paper sx={{ p: { xs: 1, sm: 2 }, mb: 2, mt: 2 }}>
        <Typography variant="h6" sx={{ mb: 1 }}>Strategy Preset & Indicator Parameters</Typography>
        <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 2, alignItems: 'center' }}>
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel id="preset-label">Preset</InputLabel>
            <Select labelId="preset-label" value={selectedPreset} label="Preset" onChange={e => setSelectedPreset(e.target.value)}>
              {strategyPresets.map(p => <MenuItem key={p.value} value={p.value}>{p.label}</MenuItem>)}
            </Select>
          </FormControl>
          {/* Parameter indikator */}
          <TextField label="RSI Period" type="number" size="small" value={indicatorParams.rsi} onChange={e => handleParamChange('rsi', Number(e.target.value))} sx={{ width: 100 }} />
          <TextField label="RSI Level" type="number" size="small" value={indicatorParams.rsiLevel} onChange={e => handleParamChange('rsiLevel', Number(e.target.value))} sx={{ width: 100 }} />
          <TextField label="MACD Fast" type="number" size="small" value={indicatorParams.macdFast} onChange={e => handleParamChange('macdFast', Number(e.target.value))} sx={{ width: 100 }} />
          <TextField label="MACD Slow" type="number" size="small" value={indicatorParams.macdSlow} onChange={e => handleParamChange('macdSlow', Number(e.target.value))} sx={{ width: 100 }} />
          <TextField label="MACD Signal" type="number" size="small" value={indicatorParams.macdSignal} onChange={e => handleParamChange('macdSignal', Number(e.target.value))} sx={{ width: 100 }} />
          <TextField label="Stoch K" type="number" size="small" value={indicatorParams.stochK} onChange={e => handleParamChange('stochK', Number(e.target.value))} sx={{ width: 100 }} />
          <TextField label="Stoch D" type="number" size="small" value={indicatorParams.stochD} onChange={e => handleParamChange('stochD', Number(e.target.value))} sx={{ width: 100 }} />
          <TextField label="Stoch S" type="number" size="small" value={indicatorParams.stochS} onChange={e => handleParamChange('stochS', Number(e.target.value))} sx={{ width: 100 }} />
          <TextField label="BB Period" type="number" size="small" value={indicatorParams.bbPeriod} onChange={e => handleParamChange('bbPeriod', Number(e.target.value))} sx={{ width: 100 }} />
          <TextField label="BB Std" type="number" size="small" value={indicatorParams.bbStd} onChange={e => handleParamChange('bbStd', Number(e.target.value))} sx={{ width: 100 }} />
          <TextField label="MA Period" type="number" size="small" value={indicatorParams.maPeriod} onChange={e => handleParamChange('maPeriod', Number(e.target.value))} sx={{ width: 100 }} />
        </Box>
        <Typography variant="caption" sx={{ mt: 1, display: 'block' }}>
          * Changing parameters only affects chart/indicator visualization. Trade signals (open/close) always follow backend.
        </Typography>
      </Paper>
      {signalError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {signalError}
        </Alert>
      )}
      {ohlcvError && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {ohlcvWarning ? (
            <>
              {ohlcvWarning}<br />
              <Button variant="outlined" size="small" sx={{ mt: 1 }} onClick={() => {
                setOhlcvWarning("");
                setOhlcvError(false);
                setBarCount(barCount); // trigger refetch
              }}>Retry Fetch</Button>
            </>
          ) : (
            <>
              Candlestick data not available.<br />
              <b>Make sure FastAPI backend is running at <code>localhost:8000</code></b>.<br />
              Run: <code>uvicorn app.main:app --reload</code> in the backend folder.<br />
              After backend is active, refresh this page.
            </>
          )}
        </Alert>
      )}
      <Paper sx={{ p: { xs: 1, sm: 2 }, mb: 2, overflowX: 'auto', width: '100%' }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} sm={3}>
            <TextField label="Symbol" value={symbol} onChange={e => setSymbol(e.target.value)} size="small" fullWidth />
          </Grid>
          <Grid item xs={12} sm={4}>
            <ButtonGroup variant="outlined" color="primary" size="small">
              {['M1','M5','M15','M30'].map(opt => (
                <Button
                  key={opt}
                  variant={tf === opt ? 'contained' : 'outlined'}
                  onClick={() => setTf(opt)}
                >{opt}</Button>
              ))}
            </ButtonGroup>
          </Grid>
          <Grid item xs={12} sm={3}>
            <FormControl size="small" fullWidth>
              <InputLabel id="bar-count-label">Range</InputLabel>
              <Select
                labelId="bar-count-label"
                value={barCount}
                label="Range"
                onChange={e => setBarCount(Number(e.target.value))}
              >
                <MenuItem value={30}>30 Bars</MenuItem>
                <MenuItem value={60}>60 Bars</MenuItem>
                <MenuItem value={120}>120 Bars</MenuItem>
                <MenuItem value={240}>240 Bars</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={2}>
            <Button variant="contained" color="primary" fullWidth onClick={() => {
              setSymbol(symbol);
              setTf(tf);
            }}>
              Update
            </Button>
          </Grid>
        </Grid>
      </Paper>

      <Paper sx={{
        p: { xs: 1, sm: 2 },
        mb: 2,
        background: (theme) =>
          signal === 'buy'
            ? (theme.palette.mode === 'dark'
                ? 'linear-gradient(90deg,#1de9b6 0%,#00bfae 100%)'
                : 'linear-gradient(90deg,#43e97b 0%,#38f9d7 100%)')
            : (theme.palette.mode === 'dark'
                ? 'linear-gradient(90deg,#23272b 0%,#444950 100%)'
                : 'linear-gradient(90deg,#ece9e6 0%,#bab9b6 100%)'),
        border: signal === 'buy' ? '2px solid #1b5e20' : '1px solid #888',
        boxShadow: signal === 'buy' ? '0 0 12px 2px #43e97b55' : '0 0 8px 1px #bab9b655',
        transition: 'all 0.4s',
        overflowX: 'auto',
        color: (theme) => theme.palette.mode === 'dark' ? '#fff' : undefined,
        width: '100%',
        '@media (max-width:600px)': {
          padding: '8px !important',
          marginBottom: '10px',
        },
      }}>
        <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 2 }}>
          {/* Left Signal Panel */}
          <Box sx={{ flex: 1, minWidth: 0 }}>
            {/* Flip-flop panel for reversal warning or signal */}
            {reversalWarning ? (
              <Box sx={{
                p: 2,
                mb: 1,
                borderRadius: 2,
                background: 'linear-gradient(90deg,#ff1744 0%,#ff9100 100%)',
                color: '#fff',
                fontWeight: 'bold',
                fontSize: 20,
                textAlign: 'center',
                boxShadow: '0 0 12px 2px #ff174455',
                letterSpacing: 2,
                transition: 'all 0.4s',
              }}>
                REVERSAL WARNING: {reversalWarning}
              </Box>
            ) : (
              <Typography variant="h6" sx={{ fontWeight:'bold', letterSpacing:2 }}>
                Signal: <b style={{ color: signal === "buy" ? "#1b5e20" : "#424242", fontWeight:'bold', fontSize:22 }}>{signal ? signal.toUpperCase() : '-'}</b>
              </Typography>
            )}
            {/* Current Price */}
            {ohlcv && ohlcv.length > 0 && (
              <Typography variant="body2" sx={{ mt: 1, fontWeight: 'bold', color: '#1976d2' }}>
                Current Price: {ohlcv[ohlcv.length-1].close?.toFixed(2)}
              </Typography>
            )}
            {/* Main indicator summary for active timeframe */}
            {indicators && indicators[tf] ? (
              <Box sx={{ mt: 1 }}>
                <Typography variant="subtitle2">Summary {symbol} {tf}:</Typography>
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 14, color: darkMode ? '#fff' : undefined }}>
                  <li>RSI: <b style={{color: indicators[tf].rsi < 0 ? 'red' : undefined}}>{indicators[tf].rsi?.toFixed(2)}</b></li>
                  <li>MACD: <b style={{color: indicators[tf].macd < 0 ? 'red' : undefined}}>{indicators[tf].macd?.toFixed(2)}</b> | Signal: <b style={{color: indicators[tf].macd_signal < 0 ? 'red' : undefined}}>{indicators[tf].macd_signal?.toFixed(2)}</b></li>
                  <li>Bollinger Bands: <b style={{color: indicators[tf].bb_lower < 0 ? 'red' : undefined}}>{indicators[tf].bb_lower?.toFixed(2)}</b> - <b style={{color: indicators[tf].bb_mid < 0 ? 'red' : undefined}}>{indicators[tf].bb_mid?.toFixed(2)}</b> - <b style={{color: indicators[tf].bb_upper < 0 ? 'red' : undefined}}>{indicators[tf].bb_upper?.toFixed(2)}</b></li>
                  <li>SMA: <b style={{color: indicators[tf].sma < 0 ? 'red' : undefined}}>{indicators[tf].sma?.toFixed(2)}</b></li>
                  <li>Stoch K/D: <b style={{color: indicators[tf].stoch_k < 0 ? 'red' : undefined}}>{indicators[tf].stoch_k?.toFixed(2)}</b> / <b style={{color: indicators[tf].stoch_d < 0 ? 'red' : undefined}}>{indicators[tf].stoch_d?.toFixed(2)}</b></li>
                </ul>
              </Box>
            ) : null}
            {/* Last data time info */}
            {ohlcv && ohlcv.length > 0 && (
              <Typography variant="caption" sx={{ display: 'block', mt: 1 }}>
                Last data (GMT+2): {(() => {
                  const t = ohlcv[ohlcv.length-1].time;
                  if (!t) return '-';
                  // Convert epoch (UTC) to GMT+2
                  const dt = new Date((t + 2 * 3600) * 1000);
                  return dt.toLocaleString();
                })()} &nbsp;|&nbsp; 
                <span style={{color:'#888'}}>Note: Broker server time is usually GMT+2/GMT+3, this time = GMT+2</span>
              </Typography>
            )}
          </Box>
          {/* Right Simulation Panel */}
          <Box sx={{ flex: 1, minWidth: 0, borderLeft: { md: '1px solid #eee' }, pl: { md: 2, xs: 0 }, mt: { xs: 2, md: 0 } }}>
            <Typography variant="subtitle1" sx={{ fontWeight:'bold', letterSpacing:1, mb: 1 }}>Automatic Simulation (Follow Signal, 0.01 lot)</Typography>
            <Typography variant="body2">
              Balance: <span style={{color: simu && simu.balance < 0 ? 'red' : undefined}}>{simu && typeof simu.balance === 'number' ? `$${simu.balance.toFixed(2)}` : '-'}</span> |
              Floating PnL: <span style={{color: simu && simu.pnl < 0 ? 'red' : undefined}}>{simu && typeof simu.pnl === 'number' ? simu.pnl.toFixed(2) : '-'}</span> |
              Open Trade: {simu && simu.openTrade ? (simu.direction === 'buy' ? 'Buy' : 'Sell') : 'No'}
            </Typography>
            {/* Checklist and custom TP input */}
            <Box sx={{ display: 'flex', alignItems: 'center', mt: 1, gap: 2 }}>
              <Checkbox checked={useCustomTP} onChange={e => setUseCustomTP(e.target.checked)} />
              <Typography variant="body2">Set</Typography>
              <TextField
                label="TP Value"
                size="small"
                type="number"
                value={customTP}
                onChange={e => {6
                  setCustomTP(Number(e.target.value));
                  setCustomTPManuallySet(true);
                }}
                sx={{ width: 200 }}
                disabled={!useCustomTP || autoTPSL}
                inputProps={{ step: 0.1 }}
              />
              <Checkbox checked={useCustomSL} onChange={e => setUseCustomSL(e.target.checked)} sx={{ml:2}} />
              <Typography variant="body2">Set</Typography>
              <TextField
                label="SL Value"
                size="small"
                type="number"
                value={customSL}
                onChange={e => setCustomSL(Number(e.target.value))}
                sx={{ width: 200 }}
                disabled={!useCustomSL || autoTPSL}
                inputProps={{ step: 0.1 }}
              />
              <FormControlLabel
                control={<Checkbox checked={autoTPSL} onChange={e => setAutoTPSL(e.target.checked)} />}
                label={<Typography variant="body2" color="primary">Auto Analytic TP/SL</Typography>}
                sx={{ml:2}}
              />
              <Typography variant="caption">(in price units, e.g. 5 = 5 USD)</Typography>
            </Box>
            {/* Checklist for indicator reversal warning */}
            <Box sx={{ display: 'flex', alignItems: 'center', mt: 1 }}>
              <Checkbox checked={enableReversalWarning} onChange={e => setEnableReversalWarning(e.target.checked)} />
              <Typography variant="body2">Enable indicator reversal warning (RSI drop, fast stochastic overbought/oversold)</Typography>
            </Box>
            {simu && simu.openTrade && (
              <>
                <Typography variant="body2" sx={{ mt: 1 }}>
                  Entry: {simu.entryPrice ?? '-'} @ {simu.entryTime ? new Date(simu.entryTime * 1000).toLocaleString() : '-'} | Direction: {simu.direction ? simu.direction.toUpperCase() : '-'}
                </Typography>
                {/* Target profit estimation: fixed TP 10 pip (1 pip = 0.1 XAUUSD) or custom if checklist active */}
                <Typography variant="body2" sx={{ mt: 1, color: '#1976d2' }}>
                  Target Profit Estimate: {(() => {
                    if (!simu.entryPrice || !simu.direction) return '-';
                    if (useCustomTP && customTP > 0) {
                      if (simu.direction === 'buy') {
                        return (simu.entryPrice + customTP).toFixed(2);
                      } else if (simu.direction === 'sell') {
                        return (simu.entryPrice - customTP).toFixed(2);
                      }
                    } else {
                      const pip = 0.1;
                      const tpPip = 10; // 10 pip
                      if (simu.direction === 'buy') {
                        return (simu.entryPrice + pip * tpPip).toFixed(2);
                      } else if (simu.direction === 'sell') {
                        return (simu.entryPrice - pip * tpPip).toFixed(2);
                      }
                    }
                    return '-';
                  })()}
                </Typography>
              </>
            )}
            {simu && Array.isArray(simu.tradeHistory) && simu.tradeHistory.length > 0 && (
              <Box sx={{ mt: 1 }}>
                <Typography variant="caption" sx={{ fontWeight:'bold' }}>Last Closed Trade:</Typography>
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
                  <li>Type: {simu.tradeHistory[simu.tradeHistory.length-1]?.type ?? '-'}</li>
                  <li>Entry: {simu.tradeHistory[simu.tradeHistory.length-1]?.entry ?? '-'}</li>
                  <li>Exit: {simu.tradeHistory[simu.tradeHistory.length-1]?.exit ?? '-'}</li>
                  <li>Entry Time: {simu.tradeHistory[simu.tradeHistory.length-1]?.entryTime ? new Date(simu.tradeHistory[simu.tradeHistory.length-1].entryTime * 1000).toLocaleString() : '-'}</li>
                  <li>Exit Time: {simu.tradeHistory[simu.tradeHistory.length-1]?.exitTime ? new Date(simu.tradeHistory[simu.tradeHistory.length-1].exitTime * 1000).toLocaleString() : '-'}</li>
                  {simu.tradeHistory[simu.tradeHistory.length-1]?.reason && (
                    <li>Reason: {simu.tradeHistory[simu.tradeHistory.length-1].reason}</li>
                  )}
                  <li>Profit: <span style={{color: simu.tradeHistory[simu.tradeHistory.length-1]?.profit < 0 ? 'red' : '#1b5e20'}}>{typeof simu.tradeHistory[simu.tradeHistory.length-1]?.profit === 'number' ? simu.tradeHistory[simu.tradeHistory.length-1].profit.toFixed(2) : '-'}</span></li>
                  <li>Entry Time: {simu.tradeHistory[simu.tradeHistory.length-1]?.entryTime ?? '-'}</li>
                  <li>Exit Time: {simu.tradeHistory[simu.tradeHistory.length-1]?.exitTime ?? '-'}</li>
                </ul>
              </Box>
            )}
          </Box>
        </Box>
      </Paper>
      <Paper sx={{ p: { xs: 1, sm: 2 }, mb: 2, overflowX: 'auto', width: '100%' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
          <Typography variant="h6">Chart</Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            {/* Hapus dropdown mode waktu, chart hanya pakai waktu MT5 (UTC epoch) */}
            <Button
              size="small"
              variant={chartMode === 'candlestick' ? 'contained' : 'outlined'}
              onClick={() => setChartMode('candlestick')}
              sx={{ mr: 1 }}
            >Candlestick</Button>
            <Button
              size="small"
              variant={chartMode === 'line' ? 'contained' : 'outlined'}
              onClick={() => setChartMode('line')}
            >Line</Button>
          </Box>
        </Box>
        {/* Sembunyikan chart jika error, tampilkan tabel OHLCV */}
        {ohlcvError || !ohlcv || ohlcv.length === 0 ? (
          <>
            <Typography variant="body2" color="text.secondary">Chart not available. Displaying OHLCV data as table.</Typography>
            <div style={{ width: '100%', overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
              <table style={{ 
                fontSize: window.innerWidth < 600 ? 11 : 13, 
                minWidth: 500, width: '100%', borderCollapse: 'collapse', marginTop: 8, background: darkMode ? '#23272b' : '#fff', color: darkMode ? '#fff' : undefined }}>
                <thead>
                  <tr style={{ background: darkMode ? '#333b44' : '#f5f5f5', color: darkMode ? '#fff' : undefined }}>
                    <th style={{ 
                      border: '1px solid #ddd', 
                      padding: 4, 
                      background: darkMode ? '#333b44' : '#1976d2',
                      color: '#fff',
                      fontWeight: 'bold',
                      fontSize: 15,
                      textAlign: 'center',
                      letterSpacing: 1
                    }}>Time (epoch UTC)</th>
                    <th style={{ 
                      border: '1px solid #ddd', 
                      padding: 4, 
                      background: darkMode ? '#333b44' : '#1976d2',
                      color: '#fff',
                      fontWeight: 'bold',
                      fontSize: 15,
                      textAlign: 'center',
                      letterSpacing: 1
                    }}>Open</th>
                    <th style={{ 
                      border: '1px solid #ddd', 
                      padding: 4, 
                      background: darkMode ? '#333b44' : '#1976d2',
                      color: '#fff',
                      fontWeight: 'bold',
                      fontSize: 15,
                      textAlign: 'center',
                      letterSpacing: 1
                    }}>High</th>
                    <th style={{ 
                      border: '1px solid #ddd', 
                      padding: 4, 
                      background: darkMode ? '#333b44' : '#1976d2',
                      color: '#fff',
                      fontWeight: 'bold',
                      fontSize: 15,
                      textAlign: 'center',
                      letterSpacing: 1
                    }}>Low</th>
                    <th style={{ 
                      border: '1px solid #ddd', 
                      padding: 4,
                      background: darkMode ? '#333b44' : '#1976d2',
                      color: '#fff',
                      fontWeight: 'bold',
                      fontSize: 15,
                      textAlign: 'center',
                      letterSpacing: 1
                    }}>Close</th>
                    <th style={{ 
                      border: '1px solid #ddd', 
                      padding: 4, 
                      background: darkMode ? '#333b44' : '#1976d2',
                      color: '#fff',
                      fontWeight: 'bold',
                      fontSize: 15,
                      textAlign: 'center',
                      letterSpacing: 1
                    }}>Volume</th>
                  </tr>
                </thead>
                <tbody>
                  {(ohlcv || []).slice(-(barCount || 30)).reverse().map((d, i) => (
                    <tr key={i}>
                      <td style={{ border: '1px solid #ddd', padding: 4 }}>{d.time}</td>
                      <td style={{ border: '1px solid #ddd', padding: 4 }}>{d.open}</td>
                      <td style={{ border: '1px solid #ddd', padding: 4 }}>{d.high}</td>
                      <td style={{ border: '1px solid #ddd', padding: 4 }}>{d.low}</td>
                      <td style={{ border: '1px solid #ddd', padding: 4 }}>{d.close}</td>
                      <td style={{ border: '1px solid #ddd', padding: 4 }}>{d.tick_volume ?? d.volume ?? d.real_volume ?? '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          (chartMode === 'candlestick' ? (
            <CandlestickChart 
              ohlcv={ohlcv} 
              jumlahBar={barCount} 
              spread={(() => {
                if (ohlcv && ohlcv.length > 0) {
                  const last = ohlcv[ohlcv.length - 1];
                  if (last.ask !== undefined && last.bid !== undefined) {
                    return Math.abs(last.ask - last.bid);
                  }
                  // fallback: default 2.0 (misal 2 pip)
                  return 2.0;
                }
                return 2.0;
              })()}
            />
          ) : (
            <LineChart ohlcv={ohlcv} />
          ))
        )}
      </Paper>
      <Paper sx={{ p: { xs: 1, sm: 2 }, overflowX: 'auto', width: '100%' }}>
        <Typography variant="h6">Indicators (M1, M5, M15, M30)</Typography>
        <Typography variant="body2" sx={{ mb: 1, color: darkMode ? '#90caf9' : '#1976d2', fontWeight: 500 }}>
          Settings: RSI (10), MACD (12,26,9), BB (20,2), SMA (20), Stoch (14,3,3)
        </Typography>
        <div style={{ width: '100%', overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
        <table style={{ fontSize: window.innerWidth < 600 ? 11 : 13, minWidth: 700, width: '100%', borderCollapse: 'collapse', marginTop: 8, background: darkMode ? '#23272b' : '#fff', color: darkMode ? '#fff' : undefined }}>
          <thead>
            <tr style={{ background: darkMode ? '#333b44' : '#f5f5f5', color: darkMode ? '#fff' : undefined }}>
              <th style={{ 
                border: '1px solid #ddd', 
                padding: 4, 
                background: darkMode ? '#333b44' : '#1976d2',
                color: '#fff',
                fontWeight: 'bold',
                fontSize: 15,
                textAlign: 'center',
                letterSpacing: 1
              }}>TF</th>
              <th style={{ 
                border: '1px solid #ddd', 
                padding: 4, 
                background: darkMode ? '#333b44' : '#1976d2',
                color: '#fff',
                fontWeight: 'bold',
                fontSize: 15,
                textAlign: 'center',
                letterSpacing: 1
              }} title="Relative Strength Index">RSI</th>
              <th style={{ 
                border: '1px solid #ddd', 
                padding: 4, 
                background: darkMode ? '#333b44' : '#1976d2',
                color: '#fff',
                fontWeight: 'bold',
                fontSize: 15,
                textAlign: 'center',
                letterSpacing: 1
              }} title="Moving Average Convergence Divergence">MACD</th>
              <th style={{ 
                border: '1px solid #ddd', 
                padding: 4, 
                background: darkMode ? '#333b44' : '#1976d2',
                color: '#fff',
                fontWeight: 'bold',
                fontSize: 15,
                textAlign: 'center',
                letterSpacing: 1
              }} title="MACD Signal Line">MACD Sig</th>
              <th style={{ 
                border: '1px solid #ddd', 
                padding: 4, 
                background: darkMode ? '#333b44' : '#1976d2',
                color: '#fff',
                fontWeight: 'bold',
                fontSize: 15,
                textAlign: 'center',
                letterSpacing: 1
              }} title="Bollinger Bands Lower">BB Lower</th>
              <th style={{ 
                border: '1px solid #ddd', 
                padding: 4, 
                background: darkMode ? '#333b44' : '#1976d2',
                color: '#fff',
                fontWeight: 'bold',
                fontSize: 15,
                textAlign: 'center',
                letterSpacing: 1
              }} title="Bollinger Bands Middle">BB Mid</th>
              <th style={{ 
                border: '1px solid #ddd', 
                padding: 4, 
                background: darkMode ? '#333b44' : '#1976d2',
                color: '#fff',
                fontWeight: 'bold',
                fontSize: 15,
                textAlign: 'center',
                letterSpacing: 1
              }} title="Bollinger Bands Upper">BB Upper</th>
              <th style={{ 
                border: '1px solid #ddd', 
                padding: 4, 
                background: darkMode ? '#333b44' : '#1976d2',
                color: '#fff',
                fontWeight: 'bold',
                fontSize: 15,
                textAlign: 'center',
                letterSpacing: 1
              }} title="Simple Moving Average">SMA</th>
              <th style={{ 
                border: '1px solid #ddd', 
                padding: 4, 
                background: darkMode ? '#333b44' : '#1976d2',
                color: '#fff',
                fontWeight: 'bold',
                fontSize: 15,
                textAlign: 'center',
                letterSpacing: 1
              }} title="Stochastic Oscillator K">Stoch K</th>
              <th style={{ 
                border: '1px solid #ddd', 
                padding: 4, 
                background: darkMode ? '#333b44' : '#1976d2',
                color: '#fff',
                fontWeight: 'bold',
                fontSize: 15,
                textAlign: 'center',
                letterSpacing: 1
              }} title="Stochastic Oscillator D">Stoch D</th>
            </tr>
          </thead>
          <tbody>
            {['M1','M5','M15','M30'].map(tf => (
              indicators && indicators[tf] ? (
                <tr key={tf} style={
                  darkMode
                    ? { background: '#23272b', color: '#fff' }
                    : { background: '#e3f2fd' }
                }>
                  <td style={{ border: '1px solid #444', padding: 4, fontWeight: 'bold', textAlign: 'center', color: darkMode ? '#fff' : undefined }}>{tf}</td>
                  {['rsi','macd','macd_signal','bb_lower','bb_mid','bb_upper','sma','stoch_k','stoch_d'].map((key) => {
                    const val = indicators[tf][key];
                    const prev = prevIndicators[tf]?.[key];
                    let arrow = null;
                    if (prev !== undefined && val !== undefined) {
                      if (val > prev) arrow = <span style={{color:'#43e97b', fontWeight:'bold', marginLeft:4}}>&#9650;</span>; // hijau naik
                      else if (val < prev) arrow = <span style={{color:'#ef5350', fontWeight:'bold', marginLeft:4}}>&#9660;</span>; // merah turun
                    }
                    return (
                      <td key={key} style={{ border: '1px solid #444', padding: 4, textAlign: 'right', color: val < 0 ? '#ef5350' : (darkMode ? '#fff' : undefined), background: darkMode ? '#23272b' : undefined, verticalAlign:'middle' }}>
                        <span>{val?.toFixed(2)}</span>{arrow}
                      </td>
                    );
                  })}
                </tr>
              ) : null
            ))}
          </tbody>
        </table>
        </div>
        <button style={{marginTop:12, float:'right'}} onClick={() => exportIndicatorsToCSV(indicators)}>Export CSV</button>
      </Paper>
      {/* Trading Strategy Table */}
      <Paper sx={{ p: { xs: 1, sm: 2 }, mt: 2, mb: 2, overflowX: 'auto', width: '100%' }}>
        <Typography variant="h6" sx={{ mb: 1 }}>Trading Strategy Reference</Typography>
        <div style={{ width: '100%', overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
        <table style={{ fontSize: window.innerWidth < 600 ? 11 : 13, minWidth: 900, width: '100%', borderCollapse: 'collapse', background: darkMode ? '#23272b' : '#fff', color: darkMode ? '#fff' : undefined }}>
          <thead>
            <tr style={{ background: darkMode ? '#333b44' : '#e3f2fd', color: darkMode ? '#fff' : '#333', fontWeight: 'bold', fontSize: 14 }}>
              <th style={{ border: '1px solid #bbb', padding: 4 }}>Strategi</th>
              <th style={{ border: '1px solid #bbb', padding: 4 }}>RSI</th>
              <th style={{ border: '1px solid #bbb', padding: 4 }}>MACD</th>
              <th style={{ border: '1px solid #bbb', padding: 4 }}>Stochastic</th>
              <th style={{ border: '1px solid #bbb', padding: 4 }}>MA (Moving Average)</th>
              <th style={{ border: '1px solid #bbb', padding: 4 }}>Volume</th>
              <th style={{ border: '1px solid #bbb', padding: 4 }}>Kapan Open Trade</th>
              <th style={{ border: '1px solid #bbb', padding: 4 }}>TF Utama</th>
              <th style={{ border: '1px solid #bbb', padding: 4 }}>TF Konfirmasi</th>
              <th style={{ border: '1px solid #bbb', padding: 4 }}>TF Besar</th>
              <th style={{ border: '1px solid #bbb', padding: 4 }}>Catatan Penting</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style={{ border: '1px solid #bbb', padding: 4, fontWeight: 'bold' }}>Santai – Long Term</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>Period 14, level 30/70</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>12-26-9, lihat tren jangka panjang</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>14,3,3 (lebih lambat)</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>MA 50 & MA 200 (golden cross/death cross)</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>Konfirmasi tren besar</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>Entry saat tren jelas (cross MA, MACD searah, RSI &gt;50 atau &lt;50)</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>H4 – D1</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>W1</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>MN</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>Cocok untuk swing/position trader, tahan beberapa hari/minggu. Gunakan MA 50/200 dan MACD untuk arah tren besar.</td>
            </tr>
            <tr>
              <td style={{ border: '1px solid #bbb', padding: 4, fontWeight: 'bold' }}>Santai – Scalp</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>Period 14, level 20/80</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>12-26-9, gunakan histogram kecil</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>5,3,3 (lebih sensitif)</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>MA 20 (BB middle line)</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>Volume stabil</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>Entry di pantulan BB + RSI/Stoch ekstrem</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>M5 – M15</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>H1</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>H4</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>Target kecil (5–15 pips), hindari news high impact. Entry di pantulan BB + RSI/Stoch ekstrem. Hindari melawan tren H1.</td>
            </tr>
            <tr>
              <td style={{ border: '1px solid #bbb', padding: 4, fontWeight: 'bold' }}>Agresif – Long Term</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>Period 7, level 20/80</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>8-17-9, lebih cepat</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>5,3,3</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>MA 100 + MA 200</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>Volume besar (breakout)</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>Entry saat breakout dengan konfirmasi volume</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>H1 – H4</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>D1</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>W1</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>Risiko tinggi, bisa profit besar tapi rawan false breakout. Fokus pada breakout besar dengan volume tinggi. Konfirmasi MACD dan RSI di D1.</td>
            </tr>
            <tr>
              <td style={{ border: '1px solid #bbb', padding: 4, fontWeight: 'bold' }}>Agresif – Scalp</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>Period 7, level 20/80</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>5-13-9, sangat cepat</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>3,1,1 (super sensitif)</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>MA 10 + MA 20</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>Volume spike</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>Entry cepat di crossing Stoch + MACD + candle momentum</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>M1 – M5</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>M15 – H1</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>H4</td>
              <td style={{ border: '1px solid #bbb', padding: 4 }}>Sangat berisiko, cocok hanya untuk trader berpengalaman dengan eksekusi cepat. Entry cepat di momentum candle. Pastikan arah H1 tidak berlawanan agar tidak terseret reversal.</td>
            </tr>
          </tbody>
        </table>
        </div>
      </Paper>
      <Paper sx={{ p: { xs: 1, sm: 2 }, mb: 2, background: darkMode ? '#23272b' : '#f5f5f5', borderRadius: 2 }}>
        {/* Footnote: Trading open/close info for user */}
        <Box sx={{ mt: 3, mb: 2, p: 2, background: darkMode ? '#23272b' : '#f5f5f5', borderRadius: 2, fontSize: 13, color: darkMode ? '#fff' : '#333' }}>
        <Alert severity="info" sx={{ mb: 2 }}>
          <b>Note:</b> Open trade signals will be sent in both <b>scalp</b> and <b>normal</b> modes when indicator conditions are met.<br/>
          <ul style={{margin: '4px 0 0 18px', fontSize: 13}}>
            <li><b>Normal mode:</b> Example: RSI &lt; 40 and MACD &lt; 0 for sell, or RSI &gt; 60 and MACD &gt; 0 for buy.</li>
            <li><b>Scalp mode:</b> Example: Stochastic K &gt; 80 for sell, or Stochastic K &lt; 20 for buy, with fast signal changes.</li>
          </ul>
          The actual logic may be adjusted in the backend simulation engine.
        </Alert>
        </Box>
      </Paper>
      </Box>
    </ThemeProvider>
  );
}
