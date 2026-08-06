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
const DEFAULT_MULTI_TFS = ["M1", "M5", "M15", "M30"];


function parseMultiTimeframes(value) {
  const source = Array.isArray(value)
    ? value
    : String(value || "")
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
  const allowed = new Set(["M1", "M5", "M15", "M30", "H1", "H4", "D1"]);
  const unique = [];
  for (const item of source) {
    const tf = String(item || "").trim().toUpperCase();
    if (!allowed.has(tf) || unique.includes(tf)) continue;
    unique.push(tf);
  }
  return unique.length >= 2 ? unique : [...DEFAULT_MULTI_TFS];
}


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
  const [autoTradeRiskMode, setAutoTradeRiskMode] = useState("fixed_lot");
  const [autoTradeRiskSelectorStrategy, setAutoTradeRiskSelectorStrategy] = useState("manual");
  const [autoTradeRiskAtrThreshold, setAutoTradeRiskAtrThreshold] = useState(12);
  const [autoTradeRiskBalanceFixedThreshold, setAutoTradeRiskBalanceFixedThreshold] = useState(500);
  const [autoTradeRiskConfidenceThreshold, setAutoTradeRiskConfidenceThreshold] = useState(0.7);
  const [autoTradeRiskSpreadFixedThreshold, setAutoTradeRiskSpreadFixedThreshold] = useState(120);
  const [autoTradeRiskSpreadLowThreshold, setAutoTradeRiskSpreadLowThreshold] = useState(60);
  const [autoTradeRiskHybridAddonRrThreshold, setAutoTradeRiskHybridAddonRrThreshold] = useState(2.0);
  const [autoTradeRiskHybridEntryMode, setAutoTradeRiskHybridEntryMode] = useState("risk_percent");
  const [autoTradeRiskHybridAddonMode, setAutoTradeRiskHybridAddonMode] = useState("balance_scaled");
  const [autoTradeRiskAdaptiveWindowDays, setAutoTradeRiskAdaptiveWindowDays] = useState(90);
  const [autoTradeRiskAdaptiveMinTrades, setAutoTradeRiskAdaptiveMinTrades] = useState(12);
  const [autoTradeHedgeEnabled, setAutoTradeHedgeEnabled] = useState(true);
  const [autoTradeHedgeThreshold, setAutoTradeHedgeThreshold] = useState(-0.05);
  const [autoTradeHedgeSlots, setAutoTradeHedgeSlots] = useState(2);
  const [autoTradeRiskPercent, setAutoTradeRiskPercent] = useState(1);
  const [autoTradeUseAccountBalance, setAutoTradeUseAccountBalance] = useState(true);
  const [autoTradeUseAvailableMargin, setAutoTradeUseAvailableMargin] = useState(true);
  const [autoTradeMinFreeMarginPct, setAutoTradeMinFreeMarginPct] = useState(30);
  const [autoTradeMaxMarginUsagePct, setAutoTradeMaxMarginUsagePct] = useState(70);
  const [autoTradeMaxSpreadPoints, setAutoTradeMaxSpreadPoints] = useState(120);
  const [autoTradeMinSignalScore, setAutoTradeMinSignalScore] = useState(0.55);
  const [autoTradeAllowSell, setAutoTradeAllowSell] = useState(true);
  const [autoTradeCooldownSec, setAutoTradeCooldownSec] = useState(30);
  const [autoTradeSessionStartHour, setAutoTradeSessionStartHour] = useState(0);
  const [autoTradeSessionEndHour, setAutoTradeSessionEndHour] = useState(24);
  const [autoTradeUseAtrTpSl, setAutoTradeUseAtrTpSl] = useState(true);
  const [autoTradeAtrPeriod, setAutoTradeAtrPeriod] = useState(14);
  const [autoTradeAtrSlMult, setAutoTradeAtrSlMult] = useState(1.5);
  const [autoTradeAtrTpMult, setAutoTradeAtrTpMult] = useState(2.5);
  const [autoTradeTrailingEnabled, setAutoTradeTrailingEnabled] = useState(true);
  const [autoTradeTrailingActivationRr, setAutoTradeTrailingActivationRr] = useState(1.0);
  const [autoTradeTrailingAtrMult, setAutoTradeTrailingAtrMult] = useState(1.0);
  const [autoTradeConfidenceModel, setAutoTradeConfidenceModel] = useState("weighted");
  const [autoTradeConfidenceThreshold, setAutoTradeConfidenceThreshold] = useState(0.6);
  const [autoTradeTimeframes, setAutoTradeTimeframes] = useState(DEFAULT_MULTI_TFS);
  const [autoTradeTfWeightM1, setAutoTradeTfWeightM1] = useState(0.35);
  const [autoTradeTfWeightM5, setAutoTradeTfWeightM5] = useState(0.30);
  const [autoTradeTfWeightM15, setAutoTradeTfWeightM15] = useState(0.20);
  const [autoTradeTfWeightM30, setAutoTradeTfWeightM30] = useState(0.15);
  const [autoTradePartialTpEnabled, setAutoTradePartialTpEnabled] = useState(true);
  const [autoTradePartialTpRr1, setAutoTradePartialTpRr1] = useState(1.0);
  const [autoTradePartialTpClosePct1, setAutoTradePartialTpClosePct1] = useState(40);
  const [autoTradePartialTpRr2, setAutoTradePartialTpRr2] = useState(2.0);
  const [autoTradePartialTpClosePct2, setAutoTradePartialTpClosePct2] = useState(35);
  const [autoTradeBreakEvenEnabled, setAutoTradeBreakEvenEnabled] = useState(true);
  const [autoTradeBreakEvenRr, setAutoTradeBreakEvenRr] = useState(1.0);
  const [autoTradeBreakEvenOffsetAtrMult, setAutoTradeBreakEvenOffsetAtrMult] = useState(0.1);
  const [autoTradeTrailingMode, setAutoTradeTrailingMode] = useState("stateful_hl");
  const [autoTradeStatefulTrailBufferAtrMult, setAutoTradeStatefulTrailBufferAtrMult] = useState(0.5);
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
  const [mlDataset, setMlDataset] = useState([]);
  const [mlDatasetLimit, setMlDatasetLimit] = useState(50);
  const [mlExportFormat, setMlExportFormat] = useState("json");
  const [mlExportLimit, setMlExportLimit] = useState(10000);
  const [mlBusy, setMlBusy] = useState({ dataset: false, train: false, export: false });
  const [mlLastTrain, setMlLastTrain] = useState(null);
  const [mlLastExport, setMlLastExport] = useState(null);
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
        setAutoTradeRiskMode(String(data.auto_trade_risk_mode || "fixed_lot"));
        setAutoTradeRiskSelectorStrategy(String(data.auto_trade_risk_selector_strategy || "manual"));
        setAutoTradeRiskAtrThreshold(Number(data.auto_trade_risk_atr_threshold ?? 12));
        setAutoTradeRiskBalanceFixedThreshold(Number(data.auto_trade_risk_balance_fixed_threshold ?? 500));
        setAutoTradeRiskConfidenceThreshold(Number(data.auto_trade_risk_confidence_threshold ?? 0.7));
        setAutoTradeRiskSpreadFixedThreshold(Number(data.auto_trade_risk_spread_fixed_threshold ?? 120));
        setAutoTradeRiskSpreadLowThreshold(Number(data.auto_trade_risk_spread_low_threshold ?? 60));
        setAutoTradeRiskHybridAddonRrThreshold(Number(data.auto_trade_risk_hybrid_addon_rr_threshold ?? 2.0));
        setAutoTradeRiskHybridEntryMode(String(data.auto_trade_risk_hybrid_entry_mode || "risk_percent"));
        setAutoTradeRiskHybridAddonMode(String(data.auto_trade_risk_hybrid_addon_mode || "balance_scaled"));
        setAutoTradeRiskAdaptiveWindowDays(Number(data.auto_trade_risk_adaptive_window_days ?? 90));
        setAutoTradeRiskAdaptiveMinTrades(Number(data.auto_trade_risk_adaptive_min_trades ?? 12));
        setAutoTradeHedgeEnabled(data.hedge_enabled !== false);
        setAutoTradeHedgeThreshold(Number(data.hedge_threshold ?? -0.05));
        setAutoTradeHedgeSlots(Number(data.hedge_slots ?? 2));
        setAutoTradeRiskPercent(Number(data.auto_trade_risk_percent ?? 1));
        setAutoTradeUseAccountBalance(data.auto_trade_use_account_balance !== false);
        setAutoTradeUseAvailableMargin(data.auto_trade_use_available_margin !== false);
        setAutoTradeMinFreeMarginPct(Number(data.auto_trade_min_free_margin_pct ?? 30));
        setAutoTradeMaxMarginUsagePct(Number(data.auto_trade_max_margin_usage_pct ?? 70));
        setAutoTradeMaxSpreadPoints(Number(data.auto_trade_max_spread_points ?? 120));
        setAutoTradeMinSignalScore(Number(data.auto_trade_min_signal_score ?? 0.55));
        setAutoTradeAllowSell(data.auto_trade_allow_sell !== false);
        setAutoTradeCooldownSec(Number(data.auto_trade_cooldown_sec ?? 30));
        setAutoTradeSessionStartHour(Number(data.auto_trade_session_start_hour ?? 0));
        setAutoTradeSessionEndHour(Number(data.auto_trade_session_end_hour ?? 24));
        setAutoTradeUseAtrTpSl(data.auto_trade_use_atr_tpsl !== false);
        setAutoTradeAtrPeriod(Number(data.auto_trade_atr_period ?? 14));
        setAutoTradeAtrSlMult(Number(data.auto_trade_atr_sl_mult ?? 1.5));
        setAutoTradeAtrTpMult(Number(data.auto_trade_atr_tp_mult ?? 2.5));
        setAutoTradeTrailingEnabled(data.auto_trade_trailing_enabled !== false);
        setAutoTradeTrailingActivationRr(Number(data.auto_trade_trailing_activation_rr ?? 1.0));
        setAutoTradeTrailingAtrMult(Number(data.auto_trade_trailing_atr_mult ?? 1.0));
        setAutoTradeConfidenceModel(String(data.auto_trade_confidence_model || "weighted"));
        setAutoTradeConfidenceThreshold(Number(data.auto_trade_confidence_threshold ?? 0.6));
        setAutoTradeTimeframes(parseMultiTimeframes(data.timeframes || data.auto_trade_timeframes));
        setAutoTradeTfWeightM1(Number(data.auto_trade_tf_weight_m1 ?? 0.35));
        setAutoTradeTfWeightM5(Number(data.auto_trade_tf_weight_m5 ?? 0.30));
        setAutoTradeTfWeightM15(Number(data.auto_trade_tf_weight_m15 ?? 0.20));
        setAutoTradeTfWeightM30(Number(data.auto_trade_tf_weight_m30 ?? 0.15));
        setAutoTradePartialTpEnabled(data.auto_trade_partial_tp_enabled !== false);
        setAutoTradePartialTpRr1(Number(data.auto_trade_partial_tp_rr1 ?? 1.0));
        setAutoTradePartialTpClosePct1(Number(data.auto_trade_partial_tp_close_pct1 ?? 40));
        setAutoTradePartialTpRr2(Number(data.auto_trade_partial_tp_rr2 ?? 2.0));
        setAutoTradePartialTpClosePct2(Number(data.auto_trade_partial_tp_close_pct2 ?? 35));
        setAutoTradeBreakEvenEnabled(data.auto_trade_break_even_enabled !== false);
        setAutoTradeBreakEvenRr(Number(data.auto_trade_break_even_rr ?? 1.0));
        setAutoTradeBreakEvenOffsetAtrMult(Number(data.auto_trade_break_even_offset_atr_mult ?? 0.1));
        setAutoTradeTrailingMode(String(data.auto_trade_trailing_mode || "stateful_hl"));
        setAutoTradeStatefulTrailBufferAtrMult(Number(data.auto_trade_stateful_trail_buffer_atr_mult ?? 0.5));
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
    setAutoTradeRiskMode(String(data.auto_trade_risk_mode || "fixed_lot"));
    setAutoTradeRiskSelectorStrategy(String(data.auto_trade_risk_selector_strategy || "manual"));
    setAutoTradeRiskAtrThreshold(Number(data.auto_trade_risk_atr_threshold ?? 12));
    setAutoTradeRiskBalanceFixedThreshold(Number(data.auto_trade_risk_balance_fixed_threshold ?? 500));
    setAutoTradeRiskConfidenceThreshold(Number(data.auto_trade_risk_confidence_threshold ?? 0.7));
    setAutoTradeRiskSpreadFixedThreshold(Number(data.auto_trade_risk_spread_fixed_threshold ?? 120));
    setAutoTradeRiskSpreadLowThreshold(Number(data.auto_trade_risk_spread_low_threshold ?? 60));
    setAutoTradeRiskHybridAddonRrThreshold(Number(data.auto_trade_risk_hybrid_addon_rr_threshold ?? 2.0));
    setAutoTradeRiskHybridEntryMode(String(data.auto_trade_risk_hybrid_entry_mode || "risk_percent"));
    setAutoTradeRiskHybridAddonMode(String(data.auto_trade_risk_hybrid_addon_mode || "balance_scaled"));
    setAutoTradeRiskAdaptiveWindowDays(Number(data.auto_trade_risk_adaptive_window_days ?? 90));
    setAutoTradeRiskAdaptiveMinTrades(Number(data.auto_trade_risk_adaptive_min_trades ?? 12));
    setAutoTradeHedgeEnabled(data.hedge_enabled !== false);
    setAutoTradeHedgeThreshold(Number(data.hedge_threshold ?? -0.05));
    setAutoTradeHedgeSlots(Number(data.hedge_slots ?? 2));
    setAutoTradeRiskPercent(Number(data.auto_trade_risk_percent ?? 1));
    setAutoTradeUseAccountBalance(data.auto_trade_use_account_balance !== false);
    setAutoTradeUseAvailableMargin(data.auto_trade_use_available_margin !== false);
    setAutoTradeMinFreeMarginPct(Number(data.auto_trade_min_free_margin_pct ?? 30));
    setAutoTradeMaxMarginUsagePct(Number(data.auto_trade_max_margin_usage_pct ?? 70));
    setAutoTradeMaxSpreadPoints(Number(data.auto_trade_max_spread_points ?? 120));
    setAutoTradeMinSignalScore(Number(data.auto_trade_min_signal_score ?? 0.55));
    setAutoTradeAllowSell(data.auto_trade_allow_sell !== false);
    setAutoTradeCooldownSec(Number(data.auto_trade_cooldown_sec ?? 30));
    setAutoTradeSessionStartHour(Number(data.auto_trade_session_start_hour ?? 0));
    setAutoTradeSessionEndHour(Number(data.auto_trade_session_end_hour ?? 24));
    setAutoTradeUseAtrTpSl(data.auto_trade_use_atr_tpsl !== false);
    setAutoTradeAtrPeriod(Number(data.auto_trade_atr_period ?? 14));
    setAutoTradeAtrSlMult(Number(data.auto_trade_atr_sl_mult ?? 1.5));
    setAutoTradeAtrTpMult(Number(data.auto_trade_atr_tp_mult ?? 2.5));
    setAutoTradeTrailingEnabled(data.auto_trade_trailing_enabled !== false);
    setAutoTradeTrailingActivationRr(Number(data.auto_trade_trailing_activation_rr ?? 1.0));
    setAutoTradeTrailingAtrMult(Number(data.auto_trade_trailing_atr_mult ?? 1.0));
    setAutoTradeConfidenceModel(String(data.auto_trade_confidence_model || "weighted"));
    setAutoTradeConfidenceThreshold(Number(data.auto_trade_confidence_threshold ?? 0.6));
    setAutoTradeTimeframes(parseMultiTimeframes(data.timeframes || data.auto_trade_timeframes));
    setAutoTradeTfWeightM1(Number(data.auto_trade_tf_weight_m1 ?? 0.35));
    setAutoTradeTfWeightM5(Number(data.auto_trade_tf_weight_m5 ?? 0.30));
    setAutoTradeTfWeightM15(Number(data.auto_trade_tf_weight_m15 ?? 0.20));
    setAutoTradeTfWeightM30(Number(data.auto_trade_tf_weight_m30 ?? 0.15));
    setAutoTradePartialTpEnabled(data.auto_trade_partial_tp_enabled !== false);
    setAutoTradePartialTpRr1(Number(data.auto_trade_partial_tp_rr1 ?? 1.0));
    setAutoTradePartialTpClosePct1(Number(data.auto_trade_partial_tp_close_pct1 ?? 40));
    setAutoTradePartialTpRr2(Number(data.auto_trade_partial_tp_rr2 ?? 2.0));
    setAutoTradePartialTpClosePct2(Number(data.auto_trade_partial_tp_close_pct2 ?? 35));
    setAutoTradeBreakEvenEnabled(data.auto_trade_break_even_enabled !== false);
    setAutoTradeBreakEvenRr(Number(data.auto_trade_break_even_rr ?? 1.0));
    setAutoTradeBreakEvenOffsetAtrMult(Number(data.auto_trade_break_even_offset_atr_mult ?? 0.1));
    setAutoTradeTrailingMode(String(data.auto_trade_trailing_mode || "stateful_hl"));
    setAutoTradeStatefulTrailBufferAtrMult(Number(data.auto_trade_stateful_trail_buffer_atr_mult ?? 0.5));
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
      const currentSettings = data?.current_settings || {};
      if (Object.prototype.hasOwnProperty.call(currentSettings, "hedge_enabled")) {
        setAutoTradeHedgeEnabled(currentSettings.hedge_enabled !== false);
      }
      if (Object.prototype.hasOwnProperty.call(currentSettings, "hedge_threshold")) {
        const value = Number(currentSettings.hedge_threshold);
        if (Number.isFinite(value)) setAutoTradeHedgeThreshold(value);
      }
      if (Object.prototype.hasOwnProperty.call(currentSettings, "hedge_slots")) {
        const value = Number(currentSettings.hedge_slots);
        if (Number.isFinite(value)) setAutoTradeHedgeSlots(value);
      }
      if (Object.prototype.hasOwnProperty.call(currentSettings, "timeframes")) {
        setAutoTradeTimeframes(parseMultiTimeframes(currentSettings.timeframes));
      }
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
          risk_mode: autoTradeRiskMode,
          risk_selector_strategy: autoTradeRiskSelectorStrategy,
          risk_atr_threshold: Number(autoTradeRiskAtrThreshold || 0),
          risk_balance_fixed_threshold: Number(autoTradeRiskBalanceFixedThreshold || 0),
          risk_confidence_threshold: Number(autoTradeRiskConfidenceThreshold || 0),
          risk_spread_fixed_threshold: Number(autoTradeRiskSpreadFixedThreshold || 0),
          risk_spread_low_threshold: Number(autoTradeRiskSpreadLowThreshold || 0),
          risk_hybrid_addon_rr_threshold: Number(autoTradeRiskHybridAddonRrThreshold || 2),
          risk_hybrid_entry_mode: autoTradeRiskHybridEntryMode,
          risk_hybrid_addon_mode: autoTradeRiskHybridAddonMode,
          risk_adaptive_window_days: Number(autoTradeRiskAdaptiveWindowDays || 90),
          risk_adaptive_min_trades: Number(autoTradeRiskAdaptiveMinTrades || 12),
          hedge_enabled: !!autoTradeHedgeEnabled,
          hedge_threshold: Number(autoTradeHedgeThreshold || -0.05),
          hedge_slots: Math.max(0, Number(autoTradeHedgeSlots || 0)),
          risk_percent: Number(autoTradeRiskPercent || 1),
          use_account_balance: !!autoTradeUseAccountBalance,
          use_available_margin: !!autoTradeUseAvailableMargin,
          min_free_margin_pct: Number(autoTradeMinFreeMarginPct || 0),
          max_margin_usage_pct: Number(autoTradeMaxMarginUsagePct || 0),
          max_spread_points: Number(autoTradeMaxSpreadPoints || 0),
          min_signal_score: Number(autoTradeMinSignalScore || 0),
          allow_sell: !!autoTradeAllowSell,
          cooldown_sec: Number(autoTradeCooldownSec || 0),
          session_start_hour: Number(autoTradeSessionStartHour || 0),
          session_end_hour: Number(autoTradeSessionEndHour || 24),
          use_atr_tpsl: !!autoTradeUseAtrTpSl,
          atr_period: Number(autoTradeAtrPeriod || 14),
          atr_sl_mult: Number(autoTradeAtrSlMult || 1.5),
          atr_tp_mult: Number(autoTradeAtrTpMult || 2.5),
          trailing_enabled: !!autoTradeTrailingEnabled,
          trailing_activation_rr: Number(autoTradeTrailingActivationRr || 1),
          trailing_atr_mult: Number(autoTradeTrailingAtrMult || 1),
          confidence_model: autoTradeConfidenceModel,
          confidence_threshold: Number(autoTradeConfidenceThreshold || 0.6),
          timeframes: parseMultiTimeframes(autoTradeTimeframes),
          tf_weight_m1: Number(autoTradeTfWeightM1 || 0),
          tf_weight_m5: Number(autoTradeTfWeightM5 || 0),
          tf_weight_m15: Number(autoTradeTfWeightM15 || 0),
          tf_weight_m30: Number(autoTradeTfWeightM30 || 0),
          partial_tp_enabled: !!autoTradePartialTpEnabled,
          partial_tp_rr1: Number(autoTradePartialTpRr1 || 1),
          partial_tp_close_pct1: Number(autoTradePartialTpClosePct1 || 0),
          partial_tp_rr2: Number(autoTradePartialTpRr2 || 2),
          partial_tp_close_pct2: Number(autoTradePartialTpClosePct2 || 0),
          break_even_enabled: !!autoTradeBreakEvenEnabled,
          break_even_rr: Number(autoTradeBreakEvenRr || 1),
          break_even_offset_atr_mult: Number(autoTradeBreakEvenOffsetAtrMult || 0),
          trailing_mode: autoTradeTrailingMode,
          stateful_trail_buffer_atr_mult: Number(autoTradeStatefulTrailBufferAtrMult || 0),
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

      if (data.status === "partial") {
        const badRows = Array.isArray(data.results)
          ? data.results.filter((r) => r.partial || (!r.synced && !r.partial))
          : [];
        const names = badRows.map((r) => r.broker_name || `broker-${r.broker_id || "unknown"}`).slice(0, 3).join(", ");
        const suffix = names ? ` Broker bermasalah: ${names}.` : "";
        setSnackbar({
          open: true,
          severity: "warning",
          message: `${data.message || "Sinkronisasi history parsial."} (${label}).${suffix}`,
        });
      } else {
        setSnackbar({ open: true, severity: "success", message: `Sinkronisasi history selesai untuk ${label}.` });
      }
    } catch (err) {
      setSnackbar({ open: true, severity: "error", message: err.message || "Tidak bisa menjalankan sinkronisasi history." });
    } finally {
      setTradeHistorySyncRunning(false);
    }
  };

  const loadMlDataset = async () => {
    setMlBusy((prev) => ({ ...prev, dataset: true }));
    try {
      const safeLimit = Math.max(10, Math.min(5000, Number(mlDatasetLimit || 50)));
      const res = await fetch(`${API_BASE}/account/auto_trade_ml_dataset?limit=${safeLimit}`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.status === "error") {
        throw new Error(data.message || data.detail || "Gagal mengambil dataset ML.");
      }
      const rows = Array.isArray(data.dataset) ? data.dataset : [];
      setMlDataset(rows);
      setSnackbar({ open: true, severity: "success", message: `Dataset ML berhasil dimuat (${rows.length} row).` });
    } catch (err) {
      setSnackbar({ open: true, severity: "error", message: err.message || "Tidak bisa mengambil dataset ML." });
    } finally {
      setMlBusy((prev) => ({ ...prev, dataset: false }));
    }
  };

  const runMlTrain = async () => {
    setMlBusy((prev) => ({ ...prev, train: true }));
    try {
      const safeLimit = Math.max(100, Math.min(50000, Number(mlExportLimit || 5000)));
      const res = await fetch(`${API_BASE}/account/auto_trade_ml_train?limit=${safeLimit}`, {
        method: "POST",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.status === "error") {
        throw new Error(data.message || data.detail || "Retrain model gagal.");
      }
      const trained = !!(data.result && data.result.trained);
      setMlLastTrain(data.result || null);
      if (!trained) {
        throw new Error(data.result?.reason || "Retrain belum dijalankan (data tidak cukup)." );
      }
      setSnackbar({ open: true, severity: "success", message: `Retrain berhasil (${data.result.model_type || "model"}, rows=${data.result.rows || 0}).` });
    } catch (err) {
      setSnackbar({ open: true, severity: "error", message: err.message || "Retrain model gagal." });
    } finally {
      setMlBusy((prev) => ({ ...prev, train: false }));
    }
  };

  const runMlExport = async () => {
    setMlBusy((prev) => ({ ...prev, export: true }));
    try {
      const safeLimit = Math.max(100, Math.min(200000, Number(mlExportLimit || 10000)));
      const res = await fetch(`${API_BASE}/account/auto_trade_ml_export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ format: mlExportFormat, limit: safeLimit }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.status === "error") {
        throw new Error(data.message || data.detail || "Export dataset ML gagal.");
      }
      setMlLastExport(data.export || null);
      setSnackbar({
        open: true,
        severity: "success",
        message: `Export ${data.export?.format || mlExportFormat} berhasil (${data.export?.rows || 0} row).`,
      });
    } catch (err) {
      setSnackbar({ open: true, severity: "error", message: err.message || "Export dataset ML gagal." });
    } finally {
      setMlBusy((prev) => ({ ...prev, export: false }));
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
    <Box
      sx={{
        p: { xs: 1.5, sm: 3 },
        "& .MuiTypography-caption": {
          fontSize: { xs: "0.82rem", sm: "0.75rem" },
          lineHeight: { xs: 1.45, sm: 1.4 },
        },
        "& .MuiTypography-subtitle1": {
          fontSize: { xs: "1.06rem", sm: "1rem" },
        },
        "& .MuiTypography-subtitle2": {
          fontSize: { xs: "0.97rem", sm: "0.875rem" },
        },
        "& .MuiTypography-body2": {
          fontSize: { xs: "0.93rem", sm: "0.875rem" },
        },
        "& .MuiFormLabel-root": {
          fontSize: { xs: "0.98rem", sm: "0.95rem" },
        },
        "& .MuiInputBase-input": {
          fontSize: { xs: "1rem", sm: "0.95rem" },
          py: { xs: 1.25, sm: 1.0 },
        },
        "& .MuiFormHelperText-root": {
          fontSize: { xs: "0.85rem", sm: "0.75rem" },
          lineHeight: 1.35,
        },
        "& .MuiButton-root": {
          fontSize: { xs: "0.95rem", sm: "0.875rem" },
          minHeight: { xs: 42, sm: 36 },
          px: { xs: 1.5, sm: 1.25 },
        },
        "& .MuiTableCell-root": {
          fontSize: { xs: "0.9rem", sm: "0.875rem" },
          py: { xs: 1.1, sm: 0.75 },
        },
        "& .MuiChip-label": {
          fontSize: { xs: "0.82rem", sm: "0.78rem" },
        },
      }}
    >
      <Typography variant="h5" sx={{ mb: 2, fontSize: { xs: "1.35rem", sm: "1.5rem" } }}>Account Monitor</Typography>
      <Paper sx={{ p: { xs: 1.5, sm: 2 }, mb: 2 }}>
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
            <Grid item xs={12} md={4}>
              <FormControlLabel
                control={<Switch checked={autoTradeAllowSell} onChange={(e) => setAutoTradeAllowSell(e.target.checked)} />}
                label="Allow Sell Signal"
              />
            </Grid>
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                select
                size="small"
                label="Risk Selector"
                value={autoTradeRiskSelectorStrategy}
                onChange={(e) => setAutoTradeRiskSelectorStrategy(e.target.value)}
                helperText="Manual / rule-based / condition-driven / hybrid / adaptive"
              >
                <MenuItem value="manual">Manual</MenuItem>
                <MenuItem value="rule_based">Rule-based Switching</MenuItem>
                <MenuItem value="condition_driven">Condition-driven Adaptation</MenuItem>
                <MenuItem value="hybrid">Hybrid Strategy</MenuItem>
                <MenuItem value="adaptive">Adaptive (History-based)</MenuItem>
              </TextField>
            </Grid>
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                select
                size="small"
                label="Risk Mode"
                value={autoTradeRiskMode}
                onChange={(e) => setAutoTradeRiskMode(e.target.value)}
                helperText="balance_scaled memakai initial balance; atr_dynamic memakai ATR untuk sizing"
              >
                <MenuItem value="fixed_lot">Fixed Lot</MenuItem>
                <MenuItem value="risk_percent">Risk % per Trade</MenuItem>
                <MenuItem value="balance_scaled">Balance Scaled Lot</MenuItem>
                <MenuItem value="atr_dynamic">ATR Dynamic Lot</MenuItem>
                <MenuItem value="hedge">Hedge Recovery</MenuItem>
              </TextField>
            </Grid>
            <Grid item xs={12} md={4}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, minHeight: 40 }}>
                <FormControlLabel
                  control={<Switch checked={autoTradeHedgeEnabled} onChange={(e) => setAutoTradeHedgeEnabled(e.target.checked)} />}
                  label="Hedge Enabled"
                />
                <Chip
                  size="small"
                  color={autoTradeHedgeEnabled ? "success" : "default"}
                  label={autoTradeHedgeEnabled ? "ENABLED" : "DISABLED"}
                />
              </Box>
            </Grid>
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                size="small"
                label="Hedge Threshold (ratio)"
                type="number"
                value={autoTradeHedgeThreshold}
                onChange={(e) => setAutoTradeHedgeThreshold(Number(e.target.value))}
                inputProps={{ min: -0.5, max: -0.001, step: 0.001 }}
                helperText="Contoh -0.05 = -5% equity"
                disabled={!autoTradeHedgeEnabled}
              />
            </Grid>
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                size="small"
                label="Hedge Slots"
                type="number"
                value={autoTradeHedgeSlots}
                onChange={(e) => setAutoTradeHedgeSlots(Number(e.target.value))}
                inputProps={{ min: 0, max: 10, step: 1 }}
                helperText="Slot hedge tambahan di luar posisi normal"
                disabled={!autoTradeHedgeEnabled}
              />
            </Grid>
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                size="small"
                label="Rule ATR Threshold"
                type="number"
                value={autoTradeRiskAtrThreshold}
                onChange={(e) => setAutoTradeRiskAtrThreshold(Number(e.target.value))}
                inputProps={{ min: 0, step: 0.1 }}
                disabled={autoTradeRiskSelectorStrategy === "manual"}
              />
            </Grid>
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                size="small"
                label="Rule Balance <$"
                type="number"
                value={autoTradeRiskBalanceFixedThreshold}
                onChange={(e) => setAutoTradeRiskBalanceFixedThreshold(Number(e.target.value))}
                inputProps={{ min: 0, step: 10 }}
                disabled={autoTradeRiskSelectorStrategy === "manual"}
              />
            </Grid>
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                size="small"
                label="Selector Confidence"
                type="number"
                value={autoTradeRiskConfidenceThreshold}
                onChange={(e) => setAutoTradeRiskConfidenceThreshold(Number(e.target.value))}
                inputProps={{ min: 0, max: 1, step: 0.01 }}
                disabled={autoTradeRiskSelectorStrategy === "manual"}
              />
            </Grid>
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                size="small"
                label="Spread Fixed Threshold"
                type="number"
                value={autoTradeRiskSpreadFixedThreshold}
                onChange={(e) => setAutoTradeRiskSpreadFixedThreshold(Number(e.target.value))}
                inputProps={{ min: 0, step: 1 }}
                disabled={autoTradeRiskSelectorStrategy === "manual"}
              />
            </Grid>
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                size="small"
                label="Spread Low Threshold"
                type="number"
                value={autoTradeRiskSpreadLowThreshold}
                onChange={(e) => setAutoTradeRiskSpreadLowThreshold(Number(e.target.value))}
                inputProps={{ min: 0, step: 1 }}
                disabled={autoTradeRiskSelectorStrategy === "manual"}
              />
            </Grid>
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                size="small"
                label="Hybrid Add-on RR"
                type="number"
                value={autoTradeRiskHybridAddonRrThreshold}
                onChange={(e) => setAutoTradeRiskHybridAddonRrThreshold(Number(e.target.value))}
                inputProps={{ min: 0.2, max: 10, step: 0.1 }}
                disabled={autoTradeRiskSelectorStrategy !== "hybrid"}
              />
            </Grid>
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                select
                size="small"
                label="Hybrid Entry Mode"
                value={autoTradeRiskHybridEntryMode}
                onChange={(e) => setAutoTradeRiskHybridEntryMode(e.target.value)}
                disabled={autoTradeRiskSelectorStrategy !== "hybrid"}
              >
                <MenuItem value="fixed_lot">Fixed Lot</MenuItem>
                <MenuItem value="risk_percent">Risk % per Trade</MenuItem>
                <MenuItem value="balance_scaled">Balance Scaled Lot</MenuItem>
                <MenuItem value="atr_dynamic">ATR Dynamic Lot</MenuItem>
              </TextField>
            </Grid>
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                select
                size="small"
                label="Hybrid Add-on Mode"
                value={autoTradeRiskHybridAddonMode}
                onChange={(e) => setAutoTradeRiskHybridAddonMode(e.target.value)}
                disabled={autoTradeRiskSelectorStrategy !== "hybrid"}
              >
                <MenuItem value="fixed_lot">Fixed Lot</MenuItem>
                <MenuItem value="risk_percent">Risk % per Trade</MenuItem>
                <MenuItem value="balance_scaled">Balance Scaled Lot</MenuItem>
                <MenuItem value="atr_dynamic">ATR Dynamic Lot</MenuItem>
              </TextField>
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Adaptive Window (days)"
                type="number"
                value={autoTradeRiskAdaptiveWindowDays}
                onChange={(e) => setAutoTradeRiskAdaptiveWindowDays(Number(e.target.value))}
                inputProps={{ min: 7, max: 3650, step: 1 }}
                disabled={autoTradeRiskSelectorStrategy !== "adaptive"}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Adaptive Min Trades"
                type="number"
                value={autoTradeRiskAdaptiveMinTrades}
                onChange={(e) => setAutoTradeRiskAdaptiveMinTrades(Number(e.target.value))}
                inputProps={{ min: 3, max: 5000, step: 1 }}
                disabled={autoTradeRiskSelectorStrategy !== "adaptive"}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Risk %"
                type="number"
                value={autoTradeRiskPercent}
                onChange={(e) => setAutoTradeRiskPercent(Number(e.target.value))}
                inputProps={{ min: 0.1, max: 10, step: 0.1 }}
                disabled={autoTradeRiskMode === "fixed_lot" || autoTradeRiskMode === "balance_scaled"}
                helperText={autoTradeRiskMode === "atr_dynamic" ? "Dipakai sebagai risk budget ATR dynamic" : "0.1 - 10%"}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Min Signal Score"
                type="number"
                value={autoTradeMinSignalScore}
                onChange={(e) => setAutoTradeMinSignalScore(Number(e.target.value))}
                inputProps={{ min: 0, max: 0.95, step: 0.01 }}
                helperText="0.00 - 0.95"
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Max Spread (points)"
                type="number"
                value={autoTradeMaxSpreadPoints}
                onChange={(e) => setAutoTradeMaxSpreadPoints(Number(e.target.value))}
                inputProps={{ min: 0, step: 1 }}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Cooldown (sec)"
                type="number"
                value={autoTradeCooldownSec}
                onChange={(e) => setAutoTradeCooldownSec(Number(e.target.value))}
                inputProps={{ min: 0, max: 3600, step: 1 }}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Session Start (hour)"
                type="number"
                value={autoTradeSessionStartHour}
                onChange={(e) => setAutoTradeSessionStartHour(Number(e.target.value))}
                inputProps={{ min: 0, max: 23, step: 1 }}
                helperText="0 - 23"
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Session End (hour)"
                type="number"
                value={autoTradeSessionEndHour}
                onChange={(e) => setAutoTradeSessionEndHour(Number(e.target.value))}
                inputProps={{ min: 0, max: 24, step: 1 }}
                helperText="0 - 24"
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Min Free Margin %"
                type="number"
                value={autoTradeMinFreeMarginPct}
                onChange={(e) => setAutoTradeMinFreeMarginPct(Number(e.target.value))}
                inputProps={{ min: 0, max: 95, step: 1 }}
                helperText="Cadangan margin minimum"
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Max Margin Usage %"
                type="number"
                value={autoTradeMaxMarginUsagePct}
                onChange={(e) => setAutoTradeMaxMarginUsagePct(Number(e.target.value))}
                inputProps={{ min: 1, max: 100, step: 1 }}
                helperText="Batas margin untuk order baru"
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <FormControlLabel
                control={<Switch checked={autoTradeUseAvailableMargin} onChange={(e) => setAutoTradeUseAvailableMargin(e.target.checked)} />}
                label="Risk Base: Available Margin"
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <FormControlLabel
                control={<Switch checked={autoTradeUseAccountBalance} onChange={(e) => setAutoTradeUseAccountBalance(e.target.checked)} />}
                label="Risk Base: Account Balance"
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <FormControlLabel
                control={<Switch checked={autoTradeUseAtrTpSl} onChange={(e) => setAutoTradeUseAtrTpSl(e.target.checked)} />}
                label="Adaptive ATR TP/SL"
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="ATR Period"
                type="number"
                value={autoTradeAtrPeriod}
                onChange={(e) => setAutoTradeAtrPeriod(Number(e.target.value))}
                inputProps={{ min: 5, max: 100, step: 1 }}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="ATR SL Mult"
                type="number"
                value={autoTradeAtrSlMult}
                onChange={(e) => setAutoTradeAtrSlMult(Number(e.target.value))}
                inputProps={{ min: 0.2, max: 10, step: 0.1 }}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="ATR TP Mult"
                type="number"
                value={autoTradeAtrTpMult}
                onChange={(e) => setAutoTradeAtrTpMult(Number(e.target.value))}
                inputProps={{ min: 0.2, max: 20, step: 0.1 }}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <FormControlLabel
                control={<Switch checked={autoTradeTrailingEnabled} onChange={(e) => setAutoTradeTrailingEnabled(e.target.checked)} />}
                label="Trailing Stop Enabled"
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Trailing Activate RR"
                type="number"
                value={autoTradeTrailingActivationRr}
                onChange={(e) => setAutoTradeTrailingActivationRr(Number(e.target.value))}
                inputProps={{ min: 0.2, max: 5, step: 0.1 }}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Trailing ATR Mult"
                type="number"
                value={autoTradeTrailingAtrMult}
                onChange={(e) => setAutoTradeTrailingAtrMult(Number(e.target.value))}
                inputProps={{ min: 0.2, max: 10, step: 0.1 }}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                select
                size="small"
                label="Confidence Model"
                value={autoTradeConfidenceModel}
                onChange={(e) => setAutoTradeConfidenceModel(e.target.value)}
              >
                <MenuItem value="weighted">Weighted per TF</MenuItem>
                <MenuItem value="equal">Equal per TF</MenuItem>
              </TextField>
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Confidence Threshold"
                type="number"
                value={autoTradeConfidenceThreshold}
                onChange={(e) => setAutoTradeConfidenceThreshold(Number(e.target.value))}
                inputProps={{ min: 0, max: 0.95, step: 0.01 }}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                size="small"
                label="Indicator Timeframes"
                value={autoTradeTimeframes.join(",")}
                onChange={(e) => setAutoTradeTimeframes(parseMultiTimeframes(e.target.value))}
                helperText="Pisahkan dengan koma. Minimal 2 TF. Contoh: M1,M5,M15,M30"
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Weight M1"
                type="number"
                value={autoTradeTfWeightM1}
                onChange={(e) => setAutoTradeTfWeightM1(Number(e.target.value))}
                inputProps={{ min: 0, step: 0.01 }}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Weight M5"
                type="number"
                value={autoTradeTfWeightM5}
                onChange={(e) => setAutoTradeTfWeightM5(Number(e.target.value))}
                inputProps={{ min: 0, step: 0.01 }}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Weight M15"
                type="number"
                value={autoTradeTfWeightM15}
                onChange={(e) => setAutoTradeTfWeightM15(Number(e.target.value))}
                inputProps={{ min: 0, step: 0.01 }}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Weight M30"
                type="number"
                value={autoTradeTfWeightM30}
                onChange={(e) => setAutoTradeTfWeightM30(Number(e.target.value))}
                inputProps={{ min: 0, step: 0.01 }}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <FormControlLabel
                control={<Switch checked={autoTradePartialTpEnabled} onChange={(e) => setAutoTradePartialTpEnabled(e.target.checked)} />}
                label="Partial TP Bertahap"
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Partial TP RR1"
                type="number"
                value={autoTradePartialTpRr1}
                onChange={(e) => setAutoTradePartialTpRr1(Number(e.target.value))}
                inputProps={{ min: 0.2, max: 10, step: 0.1 }}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Close % Stage 1"
                type="number"
                value={autoTradePartialTpClosePct1}
                onChange={(e) => setAutoTradePartialTpClosePct1(Number(e.target.value))}
                inputProps={{ min: 1, max: 95, step: 1 }}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Partial TP RR2"
                type="number"
                value={autoTradePartialTpRr2}
                onChange={(e) => setAutoTradePartialTpRr2(Number(e.target.value))}
                inputProps={{ min: 0.2, max: 20, step: 0.1 }}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Close % Stage 2"
                type="number"
                value={autoTradePartialTpClosePct2}
                onChange={(e) => setAutoTradePartialTpClosePct2(Number(e.target.value))}
                inputProps={{ min: 1, max: 95, step: 1 }}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <FormControlLabel
                control={<Switch checked={autoTradeBreakEvenEnabled} onChange={(e) => setAutoTradeBreakEvenEnabled(e.target.checked)} />}
                label="Break-even Lock"
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Break-even RR"
                type="number"
                value={autoTradeBreakEvenRr}
                onChange={(e) => setAutoTradeBreakEvenRr(Number(e.target.value))}
                inputProps={{ min: 0.2, max: 10, step: 0.1 }}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="BE Offset ATR Mult"
                type="number"
                value={autoTradeBreakEvenOffsetAtrMult}
                onChange={(e) => setAutoTradeBreakEvenOffsetAtrMult(Number(e.target.value))}
                inputProps={{ min: 0, max: 2, step: 0.05 }}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                select
                size="small"
                label="Trailing Mode"
                value={autoTradeTrailingMode}
                onChange={(e) => setAutoTradeTrailingMode(e.target.value)}
              >
                <MenuItem value="stateful_hl">Stateful High/Low</MenuItem>
                <MenuItem value="atr">ATR Dynamic</MenuItem>
              </TextField>
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Stateful Trail Buffer ATR"
                type="number"
                value={autoTradeStatefulTrailBufferAtrMult}
                onChange={(e) => setAutoTradeStatefulTrailBufferAtrMult(Number(e.target.value))}
                inputProps={{ min: 0, max: 5, step: 0.1 }}
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
                    <Grid item xs={12} md={3}><Typography variant="caption">Leverage: {autoTradeConstraints?.account_metrics?.leverage || "-"}</Typography></Grid>
                    <Grid item xs={12} md={3}><Typography variant="caption">Balance: {autoTradeConstraints?.account_metrics?.balance ?? "-"}</Typography></Grid>
                    <Grid item xs={12} md={3}><Typography variant="caption">Equity: {autoTradeConstraints?.account_metrics?.equity ?? "-"}</Typography></Grid>
                    <Grid item xs={12} md={3}><Typography variant="caption">Free Margin: {autoTradeConstraints?.account_metrics?.margin_free ?? "-"}</Typography></Grid>
                    <Grid item xs={12} md={3}><Typography variant="caption">Spread (points): {autoTradeConstraints?.account_metrics?.spread_points ?? "-"}</Typography></Grid>
                    <Grid item xs={12} md={3}><Typography variant="caption">Est. Margin/Lot: {autoTradeConstraints?.account_metrics?.estimated_margin_per_lot ?? "-"}</Typography></Grid>
                    <Grid item xs={12} md={3}><Typography variant="caption">Can Trade: {autoTradeConstraints?.account_metrics?.can_trade ? "Yes" : "No"}</Typography></Grid>
                    <Grid item xs={12} md={3}><Typography variant="caption">Metrics Reason: {autoTradeConstraints?.account_metrics?.reason || "-"}</Typography></Grid>
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

          <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>Adaptive ML Toolkit</Typography>
          <Grid container spacing={1} alignItems="center">
            <Grid item xs={12} md={2}>
              <TextField
                fullWidth
                size="small"
                label="Dataset Limit"
                type="number"
                value={mlDatasetLimit}
                onChange={(e) => setMlDatasetLimit(Number(e.target.value))}
                inputProps={{ min: 10, max: 5000, step: 10 }}
              />
            </Grid>
            <Grid item xs={12} md={2}>
              <TextField
                fullWidth
                select
                size="small"
                label="Export Format"
                value={mlExportFormat}
                onChange={(e) => setMlExportFormat(e.target.value)}
              >
                <MenuItem value="json">JSON</MenuItem>
                <MenuItem value="csv">CSV</MenuItem>
              </TextField>
            </Grid>
            <Grid item xs={12} md={2}>
              <TextField
                fullWidth
                size="small"
                label="Train/Export Limit"
                type="number"
                value={mlExportLimit}
                onChange={(e) => setMlExportLimit(Number(e.target.value))}
                inputProps={{ min: 100, max: 200000, step: 100 }}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
                <Button
                  variant="outlined"
                  onClick={loadMlDataset}
                  disabled={mlBusy.dataset}
                  data-testid="ml-dataset-btn"
                >
                  {mlBusy.dataset ? "Loading..." : "Preview Dataset"}
                </Button>
                <Button
                  variant="contained"
                  color="success"
                  onClick={runMlTrain}
                  disabled={mlBusy.train}
                  data-testid="ml-train-btn"
                >
                  {mlBusy.train ? "Training..." : "Train Model"}
                </Button>
                <Button
                  variant="outlined"
                  color="secondary"
                  onClick={runMlExport}
                  disabled={mlBusy.export}
                  data-testid="ml-export-btn"
                >
                  {mlBusy.export ? "Exporting..." : "Export Dataset"}
                </Button>
                <Button
                  variant="contained"
                  color="primary"
                  component="a"
                  href={mlLastExport?.download_url ? `${API_BASE}${mlLastExport.download_url}` : undefined}
                  download={mlLastExport?.filename || undefined}
                  disabled={!mlLastExport?.download_url}
                  data-testid="ml-download-btn"
                >
                  Download Export
                </Button>
              </Box>
            </Grid>
            <Grid item xs={12}>
              {mlLastTrain?.trained ? (
                <Alert severity="success" sx={{ mt: 0.5 }}>
                  Model terbaru: {mlLastTrain.model_type || "unknown"} | rows: {mlLastTrain.rows || 0} | trained trade count: {mlLastTrain.trained_trade_count || 0}
                </Alert>
              ) : (
                <Alert severity="info" sx={{ mt: 0.5 }}>
                  Gunakan Preview Dataset untuk melihat data training, lalu jalankan Train Model untuk retrain manual.
                </Alert>
              )}
            </Grid>
            <Grid item xs={12}>
              <Typography variant="caption" color="text.secondary">
                {mlLastExport?.filename
                  ? `File export terakhir: ${mlLastExport.filename}`
                  : "Belum ada file export yang siap di-download."}
              </Typography>
            </Grid>
            <Grid item xs={12}>
              <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 260 }}>
                <Table size="small" stickyHeader>
                  <TableHead>
                    <TableRow>
                      <TableCell>Trade ID</TableCell>
                      <TableCell>Risk Mode</TableCell>
                      <TableCell>Symbol</TableCell>
                      <TableCell>Signal</TableCell>
                      <TableCell>ATR</TableCell>
                      <TableCell>Spread</TableCell>
                      <TableCell>Profit</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody data-testid="ml-dataset-table-body">
                    {mlDataset.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={7}>
                          <Typography variant="caption" color="text.secondary">Belum ada preview dataset.</Typography>
                        </TableCell>
                      </TableRow>
                    ) : (
                      mlDataset.map((row, idx) => (
                        <TableRow key={`${row.trade_id || "row"}-${idx}`}>
                          <TableCell>{row.trade_id || "-"}</TableCell>
                          <TableCell>{row.risk_mode || "-"}</TableCell>
                          <TableCell>{row.symbol || "-"}</TableCell>
                          <TableCell>{row.features?.signal_score ?? "-"}</TableCell>
                          <TableCell>{row.features?.atr ?? "-"}</TableCell>
                          <TableCell>{row.features?.spread_points ?? "-"}</TableCell>
                          <TableCell>{row.result?.profit ?? "-"}</TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
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
