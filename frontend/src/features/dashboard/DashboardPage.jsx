import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
    Alert,
    Box,
    Button,
    ButtonGroup,
    Chip,
    FormControl,
    Grid,
    InputLabel,
    MenuItem,
    Paper,
    Select,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    TextField,
    Typography,
} from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { getBackendUrl } from "../../config/backend";
import { getJson } from "../../services/api";
import CandlestickChart from "../../CandlestickChart";

function getSignalColor(signal) {
    if (signal === "buy") return "#1b5e20";
    if (signal === "sell") return "#b71c1c";
    return "#424242";
}

function buildTradeSuggestion(signal, price, indicators = {}) {
    const value = Number(price || indicators.last || 0);
    const bid = Number(indicators.bid ?? value ?? 0);
    const ask = Number(indicators.ask ?? value ?? 0);

    if (signal === "buy") {
        return `Bullish bias detected. Prefer buy with confirmation near ${Math.max(value, ask).toFixed(2)} and keep risk tight.`;
    }

    if (signal === "sell") {
        return `Bearish bias detected. Prefer sell below ${Math.min(value, bid).toFixed(2)} unless market structure flips.`;
    }

    return `Neutral / waiting market. Avoid chasing entries; wait for a clean break or reversal confirmation.`;
}

export default function DashboardPage() {
    const theme = useTheme();
    const isDark = theme.palette.mode === "dark";
    const pageBackground = isDark
        ? "radial-gradient(circle at top left, rgba(46, 120, 255, 0.22), transparent 30%), radial-gradient(circle at top right, rgba(38, 208, 168, 0.18), transparent 28%), #07111d"
        : "radial-gradient(circle at top left, rgba(96, 165, 250, 0.18), transparent 30%), radial-gradient(circle at top right, rgba(16, 185, 129, 0.14), transparent 28%), #f8fafc";
    const panelBackground = isDark
        ? "linear-gradient(180deg, rgba(15,23,42,0.94), rgba(15,23,42,0.98))"
        : "linear-gradient(180deg, rgba(255,255,255,0.97), rgba(248,250,252,0.96))";
    const cardSurface = isDark ? "rgba(15,23,42,0.85)" : "rgba(255,255,255,0.92)";
    const cardBorder = isDark ? "rgba(148,163,184,0.16)" : "rgba(148,163,184,0.24)";
    const textPrimary = isDark ? "#e6edf7" : "#0f172a";
    const textSecondary = isDark ? "#cbd5e1" : "#475569";
    const inputBg = isDark ? "rgba(15,23,42,0.8)" : "rgba(255,255,255,0.92)";
    const [summary, setSummary] = useState(null);
    const [accountState, setAccountState] = useState({
        balance: 0,
        lot: 0.01,
        auto_trade_enabled: false,
        keep_terminal_alive: true,
        enable_real_trade: false,
    });
    const [positions, setPositions] = useState([]);
    const [engine, setEngine] = useState("mt5");
    const [tradeMode, setTradeMode] = useState("scalp");
    const [symbol, setSymbol] = useState("XAUUSD");
    const [tf, setTf] = useState("M1");
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [marketSignal, setMarketSignal] = useState({ signal: "wait", indicators: {}, cached: false });
    const [ohlcv, setOhlcv] = useState([]);
    const [marketPrice, setMarketPrice] = useState(0);

    const signal = useMemo(() => {
        if (marketSignal?.signal) return String(marketSignal.signal).toLowerCase();
        if (!positions.length) return "wait";
        const last = positions[0];
        const type = String(last?.type || "").toUpperCase();
        if (type === "BUY") return "buy";
        if (type === "SELL") return "sell";
        return "wait";
    }, [marketSignal, positions]);

    const tradeSuggestion = useMemo(
        () => buildTradeSuggestion(signal, marketPrice, marketSignal?.indicators || {}),
        [signal, marketPrice, marketSignal],
    );

    const loadDashboard = useCallback(async () => {
        try {
            setLoading(true);
            const [summaryData, accountData, positionsData] = await Promise.all([
                getJson(`${getBackendUrl("mt5", "http")}/dashboard/summary`),
                getJson(`${getBackendUrl("mt5", "http")}/account/state`),
                getJson(`${getBackendUrl("mt5", "http")}/trade/open_positions`),
            ]);

            setSummary(summaryData ?? null);
            setAccountState(accountData ?? { balance: 0, lot: 0.01, auto_trade_enabled: false, keep_terminal_alive: true, enable_real_trade: false });
            setPositions(Array.isArray(positionsData) ? positionsData : []);
            setError("");
        } catch (err) {
            setError(err.message || "Failed to load dashboard summary");
        } finally {
            setLoading(false);
        }
    }, []);

    const loadMarketData = useCallback(async () => {
        try {
            const [signalData, ohlcvData] = await Promise.all([
                getJson(`${getBackendUrl("mt5", "http")}/signal?symbol=${encodeURIComponent(symbol)}&mode=real`),
                getJson(`${getBackendUrl("mt5", "http")}/ohlcv?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(tf)}&bars=60`),
            ]);

            setMarketSignal(signalData ?? { signal: "wait", indicators: {}, cached: false });
            const nextOhlcv = Array.isArray(ohlcvData) ? ohlcvData : [];
            setOhlcv(nextOhlcv);

            const latest = nextOhlcv.length ? nextOhlcv[nextOhlcv.length - 1] : null;
            const nextPrice = Number(latest?.close ?? signalData?.indicators?.[tf]?.sma ?? signalData?.simulator?.last_price ?? 0);
            setMarketPrice(Number.isFinite(nextPrice) ? nextPrice : 0);
        } catch (err) {
            setMarketSignal({ signal: "wait", indicators: {}, cached: false, error: err.message || "Market data unavailable" });
            setOhlcv([]);
            setMarketPrice(0);
        }
    }, [symbol, tf]);

    useEffect(() => {
        loadDashboard();
        loadMarketData();
    }, [loadDashboard, loadMarketData]);

    const brokers = summary?.brokers || [];
    const onlineBrokers = brokers.filter((broker) => broker.available).length;
    const totalFloatingPnl = positions.reduce((sum, trade) => sum + Number(trade?.floating_pnl || 0), 0);

    return (
        <Box
            sx={{
                p: { xs: 1.5, sm: 2.5 },
                maxWidth: 1280,
                mx: "auto",
                width: "100%",
                minHeight: "100vh",
                background: pageBackground,
                color: textPrimary,
            }}
        >
            <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 3, gap: 2, flexWrap: "wrap" }}>
                <Box>
                    <Typography variant="overline" sx={{ color: isDark ? "#7dd3fc" : "#2563eb", letterSpacing: 2, fontWeight: 700 }}>
                        TRADING DESK
                    </Typography>
                    <Typography variant="h4" sx={{ fontWeight: 800, letterSpacing: 0.5, color: textPrimary }}>
                        Signal Dashboard
                    </Typography>
                </Box>
                <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
                    <FormControl size="small" sx={{ minWidth: 120, '& .MuiInputBase-root': { bgcolor: inputBg, color: textPrimary, borderRadius: 2 } }}>
                        <InputLabel id="engine-label" sx={{ color: isDark ? '#bfdbfe' : '#2563eb' }}>Engine</InputLabel>
                        <Select labelId="engine-label" value={engine} label="Engine" onChange={(e) => setEngine(e.target.value)}>
                            <MenuItem value="mt5">MT5 (Live)</MenuItem>
                            <MenuItem value="sim">Simulation</MenuItem>
                        </Select>
                    </FormControl>
                    <FormControl size="small" sx={{ minWidth: 120, '& .MuiInputBase-root': { bgcolor: inputBg, color: textPrimary, borderRadius: 2 } }}>
                        <InputLabel id="trade-mode-label" sx={{ color: isDark ? '#bfdbfe' : '#2563eb' }}>Mode</InputLabel>
                        <Select labelId="trade-mode-label" value={tradeMode} label="Mode" onChange={(e) => setTradeMode(e.target.value)}>
                            <MenuItem value="normal">Normal</MenuItem>
                            <MenuItem value="scalp">Scalp</MenuItem>
                        </Select>
                    </FormControl>
                </Box>
            </Box>

            {error && <Alert severity="error" sx={{ mb: 2, background: "rgba(127,29,29,0.5)", color: "#fecaca", border: "1px solid rgba(248,113,113,0.4)" }}>{error}</Alert>}

            <Grid container spacing={2.2} sx={{ mb: 2.5 }}>
                {[
                    { label: "Total Balance", value: `$${Number(accountState.balance || 0).toFixed(2)}`, tone: "primary" },
                    { label: "Open Positions", value: String(positions.length), tone: "warning" },
                    { label: "Active Brokers", value: String(onlineBrokers), tone: "success" },
                    { label: "Signal", value: signal.toUpperCase(), tone: signal === "buy" ? "success" : signal === "sell" ? "error" : "default" },
                ].map((card) => (
                    <Grid item xs={12} sm={6} md={3} key={card.label}>
                        <Paper
                            sx={{
                                p: 2,
                                borderRadius: 3,
                                border: `1px solid ${cardBorder}`,
                                background: `linear-gradient(135deg, ${cardSurface}, ${isDark ? 'rgba(30,41,59,0.92)' : 'rgba(248,250,252,0.98)'})`,
                                boxShadow: isDark ? '0 12px 30px rgba(2, 6, 23, 0.35)' : '0 12px 30px rgba(15, 23, 42, 0.08)',
                            }}
                        >
                            <Typography variant="caption" sx={{ display: "block", mb: 1.2, color: isDark ? "#93c5fd" : "#2563eb", letterSpacing: 1.2 }}>{card.label}</Typography>
                            <Typography variant="h5" sx={{ fontWeight: 800, color: textPrimary }}>{card.value}</Typography>
                        </Paper>
                    </Grid>
                ))}
            </Grid>

            <Paper
                sx={{
                    p: { xs: 1.2, sm: 2 },
                    mb: 2.5,
                    borderRadius: 3,
                    border: `1px solid ${getSignalColor(signal)}`,
                    background: signal === "buy"
                        ? (isDark ? "rgba(34,197,94,0.12)" : "rgba(34,197,94,0.08)")
                        : signal === "sell"
                            ? (isDark ? "rgba(239,68,68,0.12)" : "rgba(239,68,68,0.08)")
                            : (isDark ? "rgba(148,163,184,0.10)" : "rgba(148,163,184,0.06)"),
                    boxShadow: isDark ? "0 12px 26px rgba(15, 23, 42, 0.35)" : "0 12px 26px rgba(15, 23, 42, 0.08)",
                }}
            >
                <Grid container spacing={2} alignItems="center">
                    <Grid item xs={12} sm={3}>
                        <TextField
                            label="Symbol"
                            value={symbol}
                            onChange={(e) => setSymbol(e.target.value)}
                            size="small"
                            fullWidth
                            sx={{ '& .MuiInputBase-root': { bgcolor: inputBg, color: textPrimary, borderRadius: 2 } }}
                        />
                    </Grid>
                    <Grid item xs={12} sm={4}>
                        <ButtonGroup variant="outlined" color="primary" size="small" sx={{ bgcolor: isDark ? 'rgba(15,23,42,0.65)' : 'rgba(255,255,255,0.7)', borderRadius: 2 }}>
                            {['M1', 'M5', 'M15', 'M30'].map((opt) => (
                                <Button key={opt} variant={tf === opt ? "contained" : "outlined"} onClick={() => setTf(opt)} sx={{ minWidth: 62 }}>
                                    {opt}
                                </Button>
                            ))}
                        </ButtonGroup>
                    </Grid>
                    <Grid item xs={12} sm={3}>
                        <TextField
                            label="Range"
                            value={60}
                            size="small"
                            fullWidth
                            InputProps={{ readOnly: true }}
                            sx={{ '& .MuiInputBase-root': { bgcolor: inputBg, color: textPrimary, borderRadius: 2 } }}
                        />
                    </Grid>
                    <Grid item xs={12} sm={2}>
                        <Button variant="contained" color="primary" fullWidth sx={{ borderRadius: 2, py: 1.1, fontWeight: 700 }}>
                            Update
                        </Button>
                    </Grid>
                </Grid>
            </Paper>

            <Grid container spacing={2.2} sx={{ mb: 2.5 }}>
                <Grid item xs={12} md={5}>
                    <Paper sx={{ p: 2.3, height: "100%", borderRadius: 3, background: panelBackground, border: `1px solid ${cardBorder}`, boxShadow: isDark ? "0 12px 28px rgba(15,23,42,0.28)" : "0 12px 28px rgba(15,23,42,0.08)" }}>
                        <Typography variant="h6" sx={{ mb: 1.5, color: textPrimary, fontWeight: 700 }}>Signal Overview</Typography>
                        <Typography variant="body2" sx={{ mb: 1, color: textSecondary }}>
                            Status: <b style={{ color: getSignalColor(signal) }}>{signal.toUpperCase()}</b>
                        </Typography>
                        <Typography variant="body2" sx={{ mb: 1, color: textSecondary }}>
                            Current Price: <b style={{ color: isDark ? "#7dd3fc" : "#2563eb" }}>$ {Number(marketPrice || 0).toFixed(2)}</b>
                        </Typography>
                        <Typography variant="body2" sx={{ mb: 1, color: textSecondary }}>
                            Market Feed: <b style={{ color: isDark ? "#a7f3d0" : "#059669" }}>{summary?.status || "ready"}</b>
                        </Typography>
                        <Typography variant="body2" sx={{ mb: 1, color: textSecondary }}>
                            Broker Mode: <b style={{ color: accountState.enable_real_trade ? (isDark ? "#4ade80" : "#16a34a") : textSecondary }}>{accountState.enable_real_trade ? "REAL (MT5)" : "SIMULATION"}</b>
                        </Typography>
                        <Typography variant="body2" sx={{ mb: 1, color: textSecondary }}>
                            Floating P/L: <span style={{ color: totalFloatingPnl < 0 ? "#f87171" : (isDark ? "#4ade80" : "#16a34a"), fontWeight: 700 }}>{Number(totalFloatingPnl).toFixed(2)}</span>
                        </Typography>
                        <Typography variant="body2" sx={{ mt: 2, color: isDark ? "#dbeafe" : "#1e3a8a", lineHeight: 1.6 }}>
                            <b>Trade suggestion:</b> {tradeSuggestion}
                        </Typography>
                        <Box sx={{ mt: 2, display: "flex", gap: 1, flexWrap: "wrap" }}>
                            {brokers.length === 0 ? (
                                <Chip label="No brokers" sx={{ bgcolor: isDark ? "rgba(148,163,184,0.16)" : "rgba(148,163,184,0.12)", color: textPrimary }} />
                            ) : (
                                brokers.map((broker) => (
                                    <Chip
                                        key={broker.name}
                                        label={`${broker.name} ${broker.available ? "online" : "offline"}`}
                                        color={broker.available ? "success" : "default"}
                                        variant={broker.available ? "filled" : "outlined"}
                                        sx={{
                                            mb: 1,
                                            bgcolor: broker.available ? "rgba(34,197,94,0.16)" : isDark ? "rgba(148,163,184,0.08)" : "rgba(148,163,184,0.10)",
                                            color: broker.available ? (isDark ? "#dcfce7" : "#166534") : textSecondary,
                                            border: broker.available ? "1px solid rgba(74,222,128,0.4)" : `1px solid ${cardBorder}`,
                                        }}
                                    />
                                ))
                            )}
                        </Box>
                    </Paper>
                </Grid>

                <Grid item xs={12} md={7}>
                    <Paper sx={{ p: 2.3, height: "100%", borderRadius: 3, background: panelBackground, border: `1px solid ${cardBorder}`, boxShadow: isDark ? "0 12px 28px rgba(15,23,42,0.28)" : "0 12px 28px rgba(15,23,42,0.08)" }}>
                        <Typography variant="h6" sx={{ mb: 1.5, color: textPrimary, fontWeight: 700 }}>Trading Panel</Typography>
                        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1.5, alignItems: "center", mb: 2 }}>
                            <Button variant="contained" color="success" size="small" sx={{ borderRadius: 2, fontWeight: 700 }}>Buy</Button>
                            <Button variant="contained" color="error" size="small" sx={{ borderRadius: 2, fontWeight: 700 }}>Sell</Button>
                            <Button variant="outlined" size="small" sx={{ borderRadius: 2, color: textPrimary, borderColor: cardBorder }}>Refresh</Button>
                        </Box>
                        <TableContainer>
                            <Table size="small">
                                <TableHead>
                                    <TableRow>
                                        <TableCell sx={{ color: isDark ? "#bfdbfe" : "#1d4ed8", borderColor: cardBorder }}>Symbol</TableCell>
                                        <TableCell sx={{ color: isDark ? "#bfdbfe" : "#1d4ed8", borderColor: cardBorder }}>Lot</TableCell>
                                        <TableCell sx={{ color: isDark ? "#bfdbfe" : "#1d4ed8", borderColor: cardBorder }}>Type</TableCell>
                                        <TableCell sx={{ color: isDark ? "#bfdbfe" : "#1d4ed8", borderColor: cardBorder }}>Broker</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {positions.length === 0 ? (
                                        <TableRow>
                                            <TableCell colSpan={4} sx={{ color: textSecondary, borderColor: cardBorder }}>
                                                <Typography variant="caption" sx={{ color: textSecondary }}>Tidak ada trade aktif.</Typography>
                                            </TableCell>
                                        </TableRow>
                                    ) : (
                                        positions.slice(0, 4).map((trade, index) => (
                                            <TableRow key={`${trade.trade_id || trade.ticket || index}`}>
                                                <TableCell sx={{ color: textPrimary, borderColor: cardBorder }}>{trade.symbol || "-"}</TableCell>
                                                <TableCell sx={{ color: textPrimary, borderColor: cardBorder }}>{trade.lot ?? "-"}</TableCell>
                                                <TableCell sx={{ color: textPrimary, borderColor: cardBorder }}>{String(trade.type || "-").toUpperCase()}</TableCell>
                                                <TableCell sx={{ color: textPrimary, borderColor: cardBorder }}>{trade.broker_name || "-"}</TableCell>
                                            </TableRow>
                                        ))
                                    )}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </Paper>
                </Grid>
            </Grid>

            <Paper sx={{ p: 2.2, mb: 2.5, borderRadius: 3, background: panelBackground, border: `1px solid ${cardBorder}`, boxShadow: isDark ? "0 12px 28px rgba(15,23,42,0.28)" : "0 12px 28px rgba(15,23,42,0.08)" }}>
                <Typography variant="h6" sx={{ mb: 1.5, color: textPrimary, fontWeight: 700 }}>Price Chart</Typography>
                {ohlcv.length > 0 ? (
                    <CandlestickChart ohlcv={ohlcv} jumlahBar={60} spread={0.0002} />
                ) : (
                    <Typography variant="body2" color="text.secondary">Chart not available. Waiting for OHLCV data.</Typography>
                )}
            </Paper>

            <Paper sx={{ p: 2.2, borderRadius: 3, background: panelBackground, border: `1px solid ${cardBorder}`, boxShadow: isDark ? "0 12px 28px rgba(15,23,42,0.28)" : "0 12px 28px rgba(15,23,42,0.08)" }}>
                <Typography variant="h6" sx={{ mb: 1.5, color: textPrimary, fontWeight: 700 }}>Status Service</Typography>
                <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
                    <Chip label={`Status: ${summary?.status || "ready"}`} color={summary?.status === "ready" ? "success" : "default"} sx={{ bgcolor: summary?.status === "ready" ? "rgba(34,197,94,0.18)" : "rgba(148,163,184,0.1)", color: textPrimary }} />
                    <Chip label={`Accounting: ${summary?.accounting || "service_ready"}`} color="primary" variant="outlined" sx={{ color: isDark ? "#bfdbfe" : "#1d4ed8", borderColor: isDark ? "rgba(96,165,250,0.45)" : "rgba(37,99,235,0.35)" }} />
                    <Chip label={`Auto Trade: ${accountState.auto_trade_enabled ? "enabled" : "disabled"}`} color={accountState.auto_trade_enabled ? "success" : "default"} sx={{ bgcolor: accountState.auto_trade_enabled ? "rgba(34,197,94,0.18)" : "rgba(148,163,184,0.1)", color: textPrimary }} />
                    <Chip label={`Terminal: ${accountState.keep_terminal_alive ? "alive" : "sleep"}`} color={accountState.keep_terminal_alive ? "success" : "warning"} sx={{ bgcolor: accountState.keep_terminal_alive ? "rgba(34,197,94,0.18)" : "rgba(234,179,8,0.18)", color: textPrimary }} />
                </Box>
            </Paper>
        </Box>
    );
}
