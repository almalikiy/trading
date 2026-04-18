// =============================================
// Penjelasan singkat keyword, API, dan library (App.jsx):
//
// - React: Library utama untuk membangun UI berbasis komponen.
// - useState, useEffect: React hooks untuk state lokal dan efek samping (otomatis refresh, polling, dsb).
// - MUI (Material UI): Library komponen UI siap pakai (Button, Paper, Grid, Typography, dsb).
// - Chart.js & chartjs-chart-financial: Library charting untuk candlestick/line chart.
// - chartjs-adapter-date-fns: Adapter agar Chart.js bisa menampilkan sumbu waktu dengan format modern.
// - ReconnectingWebSocket: Library JS untuk websocket yang otomatis reconnect (real-time signal).
// - FastAPI: Backend Python (REST API/WebSocket, sumber data utama).
//
// Keyword penting:
// - props: Data yang dikirim dari parent ke child component.
// - state: Data lokal tiap komponen, berubah -> re-render.
// - useEffect: Jalankan kode saat mount/update/unmount.
// - fetch: API JS untuk ambil data dari backend (REST API).
// - map: Fungsi array untuk transformasi data.
//
// Struktur utama file ini:
// - State utama: signal, ohlcv, indicators, chartMode, dsb.
// - fetchOhlcv: Fungsi untuk ambil data harga dari backend.
// - Komponen utama: Chart, Table, Panel indikator, dsb.
// =============================================
// Helper: export object array to CSV
function exportIndicatorsToCSV(indicators) {
  if (!indicators) return;
  const tfs = ['M1','M5','M15','M30'];
  const headers = ['TF','RSI','MACD','MACD Sig','BB Lower','BB Mid','BB Upper','SMA','Stoch K','Stoch D'];
  let csv = headers.join(',') + '\n';
  tfs.forEach(tf => {
    if (indicators[tf]) {
      const row = [
        tf,
        indicators[tf].rsi,
        indicators[tf].macd,
        indicators[tf].macd_signal,
        indicators[tf].bb_lower,
        indicators[tf].bb_mid,
        indicators[tf].bb_upper,
        indicators[tf].sma,
        indicators[tf].stoch_k,
        indicators[tf].stoch_d
      ].map(x => x !== undefined ? x : '').join(',');
      csv += row + '\n';
    }
  });
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'indicators.csv';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}



import CandlestickChart from "./CandlestickChart";
import LineChart from "./LineChart";


import React, { useEffect, useState, useRef } from "react";
import { Box, Typography, Paper, Grid, Button, TextField, Alert, ButtonGroup, Snackbar, Alert as MuiAlert, Select, MenuItem, InputLabel, FormControl, Switch, FormControlLabel, CssBaseline } from "@mui/material";
import { ThemeProvider, createTheme } from '@mui/material/styles';
import ReconnectingWebSocket from "reconnecting-websocket";

const WS_URL = "ws://localhost:8000/ws/signal";

