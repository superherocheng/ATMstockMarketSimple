"""Create financial_factor table for financial quality factor data.

Revision ID: 004
Revises: 003
Create Date: 2026-05-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create financial_factor table."""
    op.create_table(
        "financial_factor",
        sa.Column("ts_code", sa.String(), nullable=False),
        sa.Column("calc_date", sa.String(), nullable=False),
        sa.Column("f_roe", sa.Float(), nullable=True, comment="ROE因子值 (Z-scored)"),
        sa.Column("f_pb_pct", sa.Float(), nullable=True, comment="PB估值分位因子 (1-pct, Z-scored)"),
        sa.Column("f_earnings_yoy", sa.Float(), nullable=True, comment="盈利加速度因子 (Z-scored)"),
        sa.Column("f_quality", sa.Float(), nullable=True, comment="复合财务质量因子 (Z-scored)"),
        sa.Column("is_commodity", sa.Boolean(), nullable=True, default=False,
                  comment="是否为商品类ETF"),
        sa.Column("num_constituents", sa.Integer(), nullable=True, default=0,
                  comment="有效成分股数量"),
        sa.Column("missing_constituents", sa.Integer(), nullable=True, default=0,
                  comment="数据缺失的成分股数量"),
        sa.PrimaryKeyConstraint("ts_code", "calc_date"),
    )
    op.create_index("idx_financial_factor_calc_date", "financial_factor", ["calc_date"])
    op.create_index("idx_financial_factor_ts_code", "financial_factor", ["ts_code"])


def downgrade() -> None:
    """Drop financial_factor table."""
    op.drop_index("idx_financial_factor_calc_date", table_name="financial_factor")
    op.drop_index("idx_financial_factor_ts_code", table_name="financial_factor")
    op.drop_table("financial_factor")
