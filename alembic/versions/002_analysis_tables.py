"""Add analysis tables for factor computation and IC analysis.

Revision ID: 002
Revises: 001
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def _create_table(table_name, *columns, **kwargs):
    op.create_table(table_name, *columns, if_not_exists=True, **kwargs)


def _create_index(index_name, table_name, *columns):
    op.create_index(index_name, table_name, columns, if_not_exists=True)


def upgrade():
    _create_table(
        "factor_daily",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("etf_code", sa.String(20), nullable=False),
        sa.Column("trade_date", sa.Date, nullable=False),
        sa.Column("preset_id", sa.String(20), nullable=False),
        sa.Column("flow", sa.Float),
        sa.Column("mom", sa.Float),
        sa.Column("z_flow", sa.Float),
        sa.Column("z_mom", sa.Float),
        sa.Column("factor", sa.Float),
        sa.Column("quadrant", sa.SmallInteger),
        sa.UniqueConstraint("etf_code", "trade_date", "preset_id", name="uq_factor_daily"),
    )
    _create_index("idx_factor_date_preset", "factor_daily", "trade_date", "preset_id")
    _create_index("idx_factor_etf_preset", "factor_daily", "etf_code", "preset_id")

    _create_table(
        "ic_daily",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("trade_date", sa.Date, nullable=False),
        sa.Column("preset_id", sa.String(20), nullable=False),
        sa.Column("forward_days", sa.SmallInteger, nullable=False),
        sa.Column("ic_value", sa.Float),
        sa.Column("forward_ret_mean", sa.Float),
        sa.UniqueConstraint("trade_date", "preset_id", "forward_days", name="uq_ic_daily"),
    )
    _create_index("idx_ic_daily_preset_fwd", "ic_daily", "preset_id", "forward_days")

    _create_table(
        "ic_summary",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("preset_id", sa.String(20), nullable=False),
        sa.Column("forward_days", sa.SmallInteger, nullable=False),
        sa.Column("ic_mean", sa.Float),
        sa.Column("ic_std", sa.Float),
        sa.Column("icir", sa.Float),
        sa.Column("ic_win_rate", sa.Float),
        sa.Column("sample_count", sa.Integer),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("preset_id", "forward_days", name="uq_ic_summary"),
    )

    _create_table(
        "quadrant_perf",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("trade_date", sa.Date, nullable=False),
        sa.Column("preset_id", sa.String(20), nullable=False),
        sa.Column("forward_days", sa.SmallInteger, nullable=False),
        sa.Column("quadrant", sa.SmallInteger, nullable=False),
        sa.Column("avg_forward_ret", sa.Float),
        sa.Column("etf_count", sa.SmallInteger),
        sa.UniqueConstraint("trade_date", "preset_id", "forward_days", "quadrant", name="uq_quadrant_perf"),
    )
    _create_index("idx_qp_date_preset", "quadrant_perf", "trade_date", "preset_id")


def downgrade():
    for idx in [
        "idx_qp_date_preset",
        "idx_ic_daily_preset_fwd",
        "idx_factor_etf_preset",
        "idx_factor_date_preset",
    ]:
        op.drop_index(idx, if_exists=True)
    for tbl in ["quadrant_perf", "ic_summary", "ic_daily", "factor_daily"]:
        op.drop_table(tbl, if_exists=True)
