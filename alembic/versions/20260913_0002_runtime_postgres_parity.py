"""runtime postgres parity

Revision ID: 20260913_0002
Revises: 20260913_0001
Create Date: 2026-09-13 00:01:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260913_0002"
down_revision = "20260913_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.account_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            balance DOUBLE PRECISION DEFAULT 1000,
            initial_balance DOUBLE PRECISION DEFAULT 1000,
            enable_real_trade BOOLEAN DEFAULT FALSE,
            auto_trade_enabled BOOLEAN DEFAULT FALSE,
            keep_terminal_alive BOOLEAN DEFAULT FALSE,
            data_feed_broker_id INTEGER,
            auto_analytic_tpsl BOOLEAN DEFAULT FALSE,
            tp_value DOUBLE PRECISION DEFAULT 0.5,
            sl_value DOUBLE PRECISION,
            lot DOUBLE PRECISION DEFAULT 0.01,
            max_open_trades INTEGER DEFAULT 1,
            auto_trade_symbol VARCHAR(50) DEFAULT 'XAUUSD',
            auto_trade_interval_sec INTEGER DEFAULT 2,
            trade_history_sync_days INTEGER DEFAULT 90,
            trade_history_sync_all BOOLEAN DEFAULT FALSE,
            auto_trade_risk_mode VARCHAR(50) DEFAULT 'fixed_lot',
            auto_trade_risk_percent DOUBLE PRECISION DEFAULT 1.0,
            auto_trade_use_account_balance BOOLEAN DEFAULT TRUE,
            auto_trade_use_available_margin BOOLEAN DEFAULT TRUE,
            auto_trade_min_free_margin_pct DOUBLE PRECISION DEFAULT 30,
            auto_trade_max_margin_usage_pct DOUBLE PRECISION DEFAULT 70,
            auto_trade_max_spread_points INTEGER DEFAULT 120,
            auto_trade_min_signal_score DOUBLE PRECISION DEFAULT 0.55,
            auto_trade_allow_sell BOOLEAN DEFAULT TRUE,
            auto_trade_cooldown_sec INTEGER DEFAULT 30,
            auto_trade_session_start_hour INTEGER DEFAULT 0,
            auto_trade_session_end_hour INTEGER DEFAULT 24,
            auto_trade_use_atr_tpsl BOOLEAN DEFAULT TRUE,
            auto_trade_atr_period INTEGER DEFAULT 14,
            auto_trade_atr_sl_mult DOUBLE PRECISION DEFAULT 1.5,
            auto_trade_atr_tp_mult DOUBLE PRECISION DEFAULT 2.5,
            auto_trade_trailing_enabled BOOLEAN DEFAULT TRUE,
            auto_trade_trailing_activation_rr DOUBLE PRECISION DEFAULT 1.0,
            auto_trade_trailing_atr_mult DOUBLE PRECISION DEFAULT 1.0,
            auto_trade_confidence_model VARCHAR(50) DEFAULT 'weighted',
            auto_trade_confidence_threshold DOUBLE PRECISION DEFAULT 0.6,
            auto_trade_timeframes VARCHAR(200) DEFAULT 'M1,M5,M15,M30',
            auto_trade_tf_weight_m1 DOUBLE PRECISION DEFAULT 0.35,
            auto_trade_tf_weight_m5 DOUBLE PRECISION DEFAULT 0.30,
            auto_trade_tf_weight_m15 DOUBLE PRECISION DEFAULT 0.20,
            auto_trade_tf_weight_m30 DOUBLE PRECISION DEFAULT 0.15,
            auto_trade_partial_tp_enabled BOOLEAN DEFAULT TRUE,
            auto_trade_partial_tp_rr1 DOUBLE PRECISION DEFAULT 1.0,
            auto_trade_partial_tp_close_pct1 DOUBLE PRECISION DEFAULT 40.0,
            auto_trade_partial_tp_rr2 DOUBLE PRECISION DEFAULT 2.0,
            auto_trade_partial_tp_close_pct2 DOUBLE PRECISION DEFAULT 35.0,
            auto_trade_break_even_enabled BOOLEAN DEFAULT TRUE,
            auto_trade_break_even_rr DOUBLE PRECISION DEFAULT 1.0,
            auto_trade_break_even_offset_atr_mult DOUBLE PRECISION DEFAULT 0.1,
            auto_trade_trailing_mode VARCHAR(50) DEFAULT 'stateful_hl',
            auto_trade_stateful_trail_buffer_atr_mult DOUBLE PRECISION DEFAULT 0.5,
            auto_trade_protective_mode VARCHAR(50) DEFAULT 'broker_sl',
            auto_trade_min_hold_sec INTEGER DEFAULT 15,
            auto_trade_reversal_confirm_cycles INTEGER DEFAULT 2
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.trade_history (
            id SERIAL PRIMARY KEY,
            trade_id VARCHAR(200),
            status VARCHAR(32),
            type VARCHAR(32),
            symbol VARCHAR(64),
            lot DOUBLE PRECISION,
            ticket INTEGER,
            entry DOUBLE PRECISION,
            exit DOUBLE PRECISION,
            profit DOUBLE PRECISION,
            entryTime BIGINT,
            exitTime BIGINT,
            reason TEXT,
            tpValue DOUBLE PRECISION,
            slValue DOUBLE PRECISION,
            broker_id INTEGER,
            broker_name VARCHAR(200),
            account_id INTEGER,
            platform VARCHAR(64),
            execution_mode VARCHAR(50),
            terminal_path TEXT,
            trailing_mode VARCHAR(50),
            risk_mode VARCHAR(50),
            signal_score DOUBLE PRECISION,
            spread_points INTEGER,
            margin_usage_pct DOUBLE PRECISION,
            equity DOUBLE PRECISION,
            balance DOUBLE PRECISION,
            atr_value DOUBLE PRECISION,
            session_hour INTEGER,
            signal_context_json TEXT,
            strategy_name VARCHAR(200),
            strategy_revision INTEGER,
            target_price DOUBLE PRECISION,
            target_factor DOUBLE PRECISION,
            target_hit INTEGER,
            overshoot_before_close DOUBLE PRECISION,
            force_close_after_target_crossed INTEGER,
            mfe_price_distance DOUBLE PRECISION,
            mae_price_distance DOUBLE PRECISION,
            time_to_close_sec INTEGER,
            target_first_crossed_at BIGINT,
            time_to_target_cross_sec INTEGER,
            open_event_id INTEGER,
            close_event_id INTEGER,
            tp_sl_mode VARCHAR(32)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.mt5_error_log (
            id SERIAL PRIMARY KEY,
            timestamp BIGINT,
            message TEXT,
            broker_id INTEGER,
            broker_name VARCHAR(200),
            account_id INTEGER
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.account_transactions (
            id SERIAL PRIMARY KEY,
            type VARCHAR(32),
            amount DOUBLE PRECISION,
            note TEXT,
            timestamp BIGINT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.auto_trade_profiles (
            id SERIAL PRIMARY KEY,
            broker_id INTEGER NOT NULL,
            account_id INTEGER NOT NULL,
            profile_json TEXT NOT NULL,
            created_at BIGINT NOT NULL,
            updated_at BIGINT NOT NULL,
            UNIQUE (broker_id, account_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.auto_trade_profile_history (
            id SERIAL PRIMARY KEY,
            broker_id INTEGER NOT NULL,
            account_id INTEGER NOT NULL,
            profile_json TEXT NOT NULL,
            note TEXT,
            source VARCHAR(100),
            created_at BIGINT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.auto_trade_risk_policy (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            policy_json TEXT NOT NULL,
            updated_at BIGINT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.auto_trade_events (
            id SERIAL PRIMARY KEY,
            timestamp BIGINT NOT NULL,
            broker_id INTEGER,
            broker_name VARCHAR(200),
            account_id INTEGER,
            symbol VARCHAR(64),
            trade_id VARCHAR(200),
            event_type VARCHAR(100) NOT NULL,
            decision VARCHAR(100),
            reason TEXT,
            signal TEXT,
            signal_score DOUBLE PRECISION,
            spread_points INTEGER,
            max_spread_points INTEGER,
            margin_free DOUBLE PRECISION,
            equity DOUBLE PRECISION,
            balance DOUBLE PRECISION,
            margin_usage_pct DOUBLE PRECISION,
            atr_value DOUBLE PRECISION,
            trailing_mode VARCHAR(50),
            risk_mode VARCHAR(50),
            lot_mode VARCHAR(50),
            lot DOUBLE PRECISION,
            profit DOUBLE PRECISION,
            rr DOUBLE PRECISION,
            session_hour INTEGER,
            strategy_name VARCHAR(200),
            strategy_revision INTEGER,
            payload_json TEXT,
            decision_source VARCHAR(100),
            strategy_meta_json TEXT,
            constraints_json TEXT,
            signal_snapshot_json TEXT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.auto_trade_strategy_versions (
            id SERIAL PRIMARY KEY,
            strategy_name VARCHAR(200) NOT NULL,
            revision INTEGER NOT NULL,
            broker_id INTEGER,
            account_id INTEGER,
            config_json TEXT NOT NULL,
            note TEXT,
            source VARCHAR(100),
            created_at BIGINT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_auto_trade_strategy_versions_name_scope
        ON public.auto_trade_strategy_versions(strategy_name, broker_id, account_id, revision)
        """
    )
    op.execute(
        """
        INSERT INTO public.auto_trade_risk_policy (id, policy_json, updated_at)
        VALUES (1, '{"auto_trade_risk_selector_strategy": "manual", "auto_trade_risk_atr_threshold": 12.0, "auto_trade_risk_balance_fixed_threshold": 500.0, "auto_trade_risk_confidence_threshold": 0.7, "auto_trade_risk_spread_fixed_threshold": 120, "auto_trade_risk_spread_low_threshold": 60, "auto_trade_risk_hybrid_addon_rr_threshold": 2.0, "auto_trade_risk_hybrid_entry_mode": "risk_percent", "auto_trade_risk_hybrid_addon_mode": "balance_scaled", "auto_trade_risk_adaptive_window_days": 90, "auto_trade_risk_adaptive_min_trades": 12, "hedge_enabled": true, "hedge_threshold": -0.05, "hedge_slots": 2}', EXTRACT(EPOCH FROM CURRENT_TIMESTAMP)::BIGINT)
        ON CONFLICT (id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.auto_trade_strategy_versions CASCADE")
    op.execute("DROP TABLE IF EXISTS public.auto_trade_events CASCADE")
    op.execute("DROP TABLE IF EXISTS public.auto_trade_risk_policy CASCADE")
    op.execute("DROP TABLE IF EXISTS public.auto_trade_profile_history CASCADE")
    op.execute("DROP TABLE IF EXISTS public.auto_trade_profiles CASCADE")
    op.execute("DROP TABLE IF EXISTS public.account_transactions CASCADE")
    op.execute("DROP TABLE IF EXISTS public.mt5_error_log CASCADE")
    op.execute("DROP TABLE IF EXISTS public.trade_history CASCADE")
    op.execute("DROP TABLE IF EXISTS public.account_state CASCADE")
