"""create brokers table

Revision ID: 20260913_0001
Revises:
Create Date: 2026-09-13 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260913_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.brokers (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            platform VARCHAR(50) NOT NULL DEFAULT 'mt5',
            terminal_path TEXT,
            execution_mode VARCHAR(50) DEFAULT 'mouse',
            window_hint TEXT,
            default_symbol VARCHAR(50) DEFAULT 'XAUUSD',
            is_default BOOLEAN DEFAULT FALSE,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        ALTER TABLE public.brokers
            ADD COLUMN IF NOT EXISTS default_symbol VARCHAR(50) DEFAULT 'XAUUSD';
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.brokers CASCADE")
