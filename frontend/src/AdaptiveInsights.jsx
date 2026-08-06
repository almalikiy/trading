import React, { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
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

const API_BASE = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

function formatTradeTime(epochSeconds) {
  if (!epochSeconds) return "-";
  const value = Number(epochSeconds);
  if (!Number.isFinite(value) || value <= 0) return "-";
  return new Date(value * 1000).toLocaleString();
}

function getRecommendationSource(event) {
  const reason = String(event?.reason || "").toLowerCase();
  const decision = String(event?.decision || "").toLowerCase();
  const modelType = String(event?.payload?.adaptive_meta?.model_type || "").toLowerCase();

  if (reason.includes("adaptive_ml_prediction") || modelType === "random_forest" || modelType === "majority") {
    return "ml_adaptive";
  }
  if (reason.startsWith("rule_") || reason.startsWith("condition_") || reason.startsWith("hybrid_")) {
    return "rule_based";
  }
  if (reason.includes("adaptive_best_history") || reason.includes("adaptive_fallback_manual") || decision.startsWith("risk_mode_recommendation:")) {
    return "adaptive_history";
  }
  return "unknown";
}

function sourceChip(source) {
  if (source === "ml_adaptive") return <Chip size="small" color="success" label="ML Adaptive" />;
  if (source === "rule_based") return <Chip size="small" color="warning" label="Rule-based" />;
  if (source === "adaptive_history") return <Chip size="small" color="info" label="Adaptive History" />;
  return <Chip size="small" label="Unknown" />;
}

export default function AdaptiveInsights() {
  const [brokers, setBrokers] = useState([]);
  const [events, setEvents] = useState([]);
  const [stats, setStats] = useState(null);
  const [loadingEvents, setLoadingEvents] = useState(true);
  const [loadingStats, setLoadingStats] = useState(true);
  const [closeDataset, setCloseDataset] = useState([]);
  const [loadingCloseDataset, setLoadingCloseDataset] = useState(true);
  const [error, setError] = useState("");

  const [brokerId, setBrokerId] = useState("");
  const [accountId, setAccountId] = useState("");
  const [sinceMinutes, setSinceMinutes] = useState(180);
  const [windowDays, setWindowDays] = useState(30);

  const refreshBrokers = async () => {
    try {
      const res = await fetch(`${API_BASE}/brokers?include_inactive=true`);
      const data = await res.json().catch(() => []);
      if (!res.ok) throw new Error("Gagal mengambil daftar broker.");
      setBrokers(Array.isArray(data) ? data : []);
    } catch {
      setBrokers([]);
    }
  };

  const refreshEvents = async () => {
    setLoadingEvents(true);
    try {
      const params = new URLSearchParams();
      params.set("limit", "300");
      params.set("event_type", "analysis");
      if (brokerId) params.set("broker_id", String(brokerId));
      if (accountId) params.set("account_id", String(accountId));
      const sinceEpoch = Math.floor(Date.now() / 1000) - (Math.max(1, Number(sinceMinutes || 180)) * 60);
      params.set("since", String(sinceEpoch));

      const res = await fetch(`${API_BASE}/account/auto_trade_events?${params.toString()}`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.status === "error") {
        throw new Error(data.message || "Gagal mengambil adaptive events.");
      }

      const rows = Array.isArray(data.events) ? data.events : [];
      setEvents(rows.filter((row) => String(row?.decision || "").toLowerCase().startsWith("risk_mode_recommendation:")));
      setError("");
    } catch (err) {
      setEvents([]);
      setError(String(err.message || "Gagal mengambil adaptive events."));
    } finally {
      setLoadingEvents(false);
    }
  };

  const refreshStats = async () => {
    setLoadingStats(true);
    try {
      const params = new URLSearchParams();
      params.set("window_days", String(Math.max(1, Number(windowDays || 30))));
      if (brokerId) params.set("broker_id", String(brokerId));
      if (accountId) params.set("account_id", String(accountId));

      const res = await fetch(`${API_BASE}/account/auto_trade_stats?${params.toString()}`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.status === "error") {
        throw new Error(data.message || "Gagal mengambil statistik adaptive.");
      }
      setStats(data.stats || null);
      setError("");
    } catch (err) {
      setStats(null);
      setError(String(err.message || "Gagal mengambil statistik adaptive."));
    } finally {
      setLoadingStats(false);
    }
  };

  const refreshCloseDataset = async () => {
    setLoadingCloseDataset(true);
    try {
      const params = new URLSearchParams();
      params.set("limit", "120");
      if (brokerId) params.set("broker_id", String(brokerId));
      if (accountId) params.set("account_id", String(accountId));
      const res = await fetch(`${API_BASE}/account/auto_trade_close_decision_dataset?${params.toString()}`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.status === "error") {
        throw new Error(data.message || "Gagal mengambil close-decision dataset.");
      }
      setCloseDataset(Array.isArray(data.dataset) ? data.dataset : []);
      setError("");
    } catch (err) {
      setCloseDataset([]);
      setError(String(err.message || "Gagal mengambil close-decision dataset."));
    } finally {
      setLoadingCloseDataset(false);
    }
  };

  useEffect(() => {
    refreshBrokers();
  }, []);

  useEffect(() => {
    refreshEvents();
    refreshStats();
    refreshCloseDataset();
  }, [brokerId, accountId, sinceMinutes, windowDays]);

  useEffect(() => {
    const timer = setInterval(() => {
      refreshEvents();
      refreshStats();
      refreshCloseDataset();
    }, 10000);
    return () => clearInterval(timer);
  }, [brokerId, accountId, sinceMinutes, windowDays]);

  const sourceSummary = useMemo(() => {
    const summary = { ml_adaptive: 0, rule_based: 0, adaptive_history: 0, unknown: 0 };
    events.forEach((event) => {
      const key = getRecommendationSource(event);
      summary[key] = (summary[key] || 0) + 1;
    });
    return summary;
  }, [events]);

  return (
    <Box sx={{ p: { xs: 1.5, sm: 2 }, maxWidth: 1400, mx: "auto", width: "100%" }}>
      <Typography variant="h5" sx={{ mb: 0.5 }}>Adaptive & ML Insights</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Halaman ini khusus untuk memonitor kualitas rekomendasi risk mode, sumber keputusan adaptive, dan performa hasil trading.
      </Typography>

      {error ? <Alert severity="warning" sx={{ mb: 2 }}>{error}</Alert> : null}

      <Paper sx={{ p: { xs: 1.5, sm: 2 }, mb: 2 }}>
        <Grid container spacing={1.5} alignItems="center">
          <Grid item xs={12} md={3}>
            <FormControl size="small" fullWidth>
              <InputLabel id="adaptive-broker-filter">Broker Filter</InputLabel>
              <Select
                labelId="adaptive-broker-filter"
                label="Broker Filter"
                value={brokerId}
                onChange={(e) => setBrokerId(e.target.value)}
              >
                <MenuItem value="">All Brokers</MenuItem>
                {brokers.map((b) => (
                  <MenuItem key={b.id} value={String(b.id)}>{b.name}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={3}>
            <TextField
              fullWidth
              size="small"
              label="Account Filter"
              value={accountId}
              onChange={(e) => setAccountId(e.target.value.replace(/[^0-9]/g, ""))}
              placeholder="contoh: 123456"
            />
          </Grid>
          <Grid item xs={12} md={2}>
            <TextField
              fullWidth
              size="small"
              label="Since (minutes)"
              type="number"
              value={sinceMinutes}
              onChange={(e) => setSinceMinutes(Math.max(1, Number(e.target.value || 180)))}
              inputProps={{ min: 1, max: 10080, step: 1 }}
            />
          </Grid>
          <Grid item xs={12} md={2}>
            <TextField
              fullWidth
              size="small"
              label="Stats Window (days)"
              type="number"
              value={windowDays}
              onChange={(e) => setWindowDays(Math.max(1, Number(e.target.value || 30)))}
              inputProps={{ min: 1, max: 3650, step: 1 }}
            />
          </Grid>
          <Grid item xs={12} md={2}>
            <Button
              fullWidth
              variant="outlined"
              onClick={() => {
                setBrokerId("");
                setAccountId("");
                setSinceMinutes(180);
                setWindowDays(30);
              }}
            >
              Reset Filters
            </Button>
          </Grid>
        </Grid>
      </Paper>

      <Grid container spacing={1.5} sx={{ mb: 2 }}>
        <Grid item xs={6} md={2.4}>
          <Paper sx={{ p: 1.5 }}>
            <Typography variant="caption" color="text.secondary">Closed Trades</Typography>
            <Typography variant="h6">{loadingStats ? "-" : Number(stats?.closed_trades || 0)}</Typography>
          </Paper>
        </Grid>
        <Grid item xs={6} md={2.4}>
          <Paper sx={{ p: 1.5 }}>
            <Typography variant="caption" color="text.secondary">Winrate</Typography>
            <Typography variant="h6">{loadingStats ? "-" : `${Number(stats?.winrate || 0).toFixed(1)}%`}</Typography>
          </Paper>
        </Grid>
        <Grid item xs={6} md={2.4}>
          <Paper sx={{ p: 1.5 }}>
            <Typography variant="caption" color="text.secondary">Net Profit</Typography>
            <Typography variant="h6" color={Number(stats?.net_profit || 0) >= 0 ? "success.main" : "error.main"}>
              {loadingStats ? "-" : Number(stats?.net_profit || 0).toFixed(2)}
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={6} md={2.4}>
          <Paper sx={{ p: 1.5 }}>
            <Typography variant="caption" color="text.secondary">Average RR</Typography>
            <Typography variant="h6">{loadingStats ? "-" : Number(stats?.average_rr || 0).toFixed(2)}</Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} md={2.4}>
          <Paper sx={{ p: 1.5 }}>
            <Typography variant="caption" color="text.secondary">Avg Signal Score</Typography>
            <Typography variant="h6">
              {loadingStats ? "-" : stats?.average_signal_score == null ? "-" : Number(stats.average_signal_score).toFixed(3)}
            </Typography>
          </Paper>
        </Grid>
      </Grid>

      <Grid container spacing={1.5} sx={{ mb: 2 }}>
        <Grid item xs={6} md={3}>
          <Paper sx={{ p: 1.5 }}>
            <Typography variant="caption" color="text.secondary">Target Hit</Typography>
            <Typography variant="h6">{loadingStats ? "-" : Number(stats?.target_outcome?.target_hit || 0)}</Typography>
          </Paper>
        </Grid>
        <Grid item xs={6} md={3}>
          <Paper sx={{ p: 1.5 }}>
            <Typography variant="caption" color="text.secondary">Missed Target</Typography>
            <Typography variant="h6">{loadingStats ? "-" : Number(stats?.target_outcome?.missed_target || 0)}</Typography>
          </Paper>
        </Grid>
        <Grid item xs={6} md={3}>
          <Paper sx={{ p: 1.5 }}>
            <Typography variant="caption" color="text.secondary">Force Close After Crossed</Typography>
            <Typography variant="h6" color="warning.main">{loadingStats ? "-" : Number(stats?.target_outcome?.force_close_after_target_crossed || 0)}</Typography>
          </Paper>
        </Grid>
        <Grid item xs={6} md={3}>
          <Paper sx={{ p: 1.5 }}>
            <Typography variant="caption" color="text.secondary">Target Hit Rate</Typography>
            <Typography variant="h6">{loadingStats ? "-" : `${Number(stats?.target_outcome?.target_hit_rate || 0).toFixed(1)}%`}</Typography>
          </Paper>
        </Grid>
      </Grid>

      <Paper sx={{ p: { xs: 1.5, sm: 2 }, mb: 2 }}>
        <Typography variant="subtitle1" sx={{ mb: 1 }}>Adaptive Target Learning Metrics</Typography>
        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
          <Chip
            color="info"
            label={`Avg Target Factor: ${stats?.target_outcome?.average_target_factor == null ? "-" : Number(stats.target_outcome.average_target_factor).toFixed(3)}`}
          />
          <Chip
            color="warning"
            label={`Avg Overshoot Before Close: ${stats?.target_outcome?.average_overshoot_before_close == null ? "-" : Number(stats.target_outcome.average_overshoot_before_close).toFixed(3)}`}
          />
          <Chip
            variant="outlined"
            label={`Evaluated Trades: ${Number(stats?.target_outcome?.evaluated || 0)}`}
          />
        </Box>
      </Paper>

      <Paper sx={{ p: { xs: 1.5, sm: 2 }, mb: 2, overflowX: "auto" }}>
        <Typography variant="subtitle1" sx={{ mb: 1 }}>Anomaly Audit: Target Crossed But Not TP Close</Typography>
        {loadingStats ? (
          <Box sx={{ py: 2, display: "flex", justifyContent: "center" }}><CircularProgress size={20} /></Box>
        ) : !Array.isArray(stats?.anomaly_audit?.rows) || stats.anomaly_audit.rows.length === 0 ? (
          <Typography variant="body2" color="text.secondary">Belum ada anomaly target-crossed pada periode ini.</Typography>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Close Time</TableCell>
                  <TableCell>Trade</TableCell>
                  <TableCell>Reason</TableCell>
                  <TableCell>Target Crossed</TableCell>
                  <TableCell>Close Delay</TableCell>
                  <TableCell>Overshoot</TableCell>
                  <TableCell>Profit</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {stats.anomaly_audit.rows.map((row, index) => (
                  <TableRow key={`${row.trade_id || "trade"}-${index}`}>
                    <TableCell>{formatTradeTime(row.exitTime)}</TableCell>
                    <TableCell>{`${row.symbol || "-"} ${row.type || "-"}`}</TableCell>
                    <TableCell>{row.reason || "-"}</TableCell>
                    <TableCell>{formatTradeTime(row.target_first_crossed_at)}</TableCell>
                    <TableCell>{row.time_to_target_cross_sec == null || row.time_to_close_sec == null ? "-" : `${Math.max(0, Number(row.time_to_close_sec || 0) - Number(row.time_to_target_cross_sec || 0))}s`}</TableCell>
                    <TableCell>{row.overshoot_before_close == null ? "-" : Number(row.overshoot_before_close).toFixed(3)}</TableCell>
                    <TableCell sx={{ color: Number(row.profit || 0) >= 0 ? "success.main" : "error.main" }}>{Number(row.profit || 0).toFixed(2)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

      <Paper sx={{ p: { xs: 1.5, sm: 2 }, mb: 2, overflowX: "auto" }}>
        <Typography variant="subtitle1" sx={{ mb: 1 }}>Close-Decision Dataset Preview</Typography>
        {loadingCloseDataset ? (
          <Box sx={{ py: 2, display: "flex", justifyContent: "center" }}><CircularProgress size={20} /></Box>
        ) : closeDataset.length === 0 ? (
          <Typography variant="body2" color="text.secondary">Belum ada data close-decision yang bisa dipreview.</Typography>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Trade</TableCell>
                  <TableCell>Close Family</TableCell>
                  <TableCell>MFE</TableCell>
                  <TableCell>MAE</TableCell>
                  <TableCell>Time To Close</TableCell>
                  <TableCell>Time To Target</TableCell>
                  <TableCell>Target Crossed</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {closeDataset.slice(0, 20).map((row, index) => (
                  <TableRow key={`${row.trade_id || "trade"}-${index}`}>
                    <TableCell>{`${row.symbol || "-"} / ${row.risk_mode || "-"}`}</TableCell>
                    <TableCell>{row.result?.close_reason_family || "-"}</TableCell>
                    <TableCell>{Number(row.result?.mfe_price_distance || 0).toFixed(3)}</TableCell>
                    <TableCell>{Number(row.result?.mae_price_distance || 0).toFixed(3)}</TableCell>
                    <TableCell>{`${Number(row.result?.time_to_close_sec || 0)}s`}</TableCell>
                    <TableCell>{row.result?.time_to_target_cross_sec ? `${Number(row.result.time_to_target_cross_sec)}s` : "-"}</TableCell>
                    <TableCell>{row.result?.target_crossed_before_close ? "Yes" : "No"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

      <Paper sx={{ p: { xs: 1.5, sm: 2 }, mb: 2 }}>
        <Typography variant="subtitle1" sx={{ mb: 1 }}>Recommendation Source Mix</Typography>
        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
          <Chip color="success" label={`ML Adaptive: ${sourceSummary.ml_adaptive}`} />
          <Chip color="warning" label={`Rule-based: ${sourceSummary.rule_based}`} />
          <Chip color="info" label={`Adaptive History: ${sourceSummary.adaptive_history}`} />
          <Chip label={`Unknown: ${sourceSummary.unknown}`} />
          <Chip variant="outlined" label={`Total Rows: ${events.length}`} />
        </Box>
      </Paper>

      <Paper sx={{ p: { xs: 1.5, sm: 2 }, mb: 2, overflowX: "auto" }}>
        <Typography variant="subtitle1" sx={{ mb: 1 }}>Risk Mode Performance</Typography>
        {loadingStats ? (
          <Box sx={{ py: 2, display: "flex", justifyContent: "center" }}><CircularProgress size={20} /></Box>
        ) : !Array.isArray(stats?.risk_mode_performance) || stats.risk_mode_performance.length === 0 ? (
          <Typography variant="body2" color="text.secondary">Belum ada data performa risk mode pada periode ini.</Typography>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Risk Mode</TableCell>
                  <TableCell>Trades</TableCell>
                  <TableCell>Winrate</TableCell>
                  <TableCell>Avg RR</TableCell>
                  <TableCell>Profit</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {stats.risk_mode_performance.map((row, idx) => (
                  <TableRow key={`${row.mode || "unknown"}-${idx}`}>
                    <TableCell>{row.mode || "-"}</TableCell>
                    <TableCell>{Number(row.count || 0)}</TableCell>
                    <TableCell>{Number(row.winrate || 0).toFixed(1)}%</TableCell>
                    <TableCell>{Number(row.average_rr || 0).toFixed(2)}</TableCell>
                    <TableCell sx={{ color: Number(row.profit || 0) >= 0 ? "success.main" : "error.main" }}>
                      {Number(row.profit || 0).toFixed(2)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

      <Paper sx={{ p: { xs: 1.5, sm: 2 }, overflowX: "auto" }}>
        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 1 }}>
          <Typography variant="subtitle1">Adaptive Risk Recommendations</Typography>
          <Button variant="outlined" size="small" onClick={refreshEvents}>Refresh</Button>
        </Box>
        {loadingEvents ? (
          <Box sx={{ py: 2, display: "flex", justifyContent: "center" }}><CircularProgress size={20} /></Box>
        ) : events.length === 0 ? (
          <Typography variant="body2" color="text.secondary">Belum ada event rekomendasi risk mode.</Typography>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Time</TableCell>
                  <TableCell>Symbol</TableCell>
                  <TableCell>Decision</TableCell>
                  <TableCell>Source</TableCell>
                  <TableCell>Reason</TableCell>
                  <TableCell>Risk Mode</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {events.map((event, index) => {
                  const source = getRecommendationSource(event);
                  return (
                    <TableRow key={`${event.timestamp || 0}-${event.trade_id || "no-trade"}-${index}`}>
                      <TableCell>{formatTradeTime(event.timestamp)}</TableCell>
                      <TableCell>{event.symbol || "-"}</TableCell>
                      <TableCell>{event.decision || "-"}</TableCell>
                      <TableCell>{sourceChip(source)}</TableCell>
                      <TableCell>{event.reason || "-"}</TableCell>
                      <TableCell>{event.risk_mode || "-"}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>
    </Box>
  );
}
