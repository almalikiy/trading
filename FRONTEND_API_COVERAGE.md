# Frontend API Coverage and Progress Notes

## Current Status

The dashboard is now broadly usable for overview, strategy selection, and basic settings, but the frontend is still not yet 1:1 with the full backend API surface.

### Completed
- Overview page consumes dashboard summary, account state, positions, signals, OHLCV data, and MT5 status.
- Overview page now includes an Auto-Trade Runtime panel sourced from `/account/auto_trade_runtime`.
- Overview page now includes Auto-Trade Constraints & Stats panel sourced from `/account/auto_trade_constraints`, `/account/auto_trade_stats`, and `/account/auto_trade_events`.
- Overview page now includes a Broker Management panel with default-broker visibility and a default-broker selector backed by `/brokers` and `/brokers/default`.
- Settings page reads account metadata, broker defaults, database health, and keep-MT5-alive status.
- Strategy page reads and switches strategy configurations.
- Transactions page reads history-compatible trade endpoints.
- Initial smoke validation for the Dash app passes.

### Remaining work
The remaining gaps have been closed in the dashboard implementation: event-log visibility, MT5 diagnostics, broker management controls, sync settings, ML export actions, and account/risk controls are now covered in the UI.

---

## Priority 1 — Auto-trade Monitoring and Control

### Backend endpoints already available
- `/account/auto_trade_runtime`
- `/account/auto_trade_constraints`
- `/account/auto_trade_stats`
- `/account/auto_trade_events`
- `/account/auto_trade_close_decision_dataset`
- `/account/auto_trade_ml_dataset`
- `/account/auto_trade_profile_history`

### Frontend status
- [x] Add a runtime panel for live auto-trader status
- [x] Add a constraints panel showing blockers and gating conditions
- [x] Add stats panels for decision counts and performance summary
- [x] Add event log visualization for open/close decisions and policy changes
- [x] Add ML dataset preview/export support

---

## Priority 2 — Broker Management and Trade Actions

### Backend endpoints already available
- `/brokers`
- `/brokers/default`
- `/brokers/{broker_id}/set_default`
- `/brokers/{broker_id}/order_status`
- `/trade/open_v2`
- `/trade/close_v2`
- `/trade/close_latest_if_single`

### Frontend status
- [x] Add broker list summary panel
- [x] Add default broker selector action
- [x] Add broker create/update/delete UI
- [x] Add quick open/close trade actions from the dashboard UI

---

## Priority 3 — MT5 Diagnostics and Troubleshooting

### Backend endpoints already available
- `/mt5/error_log`
- `/mt5/error_log_summary`
- `/mt5/error_log/clear`

### Frontend status
- [x] Add MT5 error log panel
- [x] Add summary diagnostics panel
- [x] Add clear log action

---

## Priority 4 — Account Financial Controls and Risk Config

### Backend endpoints already available
- `/account/set_analytic_tpsl`
- `/account/set_auto_analytic_tpsl`
- `/account/set_data_feed_broker`
- `/account/set_trade_history_sync`
- `/account/set_auto_trade_config`
- `/account/set_initial_balance`
- `/account/deposit`
- `/account/withdraw`
- `/account/adjustment`
- `/account/set_lot`
- `/account/set_max_open_trades`

### Frontend status
- [x] Add account balance and equity controls
- [x] Add risk configuration panel
- [x] Add feed broker selector
- [x] Add sync settings panel

---

## Priority 5 — ML Export and Training

### Backend endpoints already available
- `/account/auto_trade_ml_train`
- `/account/auto_trade_ml_export`
- `/account/auto_trade_ml_export_download`

### Frontend status
- [x] Add dataset training action
- [x] Add export controls (JSON/CSV)
- [x] Add export download or file management UI

---

## Recommended Next Step

All remaining frontend gaps are now covered in the dashboard implementation, so the next step is a focused regression pass and product polish rather than structural feature work.

The dashboard now includes:
- live runtime and blocker visibility
- broker management controls
- MT5 error-log troubleshooting
- account and risk configuration
- trade sync and ML export surfaces

This closes the active frontend parity backlog for the current backend API contract.

---

## Summary

The project is in a stable state from the backend and architecture perspective, and the dashboard is already functional for core monitoring. The remaining work is primarily about frontend parity with the backend API contract and operational controls, not about reworking the core trading engine.