export default function App() {
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
  const [barCount, setBarCount] = useState(240); // jumlah bar/candle chart
  const [darkMode, setDarkMode] = useState(false);

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
    const ws = new ReconnectingWebSocket(WS_URL);
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      console.log("WS Response:", data); // DEBUG: tampilkan respons websocket
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
      setPrevIndicators(indicators); // simpan indikator sebelumnya sebelum update
      setIndicators(data.indicators);
      setSim(data.simulator);
    };
    // Tampilkan snackbar jika sinyal berubah
    return () => ws.close();
  }, []);

  useEffect(() => {
    if (prevSignal && signal && prevSignal !== signal) {
      setSnackbarMsg(`Signal berubah dari ${prevSignal.toUpperCase()} ke ${signal.toUpperCase()}`);
      setSnackbarOpen(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signal]);

  // Auto refresh OHLCV tiap detik
  useEffect(() => {
    let timer;
    let stopped = false;
    const fetchOhlcv = () => {
      fetch(`http://localhost:8000/ohlcv?symbol=${symbol}&timeframe=${tf}&bars=${barCount}`)
        .then((res) => {
          if (!res.ok) throw new Error("Backend not active");
          return res.json();
        })
        .then((data) => {
          console.log("OHLCV Response:", data); // DEBUG: tampilkan respons OHLCV
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
  }, [symbol, tf, barCount]);

  // ...existing code...


  useEffect(() => {
    const ws = new ReconnectingWebSocket(WS_URL);
    ws.onmessage = (e) => {
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
      setPrevIndicators(indicators); // simpan indikator sebelumnya sebelum update
      setIndicators(data.indicators);
      setSim(data.simulator);
    };
    // Tampilkan snackbar jika sinyal berubah
    return () => ws.close();
  }, []);

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
      <Snackbar open={snackbarOpen} autoHideDuration={2500} onClose={() => setSnackbarOpen(false)} anchorOrigin={{vertical:'top',horizontal:'center'}}>
        <MuiAlert onClose={() => setSnackbarOpen(false)} severity={signal === 'buy' ? 'success' : 'info'} sx={{ width: '100%' }}>
          {snackbarMsg}
        </MuiAlert>
      </Snackbar>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
        <Typography variant="h4" gutterBottom>
          Trading Signal Dashboard
        </Typography>
        <FormControlLabel
          control={<Switch checked={darkMode} onChange={() => setDarkMode(v => !v)} color="primary" />}
          label={darkMode ? 'Dark Mode' : 'Light Mode'}
        />
      </Box>
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
              }}>Coba Fetch Ulang</Button>
            </>
          ) : (
            <>
              Data candlestick tidak tersedia.<br />
              <b>Pastikan backend FastAPI berjalan di <code>localhost:8000</code></b>.<br />
              Jalankan: <code>uvicorn app.main:app --reload</code> di folder backend.<br />
              Setelah backend aktif, refresh halaman ini.
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
                <MenuItem value={30}>30 Bar</MenuItem>
                <MenuItem value={60}>60 Bar</MenuItem>
                <MenuItem value={120}>120 Bar</MenuItem>
                <MenuItem value={240}>240 Bar</MenuItem>
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
        <Typography variant="h6" sx={{ fontWeight:'bold', letterSpacing:2 }}>
          Signal: <b style={{ color: signal === "buy" ? "#1b5e20" : "#424242", fontWeight:'bold', fontSize:22 }}>{signal ? signal.toUpperCase() : '-'}</b>
        </Typography>
        <Typography variant="body2">
          Balance: <span style={{color: sim && sim.balance < 0 ? 'red' : undefined}}>${sim && sim.balance !== undefined ? sim.balance.toFixed(2) : '-'}</span> |
          PnL: <span style={{color: sim && sim.pnl < 0 ? 'red' : undefined}}>{sim && sim.pnl !== undefined ? sim.pnl.toFixed(2) : '-'}</span> |
          Open Trade: {sim && sim.open_trade !== undefined ? (sim.open_trade ? "Yes" : "No") : '-'}
        </Typography>
        {/* Ringkasan indikator utama timeframe aktif */}
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
        {/* Info waktu data terakhir */}
        {ohlcv && ohlcv.length > 0 && (
          <Typography variant="caption" sx={{ display: 'block', mt: 1 }}>
            {/* Keterangan waktu: epoch UTC, biasanya waktu server broker GMT+2/GMT+3 */}
            Last data (epoch UTC): {ohlcv[ohlcv.length-1].time} &nbsp;|&nbsp; 
            <span style={{color:'#888'}}>Note: Waktu server broker biasanya GMT+2/GMT+3, epoch ini = UTC</span>
          </Typography>
        )}
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
            <Typography variant="body2" color="text.secondary">Chart tidak tersedia. Menampilkan data OHLCV sebagai tabel.</Typography>
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
            <CandlestickChart ohlcv={ohlcv} />
          ) : (
            <LineChart ohlcv={ohlcv} />
          ))
        )}
      </Paper>
      <Paper sx={{ p: { xs: 1, sm: 2 }, overflowX: 'auto', width: '100%' }}>
        <Typography variant="h6">Indicators (M1, M5, M15, M30)</Typography>
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
      </Box>
    </ThemeProvider>
  );
}
