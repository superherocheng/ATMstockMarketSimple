"""Initial schema — 从 init_db() 提取的完整数据库结构

Revision ID: 001
Revises: None
Create Date: 2026-07-18

包含所有核心表：
  - ETF 日线 (index_etf_daily, sector_etf_daily)
  - ETF 份额 (etf_share)
  - ETF 复权因子 (etf_adj_factor)
  - ETF 异常 (etf_anomalies)
  - 个股日线 (stock_daily)
  - 个股基本信息 (stock_basic)
  - 每日估值 (stock_daily_basic)
  - 财务指标 (stock_fina_indicator)
  - 行业分类 (stock_info)
  - 概念板块 (concept_dict, stock_concept)
  - 缓存表 (analysis_cache, precomputed_cache)
  - 龙虎榜 (lhb_data)
  - 性能索引 (8 个)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ══════════════════════════════════════════════════
#  Helper: create table with IF NOT EXISTS
# ══════════════════════════════════════════════════
def _create_table(name, *cols, **kw):
    """建表（带 IF NOT EXISTS 兼容性）"""
    op.create_table(name, *cols, if_not_exists=True, **kw)


def _create_index(name, table, cols, **kw):
    """建索引（带 IF NOT EXISTS 兼容性）"""
    op.create_index(name, table, cols, if_not_exists=True, **kw)


def upgrade() -> None:
    # ── ETF 日线 ──
    _create_table(
        "index_etf_daily",
        sa.Column("ts_code", sa.String(), nullable=False),
        sa.Column("trade_date", sa.String(), nullable=False),
        sa.Column("open", sa.Float()),
        sa.Column("high", sa.Float()),
        sa.Column("low", sa.Float()),
        sa.Column("close", sa.Float()),
        sa.Column("vol", sa.Float()),
        sa.Column("amount", sa.Float()),
        sa.Column("pre_close", sa.Float()),
        sa.Column("pct_chg", sa.Float()),
        sa.PrimaryKeyConstraint("ts_code", "trade_date"),
    )

    _create_table(
        "sector_etf_daily",
        sa.Column("ts_code", sa.String(), nullable=False),
        sa.Column("trade_date", sa.String(), nullable=False),
        sa.Column("open", sa.Float()),
        sa.Column("high", sa.Float()),
        sa.Column("low", sa.Float()),
        sa.Column("close", sa.Float()),
        sa.Column("vol", sa.Float()),
        sa.Column("amount", sa.Float()),
        sa.Column("pre_close", sa.Float()),
        sa.Column("pct_chg", sa.Float()),
        sa.PrimaryKeyConstraint("ts_code", "trade_date"),
    )

    # ── ETF 份额 ──
    _create_table(
        "etf_share",
        sa.Column("ts_code", sa.String(), nullable=False),
        sa.Column("trade_date", sa.String(), nullable=False),
        sa.Column("fd_share", sa.Float()),
        sa.PrimaryKeyConstraint("ts_code", "trade_date"),
    )

    # ── ETF 复权因子 (P2.6) ──
    _create_table(
        "etf_adj_factor",
        sa.Column("ts_code", sa.String(), nullable=False),
        sa.Column("trade_date", sa.String(), nullable=False),
        sa.Column("adj_factor", sa.Float()),
        sa.PrimaryKeyConstraint("ts_code", "trade_date"),
    )

    # ── ETF 异常 ──
    _create_table(
        "etf_anomalies",
        sa.Column("ts_code", sa.String(), nullable=False),
        sa.Column("trade_date", sa.String(), nullable=False),
        sa.Column("anomaly_type", sa.String(), nullable=False),
        sa.Column("z_score", sa.Float()),
        sa.Column("value", sa.Float()),
        sa.PrimaryKeyConstraint("ts_code", "trade_date", "anomaly_type"),
    )

    # ── 个股日线 ──
    _create_table(
        "stock_daily",
        sa.Column("ts_code", sa.String(), nullable=False),
        sa.Column("trade_date", sa.String(), nullable=False),
        sa.Column("open", sa.Float()),
        sa.Column("high", sa.Float()),
        sa.Column("low", sa.Float()),
        sa.Column("close", sa.Float()),
        sa.Column("vol", sa.Float()),
        sa.Column("amount", sa.Float()),
        sa.Column("pre_close", sa.Float()),
        sa.Column("pct_chg", sa.Float()),
        sa.PrimaryKeyConstraint("ts_code", "trade_date"),
    )

    # ── 个股基本信息 ──
    _create_table(
        "stock_basic",
        sa.Column("ts_code", sa.String(), nullable=False),
        sa.Column("name", sa.String()),
        sa.Column("industry", sa.String()),
        sa.Column("area", sa.String()),
        sa.Column("market", sa.String()),
        sa.Column("list_date", sa.String()),
        sa.PrimaryKeyConstraint("ts_code"),
    )

    # ── 每日估值 ──
    _create_table(
        "stock_daily_basic",
        sa.Column("ts_code", sa.String(), nullable=False),
        sa.Column("trade_date", sa.String(), nullable=False),
        sa.Column("pe", sa.Float()),
        sa.Column("pe_ttm", sa.Float()),
        sa.Column("pb", sa.Float()),
        sa.Column("ps", sa.Float()),
        sa.Column("ps_ttm", sa.Float()),
        sa.Column("total_mv", sa.Float()),
        sa.Column("circ_mv", sa.Float()),
        sa.Column("turnover_rate", sa.Float()),
        sa.PrimaryKeyConstraint("ts_code", "trade_date"),
    )

    # ── 财务指标 ──
    _create_table(
        "stock_fina_indicator",
        sa.Column("ts_code", sa.String(), nullable=False),
        sa.Column("ann_date", sa.String()),
        sa.Column("end_date", sa.String(), nullable=False),
        sa.Column("roe", sa.Float()),
        sa.Column("netprofit_yoy", sa.Float()),
        sa.Column("tr_yoy", sa.Float()),
        sa.Column("grossprofit_margin", sa.Float()),
        sa.Column("netprofit_margin", sa.Float()),
        sa.Column("eps", sa.Float()),
        sa.Column("debt_to_assets", sa.Float()),
        sa.Column("current_ratio", sa.Float()),
        sa.PrimaryKeyConstraint("ts_code", "end_date"),
    )

    # ── 缓存表 ──
    _create_table(
        "analysis_cache",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String()),
        sa.Column("data_json", sa.String()),
        sa.PrimaryKeyConstraint("key"),
    )

    _create_table(
        "precomputed_cache",
        sa.Column("cache_key", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String()),
        sa.Column("data_json", sa.Text()),
        sa.PrimaryKeyConstraint("cache_key"),
    )

    # ── 行业分类 ──
    _create_table(
        "stock_info",
        sa.Column("ts_code", sa.String(), nullable=False),
        sa.Column("name", sa.String()),
        sa.Column("area", sa.String()),
        sa.Column("market", sa.String()),
        sa.Column("list_date", sa.String()),
        sa.Column("sw_level1", sa.String()),
        sa.Column("sw_level2", sa.String()),
        sa.Column("sw_level3", sa.String()),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("ts_code"),
    )

    # ── 概念板块 ──
    _create_table(
        "concept_dict",
        sa.Column("concept_id", sa.Integer(), nullable=False),
        sa.Column("concept_name", sa.String(), nullable=False, unique=True),
        sa.Column("concept_category", sa.String()),
        sa.PrimaryKeyConstraint("concept_id"),
    )

    _create_table(
        "stock_concept",
        sa.Column("ts_code", sa.String(), nullable=False),
        sa.Column("concept_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("ts_code", "concept_id"),
    )

    # ── 龙虎榜 ──
    _create_table(
        "lhb_data",
        sa.Column("ts_code", sa.String(), nullable=False),
        sa.Column("trade_date", sa.String(), nullable=False),
        sa.Column("buy_amount", sa.Float()),
        sa.Column("sell_amount", sa.Float()),
        sa.Column("net_amount", sa.Float()),
        sa.PrimaryKeyConstraint("ts_code", "trade_date"),
    )

    # ══════════════════════════════════════════════
    #  索引
    # ══════════════════════════════════════════════
    _create_index("idx_stock_concept_code", "stock_concept", ["ts_code"])
    _create_index("idx_stock_concept_id", "stock_concept", ["concept_id"])
    _create_index("idx_stock_info_sw1", "stock_info", ["sw_level1"])
    _create_index("idx_stock_info_sw2", "stock_info", ["sw_level2"])
    _create_index("idx_stock_info_sw3", "stock_info", ["sw_level3"])

    # P0.2: Performance-critical indexes
    _create_index("idx_sd_code_date", "stock_daily", ["ts_code", "trade_date"])
    _create_index("idx_sdb_date_mv_pe", "stock_daily_basic", ["trade_date", "total_mv", "pe_ttm", "pb"])
    _create_index("idx_sd_date", "stock_daily", ["trade_date"])
    _create_index("idx_sdb_code_date", "stock_daily_basic", ["ts_code", "trade_date"])
    _create_index("idx_etf_adj_code_date", "etf_adj_factor", ["ts_code", "trade_date"])


def downgrade() -> None:
    """回滚：删除所有表（逆序避免外键问题）"""
    # 索引会在删表时自动删除，但显式删除更清洁
    op.drop_index("idx_sdb_code_date", table_name="stock_daily_basic", if_exists=True)
    op.drop_index("idx_sd_date", table_name="stock_daily", if_exists=True)
    op.drop_index("idx_sdb_date_mv_pe", table_name="stock_daily_basic", if_exists=True)
    op.drop_index("idx_sd_code_date", table_name="stock_daily", if_exists=True)
    op.drop_index("idx_etf_adj_code_date", table_name="etf_adj_factor", if_exists=True)
    op.drop_index("idx_stock_info_sw3", table_name="stock_info", if_exists=True)
    op.drop_index("idx_stock_info_sw2", table_name="stock_info", if_exists=True)
    op.drop_index("idx_stock_info_sw1", table_name="stock_info", if_exists=True)
    op.drop_index("idx_stock_concept_id", table_name="stock_concept", if_exists=True)
    op.drop_index("idx_stock_concept_code", table_name="stock_concept", if_exists=True)

    # 删表
    tables = [
        "lhb_data",
        "stock_concept",
        "concept_dict",
        "stock_info",
        "precomputed_cache",
        "analysis_cache",
        "stock_fina_indicator",
        "stock_daily_basic",
        "stock_basic",
        "stock_daily",
        "etf_anomalies",
        "etf_adj_factor",
        "etf_share",
        "sector_etf_daily",
        "index_etf_daily",
    ]
    for table in tables:
        op.drop_table(table, if_exists=True)
