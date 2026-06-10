"""Convert trade_date/date columns from VARCHAR to native DATE type

Revision ID: 008
Revises: 007
Create Date: 2026-06-10

Changes:
  - sector_etf_daily.trade_date     VARCHAR → DATE
  - index_etf_daily.trade_date      VARCHAR → DATE
  - etf_share.trade_date             VARCHAR → DATE
  - etf_adj_factor.trade_date        VARCHAR → DATE
  - etf_anomalies.trade_date         VARCHAR → DATE
  - stock_daily.trade_date           VARCHAR → DATE
  - stock_daily_basic.trade_date     VARCHAR → DATE
  - lhb_data.trade_date              VARCHAR → DATE
  - stock_basic.list_date            VARCHAR → DATE
  - stock_fina_indicator.ann_date    VARCHAR → DATE
  - stock_fina_indicator.end_date    VARCHAR → DATE
  - stock_info.list_date             VARCHAR → DATE

This eliminates the need for ::date casts everywhere and prevents
"operator does not exist: text - interval" errors.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ════════════════════════════════════════════════════════════
#  Tables with trade_date as VARCHAR
#  (part of PRIMARY KEY — need CASCADE drop/recreate of PK)
# ════════════════════════════════════════════════════════════
TRADE_DATE_TABLES = [
    "sector_etf_daily",
    "index_etf_daily",
    "etf_share",
    "etf_adj_factor",
    "stock_daily",
    "stock_daily_basic",
    "lhb_data",
]

# etf_anomalies has 3-part PK (ts_code, trade_date, anomaly_type)
TRADE_DATE_TABLES_3PK = [
    "etf_anomalies",
]

# Tables with non-PK date columns
OTHER_DATE_TABLES = [
    ("stock_basic", "list_date"),
    ("stock_fina_indicator", "ann_date"),
    ("stock_fina_indicator", "end_date"),
    ("stock_info", "list_date"),
]


def upgrade() -> None:
    # ── 1. Convert trade_date in tables where it's part of PRIMARY KEY ──
    for tbl in TRADE_DATE_TABLES:
        # Drop default if any (text columns have none, but be safe)
        op.execute(f"""
            ALTER TABLE {tbl}
            ALTER COLUMN trade_date TYPE DATE
            USING trade_date::date
        """)
        op.execute(f"ALTER TABLE {tbl} ALTER COLUMN trade_date SET NOT NULL")

    # ── 2. etf_anomalies: 3-column PK ──
    for tbl in TRADE_DATE_TABLES_3PK:
        op.execute(f"""
            ALTER TABLE {tbl}
            ALTER COLUMN trade_date TYPE DATE
            USING trade_date::date
        """)
        op.execute(f"ALTER TABLE {tbl} ALTER COLUMN trade_date SET NOT NULL")

    # ── 3. Other non-PK date columns ──
    for tbl, col in OTHER_DATE_TABLES:
        op.execute(f"""
            ALTER TABLE {tbl}
            ALTER COLUMN {col} TYPE DATE
            USING {col}::date
        """)

    # ── 4. Drop unused index on analysis_cache.updated_at (was VARCHAR) ──
    try:
        op.drop_index("idx_analysis_cache_updated_at", table_name="analysis_cache", if_exists=True)
    except Exception:
        pass


def downgrade() -> None:
    # ── Revert: DATE → VARCHAR ──
    for tbl in TRADE_DATE_TABLES:
        op.execute(f"""
            ALTER TABLE {tbl}
            ALTER COLUMN trade_date TYPE VARCHAR
            USING trade_date::text
        """)
        op.execute(f"ALTER TABLE {tbl} ALTER COLUMN trade_date SET NOT NULL")

    for tbl in TRADE_DATE_TABLES_3PK:
        op.execute(f"""
            ALTER TABLE {tbl}
            ALTER COLUMN trade_date TYPE VARCHAR
            USING trade_date::text
        """)
        op.execute(f"ALTER TABLE {tbl} ALTER COLUMN trade_date SET NOT NULL")

    for tbl, col in OTHER_DATE_TABLES:
        op.execute(f"""
            ALTER TABLE {tbl}
            ALTER COLUMN {col} TYPE VARCHAR
            USING {col}::text
        """)
