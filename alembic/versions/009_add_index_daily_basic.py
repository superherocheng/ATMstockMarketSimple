"""Add index_daily_basic table (index valuation PE/PB for thermometer page)

Revision ID: 009
Revises: 008
Create Date: 2026-08-24

Changes:
  - New table index_daily_basic: 指数估值 (Tushare index_dailybasic)
    ts_code / trade_date DATE / pe / pb — 用于大盘温度计的估值分位面板。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "009"
down_revision: str = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS index_daily_basic (
            ts_code VARCHAR,
            trade_date DATE,
            pe DOUBLE PRECISION,
            pb DOUBLE PRECISION,
            PRIMARY KEY (ts_code, trade_date)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_index_daily_basic_code_date "
        "ON index_daily_basic(ts_code, trade_date)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS index_daily_basic")
