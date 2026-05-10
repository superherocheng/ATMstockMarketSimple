# 可视化分析模块 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "可视化分析" module to the ATMstockMarket website that computes sector ETF four-quadrant factors, runs IC analysis, and presents 7 interactive ECharts visualizations with investment guidance.

**Architecture:** New `src/analysis/` Python package for factor computation and IC analysis, 4 new DB tables via Alembic migration, a new FastAPI router serving pre-computed results, and a new Jinja2 template rendering ECharts. Computation runs during the existing data fetch pipeline.

**Tech Stack:** Python (pandas, numpy, scipy.stats.spearmanr), FastAPI, SQLAlchemy, Alembic, ECharts 5, Jinja2

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `src/analysis/__init__.py` | Package init |
| `src/analysis/presets.py` | Preset parameter definitions |
| `src/analysis/factor_engine.py` | Flow/Mom/Z-score/Factor computation |
| `src/analysis/ic_analyzer.py` | IC series, ICIR, IC decay, rolling ICIR |
| `src/analysis/chart_builder.py` | DB results → ECharts JSON transformers |
| `src/web/routers/analysis.py` | FastAPI routes for analysis module |
| `src/web/templates/analysis.html` | Full page template with inline ECharts JS |
| `alembic/versions/002_analysis_tables.py` | Migration for factor_daily, ic_daily, ic_summary, quadrant_perf |
| `tests/unit/test_factor_engine.py` | Tests for factor computation |
| `tests/unit/test_ic_analyzer.py` | Tests for IC analysis |

### Modified Files

| File | Change |
|------|--------|
| `requirements.txt` | Add `scipy>=1.11.0` |
| `pyproject.toml` | Add `scipy>=1.11.0` to dependencies |
| `src/web/app.py` | Import and register `analysis` router |
| `src/web/routers/fetch.py` | Trigger analysis recomputation after fetch |
| `src/web/services/cache.py` | Add "analysis" cache category |
| `src/web/templates/index.html` | Add nav link |
| `src/web/templates/etf.html` | Add nav link |
| `src/web/templates/sector.html` | Add nav link |

---

## Task 1: Dependencies + Alembic Migration

**Files:**
- Modify: `requirements.txt`
- Modify: `pyproject.toml`
- Create: `alembic/versions/002_analysis_tables.py`

- [ ] **Step 1: Add scipy to requirements.txt**

Append this line to `requirements.txt`:
```
scipy>=1.11.0
```

- [ ] **Step 2: Add scipy to pyproject.toml**

Add `scipy>=1.11.0` to the `dependencies` list in `pyproject.toml`, after the `numpy` entry.

- [ ] **Step 3: Install scipy**

Run: `pip install scipy>=1.11.0`
Expected: Successfully installed

- [ ] **Step 4: Write the Alembic migration**

Create `alembic/versions/002_analysis_tables.py`:

```python
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
```

- [ ] **Step 5: Run the migration**

Run: `cd /Users/atmbrandnew/Desktop/SOLOProject/ATMstockMarketSimple && alembic upgrade head`
Expected: Running upgrade 001 -> 002, done.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt pyproject.toml alembic/versions/002_analysis_tables.py
git commit -m "feat: add analysis DB tables and scipy dependency"
```

---

## Task 2: Presets Module

**Files:**
- Create: `src/analysis/__init__.py`
- Create: `src/analysis/presets.py`

- [ ] **Step 1: Create `src/analysis/__init__.py`**

```python
"""Sector ETF four-quadrant factor analysis package."""
```

- [ ] **Step 2: Create `src/analysis/presets.py`**

```python
"""Factor analysis parameter presets."""

PRESETS = {
    "short": {
        "id": "short",
        "label": "短期",
        "description": "N=10, M=20 — 适合短线因子验证",
        "flow_lookback": 10,
        "mom_lookback": 20,
        "forward_periods": [1, 5, 10, 20],
    },
    "medium": {
        "id": "medium",
        "label": "中期",
        "description": "N=20, M=60 — 适合中线持仓参考",
        "flow_lookback": 20,
        "mom_lookback": 60,
        "forward_periods": [1, 5, 10, 20, 40, 60],
    },
    "long": {
        "id": "long",
        "label": "长期",
        "description": "N=40, M=120 — 适合长周期趋势判断",
        "flow_lookback": 40,
        "mom_lookback": 120,
        "forward_periods": [5, 10, 20, 40, 60],
    },
}

DEFAULT_PRESET = "short"


def get_preset(preset_id: str) -> dict:
    """Return preset config or the default if not found."""
    return PRESETS.get(preset_id, PRESETS[DEFAULT_PRESET])


def all_preset_ids() -> list:
    """Return all preset IDs in display order."""
    return ["short", "medium", "long"]
```

- [ ] **Step 3: Verify imports work**

Run: `python -c "from src.analysis.presets import PRESETS, get_preset; print(get_preset('short')['label'])"`
Expected: 短期

- [ ] **Step 4: Commit**

```bash
git add src/analysis/__init__.py src/analysis/presets.py
git commit -m "feat: add analysis presets module"
```

---

## Task 3: Factor Engine + Tests

**Files:**
- Create: `src/analysis/factor_engine.py`
- Create: `tests/unit/test_factor_engine.py`

### Part A: Tests

- [ ] **Step 1: Write test file `tests/unit/test_factor_engine.py`**

```python
"""因子引擎单元测试"""
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock


class TestComputeFlow:
    """测试 Flow (份额趋势) 计算"""

    def test_rising_shares_positive_flow(self):
        """持续增长的份额 → 正 Flow"""
        from src.analysis.factor_engine import _compute_flow

        shares = pd.Series([100, 102, 104, 106, 108, 110, 112, 114, 116, 118],
                           name="fd_share")
        flow = _compute_flow(shares, lookback=10)
        assert flow > 0

    def test_declining_shares_negative_flow(self):
        """持续减少的份额 → 负 Flow"""
        from src.analysis.factor_engine import _compute_flow

        shares = pd.Series([120, 118, 116, 114, 112, 110, 108, 106, 104, 102],
                           name="fd_share")
        flow = _compute_flow(shares, lookback=10)
        assert flow < 0

    def test_insufficient_data_returns_nan(self):
        """数据不足 → NaN"""
        from src.analysis.factor_engine import _compute_flow

        shares = pd.Series([100, 102], name="fd_share")
        flow = _compute_flow(shares, lookback=10)
        assert pd.isna(flow)


class TestComputeMom:
    """测试 Momentum (价格动量) 计算"""

    def test_rising_price_positive_mom(self):
        """价格上涨 → 正动量"""
        from src.analysis.factor_engine import _compute_mom

        closes = pd.Series([10.0, 10.5, 11.0, 11.5, 12.0, 12.5, 13.0, 13.5, 14.0, 14.5,
                            15.0, 15.5, 16.0, 16.5, 17.0, 17.5, 18.0, 18.5, 19.0, 19.5,
                            20.0], name="close")
        mom = _compute_mom(closes, lookback=20)
        assert mom > 0

    def test_falling_price_negative_mom(self):
        """价格下跌 → 负动量"""
        from src.analysis.factor_engine import _compute_mom

        closes = pd.Series([20.0, 19.5, 19.0, 18.5, 18.0, 17.5, 17.0, 16.5, 16.0, 15.5,
                            15.0, 14.5, 14.0, 13.5, 13.0, 12.5, 12.0, 11.5, 11.0, 10.5,
                            10.0], name="close")
        mom = _compute_mom(closes, lookback=20)
        assert mom < 0

    def test_insufficient_data_returns_nan(self):
        """数据不足 → NaN"""
        from src.analysis.factor_engine import _compute_mom

        closes = pd.Series([10.0, 11.0], name="close")
        mom = _compute_mom(closes, lookback=20)
        assert pd.isna(mom)


class TestCrossSectionalZscore:
    """测试横截面 Z-score"""

    def test_zscore_basic(self):
        """基本 Z-score 计算"""
        from src.analysis.factor_engine import _cross sectional_zscore

        values = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        z = _cross_sectional_zscore(values)
        assert len(z) == 5
        assert abs(z.mean()) < 1e-10

    def test_zero_std_returns_zero(self):
        """标准差为零 → 全部返回 0"""
        from src.analysis.factor_engine import _cross_sectional_zscore

        values = pd.Series([3.0, 3.0, 3.0])
        z = _cross_sectional_zscore(values)
        assert (z == 0).all()


class TestQuadrantClassification:
    """测试四象限分类"""

    def test_q1_strong(self):
        """Z_Flow > 0, Z_Mom > 0 → Q1"""
        from src.analysis.factor_engine import _classify_quadrant

        assert _classify_quadrant(0.5, 0.5) == 1

    def test_q2_lurk(self):
        """Z_Flow > 0, Z_Mom < 0 → Q2"""
        from src.analysis.factor_engine import _classify_quadrant

        assert _classify_quadrant(0.5, -0.5) == 2

    def test_q3_exit(self):
        """Z_Flow < 0, Z_Mom < 0 → Q3"""
        from src.analysis.factor_engine import _classify_quadrant

        assert _classify_quadrant(-0.5, -0.5) == 3

    def test_q4_risk(self):
        """Z_Flow < 0, Z_Mom > 0 → Q4"""
        from src.analysis.factor_engine import _classify_quadrant

        assert _classify_quadrant(-0.5, 0.5) == 4


class TestComputeFactorsForDate:
    """测试单日因子计算集成"""

    def test_returns_dataframe_with_expected_columns(self):
        """返回正确的 DataFrame 结构"""
        from src.analysis.factor_engine import compute_factors_for_date

        # Build mock data: 3 ETFs with enough history
        n = 30
        dates = pd.date_range("2025-01-01", periods=n, freq="D")
        kline_data = []
        share_data = []
        for code in ["A", "B", "C"]:
            for i, d in enumerate(dates):
                price = 10.0 + i * 0.1
                kline_data.append({"ts_code": code, "trade_date": d, "close": price,
                                   "pct_chg": 1.0})
                share_data.append({"ts_code": code, "trade_date": d, "fd_share": 1000 + i * 10})

        kline_df = pd.DataFrame(kline_data)
        share_df = pd.DataFrame(share_data)
        preset = {"flow_lookback": 10, "mom_lookback": 20}

        result = compute_factors_for_date(kline_df, share_df, dates[-1], preset)
        assert isinstance(result, pd.DataFrame)
        assert "etf_code" in result.columns
        assert "flow" in result.columns
        assert "mom" in result.columns
        assert "z_flow" in result.columns
        assert "z_mom" in result.columns
        assert "factor" in result.columns
        assert "quadrant" in result.columns
        assert len(result) == 3
```

Note: The test file has a deliberate typo `_cross sectional_zscore` (space in name) — this will fail, forcing us to write the correct function name in the implementation. Fix the test to use `_cross_sectional_zscore` when writing.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_factor_engine.py -v`
Expected: FAIL (module not found)

### Part B: Implementation

- [ ] **Step 3: Write `src/analysis/factor_engine.py`**

```python
"""Factor computation engine for sector ETF four-quadrant analysis.

Computes Flow (share trend), Momentum, cross-sectional Z-scores,
interaction factor, and quadrant classification.
"""
import logging

import numpy as np
import pandas as pd
from sqlalchemy import text

from src.core.db_manager_postgresql import get_conn, safe_json
from src.analysis.presets import get_preset, all_preset_ids

logger = logging.getLogger(__name__)


def _compute_flow(shares: pd.Series, lookback: int) -> float:
    """Compute normalized share trend via OLS slope.

    Flow = OLS_slope(recent N days) / mean(recent N days)
    Positive = inflow, Negative = outflow.
    Returns NaN if insufficient data.
    """
    if len(shares) < lookback:
        return np.nan
    recent = shares.iloc[-lookback:].astype(float).values
    if len(recent) < 2:
        return np.nan
    mean_val = recent.mean()
    if mean_val == 0:
        return np.nan
    x = np.arange(len(recent), dtype=float)
    slope = np.polyfit(x, recent, 1)[0]
    return float(slope / mean_val)


def _compute_mom(closes: pd.Series, lookback: int, vol_window: int = 60) -> float:
    """Compute volatility-adjusted momentum.

    Mom = close_today / close_{M days ago} - 1
    Mom_adj = Mom / std(daily_returns, 60 days)
    Falls back to unadjusted Mom if insufficient volatility data.
    """
    if len(closes) < lookback + 1:
        return np.nan
    close_today = float(closes.iloc[-1])
    close_past = float(closes.iloc[-(lookback + 1)])
    if close_past == 0:
        return np.nan
    mom = close_today / close_past - 1

    # Volatility adjustment
    if len(closes) >= vol_window + 1:
        daily_ret = closes.astype(float).pct_change().dropna().tail(vol_window)
        if len(daily_ret) >= 30:
            vol = daily_ret.std()
            if vol > 0:
                return float(mom / vol)

    return float(mom)


def _cross_sectional_zscore(values: pd.Series) -> pd.Series:
    """Compute cross-sectional Z-scores. Returns zeros if std is 0."""
    std = values.std()
    if std == 0 or pd.isna(std):
        return pd.Series(0.0, index=values.index)
    return (values - values.mean()) / std


def _classify_quadrant(z_flow: float, z_mom: float) -> int:
    """Classify ETF into one of four quadrants.

    Q1: z_flow > 0, z_mom > 0 → 强势 (strong)
    Q2: z_flow > 0, z_mom < 0 → 潜伏 (lurk)
    Q3: z_flow < 0, z_mom < 0 → 逃顶 (exit)
    Q4: z_flow < 0, z_mom > 0 → 风险 (risk)
    """
    if z_flow >= 0 and z_mom >= 0:
        return 1
    elif z_flow >= 0 and z_mom < 0:
        return 2
    elif z_flow < 0 and z_mom < 0:
        return 3
    else:
        return 4


def compute_factors_for_date(
    kline_df: pd.DataFrame,
    share_df: pd.DataFrame,
    target_date,
    preset: dict,
) -> pd.DataFrame:
    """Compute factor values for all ETFs on a single date.

    Args:
        kline_df: DataFrame with columns [ts_code, trade_date, close, pct_chg]
        share_df: DataFrame with columns [ts_code, trade_date, fd_share]
        target_date: The date to compute factors for
        preset: Preset config dict with flow_lookback, mom_lookback

    Returns:
        DataFrame with columns [etf_code, trade_date, flow, mom, z_flow, z_mom, factor, quadrant]
    """
    flow_lb = preset["flow_lookback"]
    mom_lb = preset["mom_lookback"]
    lookback_needed = max(flow_lb, mom_lb) + 1

    etf_codes = kline_df["ts_code"].unique()
    rows = []

    for code in etf_codes:
        etf_kline = kline_df[kline_df["ts_code"] == code].sort_values("trade_date")
        etf_shares = share_df[share_df["ts_code"] == code].sort_values("trade_date")

        # Filter to data up to target_date
        etf_kline = etf_kline[etf_kline["trade_date"] <= target_date]
        etf_shares = etf_shares[etf_shares["trade_date"] <= target_date]

        if len(etf_kline) < lookback_needed or len(etf_shares) < flow_lb:
            continue

        flow = _compute_flow(etf_shares["fd_share"], flow_lb)
        mom = _compute_mom(etf_kline["close"], mom_lb)

        if pd.isna(flow) or pd.isna(mom):
            continue

        rows.append({
            "etf_code": code,
            "trade_date": target_date,
            "flow": flow,
            "mom": mom,
        })

    if len(rows) < 2:
        return pd.DataFrame(columns=["etf_code", "trade_date", "flow", "mom",
                                      "z_flow", "z_mom", "factor", "quadrant"])

    result = pd.DataFrame(rows)
    result["z_flow"] = _cross_sectional_zscore(result["flow"]).values
    result["z_mom"] = _cross_sectional_zscore(result["mom"]).values
    result["factor"] = result["z_flow"] * result["z_mom"]
    result["quadrant"] = result.apply(
        lambda r: _classify_quadrant(r["z_flow"], r["z_mom"]), axis=1
    )

    return result


def compute_all_factors(preset_id: str = None) -> int:
    """Compute factors for all trading dates for the given preset.

    Fetches sector ETF price + share data from DB, computes factors
    for each trading date, and upserts to factor_daily table.

    Returns the number of rows upserted.
    """
    preset_ids = [preset_id] if preset_id else all_preset_ids()
    total_upserted = 0

    for pid in preset_ids:
        preset = get_preset(pid)
        flow_lb = preset["flow_lookback"]
        mom_lb = preset["mom_lookback"]
        lookback_needed = max(flow_lb, mom_lb) + 1

        conn = get_conn()
        try:
            # Fetch all sector ETF price data
            kline_rows = conn.execute(text(
                "SELECT ts_code, trade_date, close, pct_chg FROM sector_etf_daily "
                "ORDER BY ts_code, trade_date"
            )).fetchall()

            # Fetch all ETF share data
            share_rows = conn.execute(text(
                "SELECT ts_code, trade_date, fd_share FROM etf_share "
                "ORDER BY ts_code, trade_date"
            )).fetchall()
        finally:
            conn.close()

        if not kline_rows or not share_rows:
            logger.warning(f"No data for factor computation (preset={pid})")
            continue

        kline_df = pd.DataFrame(kline_rows, columns=["ts_code", "trade_date", "close", "pct_chg"])
        share_df = pd.DataFrame(share_rows, columns=["ts_code", "trade_date", "fd_share"])

        # Get unique trading dates, skip dates that don't have enough history
        all_dates = sorted(kline_df["trade_date"].unique())
        # Only compute for dates after sufficient lookback
        # Find the first date where we have enough history for at least one ETF
        computable_dates = []
        for d in all_dates:
            history = kline_df[kline_df["trade_date"] <= d]
            max_len = history.groupby("ts_code").size().max() if len(history) > 0 else 0
            if max_len >= lookback_needed:
                computable_dates.append(d)

        if not computable_dates:
            continue

        # Check what's already computed
        conn = get_conn()
        try:
            existing = conn.execute(text(
                "SELECT DISTINCT trade_date FROM factor_daily WHERE preset_id = :pid"
            ), {"pid": pid}).fetchall()
            existing_dates = {r[0] for r in existing}
        finally:
            conn.close()

        new_dates = [d for d in computable_dates if d not in existing_dates]
        if not new_dates:
            logger.info(f"All factor data already computed for preset={pid}")
            continue

        # Compute factors for new dates
        batch_rows = []
        for d in new_dates:
            day_result = compute_factors_for_date(kline_df, share_df, d, preset)
            for _, row in day_result.iterrows():
                batch_rows.append({
                    "etf_code": row["etf_code"],
                    "trade_date": row["trade_date"],
                    "preset_id": pid,
                    "flow": float(row["flow"]),
                    "mom": float(row["mom"]),
                    "z_flow": float(row["z_flow"]),
                    "z_mom": float(row["z_mom"]),
                    "factor": float(row["factor"]),
                    "quadrant": int(row["quadrant"]),
                })

        if batch_rows:
            from src.core.db_manager_postgresql import get_db_manager
            db = get_db_manager()
            df = pd.DataFrame(batch_rows)
            db.upsert_dataframe(df, "factor_daily", ["etf_code", "trade_date", "preset_id"])
            total_upserted += len(batch_rows)
            logger.info(f"Computed {len(batch_rows)} factor rows for preset={pid}")

    return total_upserted
```

- [ ] **Step 4: Fix the test typo and run tests**

Fix the test: ensure `_cross_sectional_zscore` has no space. Then run:

Run: `pytest tests/unit/test_factor_engine.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/analysis/factor_engine.py tests/unit/test_factor_engine.py
git commit -m "feat: add factor engine with Flow/Mom/Z-score computation and tests"
```

---

## Task 4: IC Analyzer + Tests

**Files:**
- Create: `src/analysis/ic_analyzer.py`
- Create: `tests/unit/test_ic_analyzer.py`

### Part A: Tests

- [ ] **Step 1: Write test file `tests/unit/test_ic_analyzer.py`**

```python
"""IC分析器单元测试"""
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock


class TestComputeICForDate:
    """测试单日IC计算"""

    def test_perfect_positive_correlation(self):
        """因子与收益完全正相关 → IC接近1"""
        from src.analysis.ic_analyzer import _compute_ic_for_date

        factors = pd.Series([0.1, 0.3, 0.5, 0.7, 0.9, 1.1, 1.3, 1.5])
        returns = pd.Series([0.01, 0.03, 0.05, 0.07, 0.09, 0.11, 0.13, 0.15])
        ic = _compute_ic_for_date(factors, returns)
        assert ic > 0.9

    def test_perfect_negative_correlation(self):
        """因子与收益完全负相关 → IC接近-1"""
        from src.analysis.ic_analyzer import _compute_ic_for_date

        factors = pd.Series([1.5, 1.3, 1.1, 0.9, 0.7, 0.5, 0.3, 0.1])
        returns = pd.Series([0.01, 0.03, 0.05, 0.07, 0.09, 0.11, 0.13, 0.15])
        ic = _compute_ic_for_date(factors, returns)
        assert ic < -0.9

    def test_insufficient_data_returns_nan(self):
        """数据不足 → NaN"""
        from src.analysis.ic_analyzer import _compute_ic_for_date

        factors = pd.Series([0.1, 0.2])
        returns = pd.Series([0.01, 0.02])
        ic = _compute_ic_for_date(factors, returns)
        assert pd.isna(ic)


class TestComputeICSummary:
    """测试IC汇总统计"""

    def test_basic_summary(self):
        """基本IC汇总"""
        from src.analysis.ic_analyzer import _compute_ic_summary

        ic_series = pd.Series([0.05, 0.03, -0.02, 0.04, 0.06, 0.01, -0.01, 0.07, 0.02, 0.03])
        summary = _compute_ic_summary(ic_series)
        assert "ic_mean" in summary
        assert "ic_std" in summary
        assert "icir" in summary
        assert "ic_win_rate" in summary
        assert summary["ic_win_rate"] == 0.8  # 8 out of 10 positive
        assert summary["sample_count"] == 10

    def test_all_positive_ic(self):
        """全部正IC → 胜率1.0"""
        from src.analysis.ic_analyzer import _compute_ic_summary

        ic_series = pd.Series([0.1, 0.2, 0.3, 0.4, 0.5])
        summary = _compute_ic_summary(ic_series)
        assert summary["ic_win_rate"] == 1.0
        assert summary["icir"] > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_ic_analyzer.py -v`
Expected: FAIL (module not found)

### Part B: Implementation

- [ ] **Step 3: Write `src/analysis/ic_analyzer.py`**

```python
"""IC (Information Coefficient) analyzer for factor validation.

Computes Spearman Rank IC, ICIR, IC win rate, IC decay,
and rolling ICIR from factor values and forward returns.
"""
import logging

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
from sqlalchemy import text

from src.core.db_manager_postgresql import get_conn, get_db_manager
from src.analysis.presets import get_preset, all_preset_ids

logger = logging.getLogger(__name__)

MIN_ETF_COUNT = 8  # Minimum ETFs for meaningful IC


def _compute_ic_for_date(factors: pd.Series, forward_returns: pd.Series) -> float:
    """Compute Spearman Rank IC for a single cross-section.

    Returns NaN if insufficient data (< MIN_ETF_COUNT valid pairs).
    """
    valid = factors.notna() & forward_returns.notna()
    f = factors[valid]
    r = forward_returns[valid]

    if len(f) < MIN_ETF_COUNT:
        return np.nan

    corr, _ = scipy_stats.spearmanr(f, r)
    return float(corr) if not np.isnan(corr) else np.nan


def _compute_ic_summary(ic_series: pd.Series) -> dict:
    """Compute aggregate IC statistics from an IC time series."""
    valid = ic_series.dropna()
    n = len(valid)
    if n == 0:
        return {"ic_mean": None, "ic_std": None, "icir": None, "ic_win_rate": None, "sample_count": 0}

    ic_mean = float(valid.mean())
    ic_std = float(valid.std())
    icir = ic_mean / ic_std if ic_std > 0 else None
    ic_win_rate = float((valid > 0).sum() / n)

    return {
        "ic_mean": round(ic_mean, 6),
        "ic_std": round(ic_std, 6),
        "icir": round(icir, 6) if icir is not None else None,
        "ic_win_rate": round(ic_win_rate, 4),
        "sample_count": n,
    }


def compute_all_ic(preset_id: str = None) -> int:
    """Compute IC analysis for all presets and store to DB.

    For each preset:
    1. Compute daily IC for each forward period H
    2. Compute aggregate IC summary
    3. Compute quadrant performance (avg forward return per quadrant)
    4. Upsert results to ic_daily, ic_summary, quadrant_perf tables

    Returns total rows upserted.
    """
    preset_ids = [preset_id] if preset_id else all_preset_ids()
    total_upserted = 0

    for pid in preset_ids:
        preset = get_preset(pid)
        forward_periods = preset["forward_periods"]

        conn = get_conn()
        try:
            # Get factor data for this preset
            factor_rows = conn.execute(text(
                "SELECT etf_code, trade_date, factor, z_flow, z_mom, quadrant "
                "FROM factor_daily WHERE preset_id = :pid ORDER BY trade_date"
            ), {"pid": pid}).fetchall()

            # Get sector ETF price data for forward returns
            price_rows = conn.execute(text(
                "SELECT ts_code, trade_date, close FROM sector_etf_daily "
                "ORDER BY ts_code, trade_date"
            )).fetchall()
        finally:
            conn.close()

        if not factor_rows or not price_rows:
            logger.warning(f"No data for IC computation (preset={pid})")
            continue

        factor_df = pd.DataFrame(factor_rows,
                                  columns=["etf_code", "trade_date", "factor", "z_flow", "z_mom", "quadrant"])
        price_df = pd.DataFrame(price_rows, columns=["ts_code", "trade_date", "close"])

        # Build price lookup: (code, date) → close
        price_df["close"] = price_df["close"].astype(float)
        price_lookup = {}
        for _, row in price_df.iterrows():
            price_lookup[(row["ts_code"], row["trade_date"])] = row["close"]

        # Get sorted unique dates for forward return computation
        all_dates = sorted(price_df["trade_date"].unique())
        date_idx = {d: i for i, d in enumerate(all_dates)}

        # Get trading dates present in factor data
        factor_dates = sorted(factor_df["trade_date"].unique())

        for h in forward_periods:
            ic_rows = []
            quadrant_rows = []

            for t in factor_dates:
                # Get factors for this date
                day_factors = factor_df[factor_df["trade_date"] == t]

                # Compute forward returns: close_{t+H} / close_t - 1
                fwd_rets = {}
                for _, row in day_factors.iterrows():
                    code = row["etf_code"]
                    close_t = price_lookup.get((code, t))
                    # Find date t+H
                    if t not in date_idx:
                        continue
                    idx = date_idx[t]
                    if idx + h >= len(all_dates):
                        continue
                    fwd_date = all_dates[idx + h]
                    close_fwd = price_lookup.get((code, fwd_date))
                    if close_t and close_fwd and close_t > 0:
                        fwd_rets[code] = (close_fwd / close_t - 1, row["factor"], row["quadrant"])

                if len(fwd_rets) < MIN_ETF_COUNT:
                    continue

                codes = list(fwd_rets.keys())
                ret_vals = pd.Series([fwd_rets[c][0] for c in codes])
                fac_vals = pd.Series([fwd_rets[c][1] for c in codes])

                ic = _compute_ic_for_date(fac_vals, ret_vals)

                if not np.isnan(ic):
                    ic_rows.append({
                        "trade_date": t,
                        "preset_id": pid,
                        "forward_days": h,
                        "ic_value": float(ic),
                        "forward_ret_mean": float(ret_vals.mean()),
                    })

                # Quadrant performance
                for q in [1, 2, 3, 4]:
                    q_codes = [c for c in codes if fwd_rets[c][2] == q]
                    if q_codes:
                        q_rets = [fwd_rets[c][0] for c in q_codes]
                        quadrant_rows.append({
                            "trade_date": t,
                            "preset_id": pid,
                            "forward_days": h,
                            "quadrant": q,
                            "avg_forward_ret": float(np.mean(q_rets)),
                            "etf_count": len(q_codes),
                        })

            # Upsert ic_daily
            if ic_rows:
                db = get_db_manager()
                db.upsert_dataframe(pd.DataFrame(ic_rows), "ic_daily",
                                     ["trade_date", "preset_id", "forward_days"])
                total_upserted += len(ic_rows)

            # Upsert quadrant_perf
            if quadrant_rows:
                db = get_db_manager()
                db.upsert_dataframe(pd.DataFrame(quadrant_rows), "quadrant_perf",
                                     ["trade_date", "preset_id", "forward_days", "quadrant"])
                total_upserted += len(quadrant_rows)

            # Compute and upsert ic_summary
            if ic_rows:
                ic_series = pd.Series([r["ic_value"] for r in ic_rows])
                summary = _compute_ic_summary(ic_series)
                summary["preset_id"] = pid
                summary["forward_days"] = h

                # Delete old summary and insert new
                conn = get_conn()
                try:
                    conn.execute(text(
                        "DELETE FROM ic_summary WHERE preset_id = :pid AND forward_days = :h"
                    ), {"pid": pid, "h": h})
                    conn.commit()
                finally:
                    conn.close()

                db = get_db_manager()
                db.insert_dataframe(pd.DataFrame([summary]), "ic_summary", if_exists="append")
                total_upserted += 1

            logger.info(f"IC analysis done for preset={pid}, H={h}: {len(ic_rows)} IC values")

    return total_upserted
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_ic_analyzer.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/analysis/ic_analyzer.py tests/unit/test_ic_analyzer.py
git commit -m "feat: add IC analyzer with Spearman Rank IC computation and tests"
```

---

## Task 5: Chart Builder

**Files:**
- Create: `src/analysis/chart_builder.py`

- [ ] **Step 1: Write `src/analysis/chart_builder.py`**

```python
"""Transform DB query results into ECharts-ready JSON for the 7 chart types.

Each function takes raw data and returns a dict that can be directly
used as the ECharts `option` object.
"""
import numpy as np
import pandas as pd
from sqlalchemy import text

from src.core.db_manager_postgresql import get_conn, safe_json, safe_dict
from src.analysis.presets import get_preset


def build_factor_distribution(preset_id: str) -> dict:
    """Chart 1: Factor distribution histogram for the latest date."""
    conn = get_conn()
    try:
        row = conn.execute(text(
            "SELECT MAX(trade_date) FROM factor_daily WHERE preset_id = :pid"
        ), {"pid": preset_id}).fetchone()
        if not row or not row[0]:
            return {"error": "no_data"}
        latest_date = row[0]

        rows = conn.execute(text(
            "SELECT factor FROM factor_daily WHERE preset_id = :pid AND trade_date = :d"
        ), {"pid": preset_id, "d": latest_date}).fetchall()
    finally:
        conn.close()

    if not rows:
        return {"error": "no_data"}

    values = [float(r[0]) for r in rows if r[0] is not None]
    # Build histogram bins
    bins = np.linspace(min(values) - 0.1, max(values) + 0.1, 11)
    counts, edges = np.histogram(values, bins=bins)

    labels = [f"{edges[i]:.2f}~{edges[i+1]:.2f}" for i in range(len(counts))]

    return safe_dict({
        "date": str(latest_date),
        "chart": {
            "xAxis": {"type": "category", "data": labels, "axisLabel": {"rotate": 30, "fontSize": 10}},
            "yAxis": {"type": "value", "name": "ETF数量"},
            "series": [{"type": "bar", "data": [int(c) for c in counts],
                        "itemStyle": {"color": "#5a6f5a"}}],
            "tooltip": {"trigger": "axis"},
        }
    })


def build_ic_series(preset_id: str, forward_days: int = 5) -> dict:
    """Chart 2: IC time series with mean line and ±2 std band."""
    conn = get_conn()
    try:
        rows = conn.execute(text(
            "SELECT trade_date, ic_value FROM ic_daily "
            "WHERE preset_id = :pid AND forward_days = :h ORDER BY trade_date"
        ), {"pid": preset_id, "h": forward_days}).fetchall()

        summary_row = conn.execute(text(
            "SELECT ic_mean, ic_std FROM ic_summary "
            "WHERE preset_id = :pid AND forward_days = :h"
        ), {"pid": preset_id, "h": forward_days}).fetchone()
    finally:
        conn.close()

    if not rows:
        return {"error": "no_data"}

    dates = [str(r[0]) for r in rows]
    ics = [float(r[1]) if r[1] is not None else None for r in rows]
    ic_mean = float(summary_row[0]) if summary_row and summary_row[0] else 0
    ic_std = float(summary_row[1]) if summary_row and summary_row[1] else 0

    return safe_dict({
        "chart": {
            "xAxis": {"type": "category", "data": dates, "axisLabel": {"fontSize": 9, "rotate": 45}},
            "yAxis": {"type": "value", "name": "IC"},
            "series": [
                {"name": "IC", "type": "line", "data": ics, "lineStyle": {"width": 1.5},
                 "itemStyle": {"color": "#5a6f5a"}, "symbol": "none"},
                {"name": "IC均值", "type": "line", "data": [round(ic_mean, 4)] * len(dates),
                 "lineStyle": {"width": 2, "color": "#8b4513", "type": "dashed"}, "symbol": "none"},
                {"name": "+2σ", "type": "line", "data": [round(ic_mean + 2 * ic_std, 4)] * len(dates),
                 "lineStyle": {"width": 1, "color": "#c4d4c4", "type": "dotted"}, "symbol": "none"},
                {"name": "-2σ", "type": "line", "data": [round(ic_mean - 2 * ic_std, 4)] * len(dates),
                 "lineStyle": {"width": 1, "color": "#c4d4c4", "type": "dotted"}, "symbol": "none"},
            ],
            "tooltip": {"trigger": "axis"},
            "legend": {"bottom": 0, "textStyle": {"fontSize": 10}},
        }
    })


def build_ic_decay(preset_id: str) -> dict:
    """Chart 3: IC mean vs forward period (decay curve)."""
    conn = get_conn()
    try:
        rows = conn.execute(text(
            "SELECT forward_days, ic_mean FROM ic_summary "
            "WHERE preset_id = :pid ORDER BY forward_days"
        ), {"pid": preset_id}).fetchall()
    finally:
        conn.close()

    if not rows:
        return {"error": "no_data"}

    periods = [f"{r[0]}D" for r in rows]
    means = [round(float(r[1]), 4) if r[1] is not None else 0 for r in rows]

    return safe_dict({
        "chart": {
            "xAxis": {"type": "category", "data": periods, "name": "持有期"},
            "yAxis": {"type": "value", "name": "IC均值"},
            "series": [{"type": "line", "data": means, "smooth": True,
                        "lineStyle": {"width": 2.5, "color": "#5a6f5a"},
                        "itemStyle": {"color": "#5a6f5a"}, "symbolSize": 8}],
            "tooltip": {"trigger": "axis"},
        }
    })


def build_quadrant_heatmap(preset_id: str, forward_days: int = None) -> dict:
    """Chart 4: Quadrant return heatmap."""
    preset = get_preset(preset_id)
    if forward_days is None:
        forward_days = preset["forward_periods"][0]

    conn = get_conn()
    try:
        # Get latest date with quadrant data
        row = conn.execute(text(
            "SELECT MAX(trade_date) FROM quadrant_perf "
            "WHERE preset_id = :pid AND forward_days = :h"
        ), {"pid": preset_id, "h": forward_days}).fetchone()

        if not row or not row[0]:
            return {"error": "no_data"}
        latest_date = row[0]

        rows = conn.execute(text(
            "SELECT quadrant, avg_forward_ret FROM quadrant_perf "
            "WHERE preset_id = :pid AND forward_days = :h AND trade_date = :d"
        ), {"pid": preset_id, "h": forward_days, "d": latest_date}).fetchall()
    finally:
        conn.close()

    if not rows:
        return {"error": "no_data"}

    quad_map = {r[0]: float(r[1]) * 100 for r in rows if r[1] is not None}

    # Layout: top-left=Q2(潜伏), top-right=Q1(强势), bottom-left=Q3(逃顶), bottom-right=Q4(风险)
    labels = {
        1: "Q1 强势", 2: "Q2 潜伏", 3: "Q3 逃顶", 4: "Q4 风险"
    }

    quadrants = [
        {"name": labels[2], "value": round(quad_map.get(2, 0), 2),
         "itemStyle": {"color": "#c4d4c4"}},
        {"name": labels[1], "value": round(quad_map.get(1, 0), 2),
         "itemStyle": {"color": "#4a7c4a"}},
        {"name": labels[3], "value": round(quad_map.get(3, 0), 2),
         "itemStyle": {"color": "#d4c4b0"}},
        {"name": labels[4], "value": round(quad_map.get(4, 0), 2),
         "itemStyle": {"color": "#e8c8c0"}},
    ]

    return safe_dict({
        "date": str(latest_date),
        "chart": {
            "quadrants": quadrants,
            "axis_labels": {"x": "Z_Mom (价格动量)", "y": "Z_Flow (资金流)"},
        }
    })


def build_group_returns(preset_id: str, forward_days: int = None) -> dict:
    """Chart 5: Cumulative return curves per quadrant over time."""
    preset = get_preset(preset_id)
    if forward_days is None:
        forward_days = preset["forward_periods"][0]

    conn = get_conn()
    try:
        rows = conn.execute(text(
            "SELECT trade_date, quadrant, avg_forward_ret FROM quadrant_perf "
            "WHERE preset_id = :pid AND forward_days = :h ORDER BY trade_date"
        ), {"pid": preset_id, "h": forward_days}).fetchall()
    finally:
        conn.close()

    if not rows:
        return {"error": "no_data"}

    df = pd.DataFrame(rows, columns=["trade_date", "quadrant", "avg_forward_ret"])
    dates = sorted(df["trade_date"].unique())

    colors = {1: "#4a7c4a", 2: "#8fbc8f", 3: "#cd853f", 4: "#cd5c5c"}
    names = {1: "Q1强势", 2: "Q2潜伏", 3: "Q3逃顶", 4: "Q4风险"}
    series = []

    for q in [1, 2, 3, 4]:
        q_df = df[df["quadrant"] == q].sort_values("trade_date")
        cumulative = (1 + q_df["avg_forward_ret"].astype(float)).cumprod() - 1
        series.append({
            "name": names[q],
            "type": "line",
            "data": [round(float(v) * 100, 2) for v in cumulative],
            "lineStyle": {"width": 2 if q in [1, 3] else 1.5,
                          "type": "solid" if q in [1, 3] else "dashed",
                          "color": colors[q]},
            "itemStyle": {"color": colors[q]},
            "symbol": "none",
        })

    return safe_dict({
        "chart": {
            "xAxis": {"type": "category", "data": [str(d) for d in dates],
                      "axisLabel": {"fontSize": 9, "rotate": 45}},
            "yAxis": {"type": "value", "name": "累计收益(%)"},
            "series": series,
            "tooltip": {"trigger": "axis"},
            "legend": {"bottom": 0, "textStyle": {"fontSize": 10}},
        }
    })


def build_rolling_icir(preset_id: str, forward_days: int = 5, window: int = 60) -> dict:
    """Chart 6: Rolling ICIR time series."""
    conn = get_conn()
    try:
        rows = conn.execute(text(
            "SELECT trade_date, ic_value FROM ic_daily "
            "WHERE preset_id = :pid AND forward_days = :h ORDER BY trade_date"
        ), {"pid": preset_id, "h": forward_days}).fetchall()
    finally:
        conn.close()

    if not rows or len(rows) < window:
        return {"error": "no_data"}

    dates_all = [str(r[0]) for r in rows]
    ics = pd.Series([float(r[1]) if r[1] is not None else np.nan for r in rows])

    rolling_mean = ics.rolling(window).mean()
    rolling_std = ics.rolling(window).std()
    rolling_icir = (rolling_mean / rolling_std).fillna(0)

    # Only show from window-th date onward
    valid_idx = list(range(window - 1, len(dates_all)))
    valid_dates = [dates_all[i] for i in valid_idx]
    valid_icir = [round(float(rolling_icir.iloc[i]), 4) for i in valid_idx]

    return safe_dict({
        "chart": {
            "xAxis": {"type": "category", "data": valid_dates,
                      "axisLabel": {"fontSize": 9, "rotate": 45}},
            "yAxis": {"type": "value", "name": "Rolling ICIR"},
            "series": [{"type": "line", "data": valid_icir,
                        "lineStyle": {"width": 1.5, "color": "#8b4513"},
                        "itemStyle": {"color": "#8b4513"}, "symbol": "none",
                        "areaStyle": {"color": "rgba(139,69,19,0.05)"}}],
            "tooltip": {"trigger": "axis"},
        }
    })


def build_weight_recommendation(preset_id: str) -> dict:
    """Chart 7: Allocation weight recommendation based on latest factor values."""
    conn = get_conn()
    try:
        row = conn.execute(text(
            "SELECT MAX(trade_date) FROM factor_daily WHERE preset_id = :pid"
        ), {"pid": preset_id}).fetchone()
        if not row or not row[0]:
            return {"error": "no_data"}
        latest_date = row[0]

        rows = conn.execute(text(
            "SELECT f.etf_code, f.factor, f.quadrant FROM factor_daily f "
            "WHERE f.preset_id = :pid AND f.trade_date = :d ORDER BY f.factor DESC"
        ), {"pid": preset_id, "d": latest_date}).fetchall()
    finally:
        conn.close()

    if not rows:
        return {"error": "no_data"}

    from config.config import SECTOR_ETF

    # Only recommend Q1 (strong) and Q2 (lurk) ETFs
    recommended = []
    for r in rows:
        code, factor, quadrant = r[0], float(r[1]) if r[1] else 0, int(r[2])
        if quadrant in [1, 2]:
            name = SECTOR_ETF.get(code, code)
            recommended.append({"name": name, "factor": round(factor, 3),
                                "quadrant": quadrant, "code": code})

    if not recommended:
        return safe_dict({"chart": {"xAxis": {"type": "category", "data": []},
                                     "yAxis": {"type": "value"}, "series": []}})

    # Normalize factor to weights (softmax-like, but simpler: proportional to positive factors)
    pos_factors = [abs(r["factor"]) for r in recommended]
    total = sum(pos_factors)
    if total == 0:
        weights = [1.0 / len(recommended)] * len(recommended)
    else:
        weights = [f / total for f in pos_factors]

    for i, r in enumerate(recommended):
        r["weight"] = round(weights[i] * 100, 1)

    colors_map = {1: "#4a7c4a", 2: "#8fbc8f"}

    return safe_dict({
        "date": str(latest_date),
        "chart": {
            "xAxis": {"type": "category",
                      "data": [f"{r['name']}(Q{r['quadrant']})" for r in recommended]},
            "yAxis": {"type": "value", "name": "建议权重(%)", "max": max(w * 100 for w in weights) * 1.2},
            "series": [{"type": "bar",
                        "data": [{"value": r["weight"],
                                  "itemStyle": {"color": colors_map[r["quadrant"]]}}
                                 for r in recommended],
                        "barMaxWidth": 40}],
            "tooltip": {"trigger": "axis"},
        }
    })


def build_summary(preset_id: str) -> dict:
    """Text summary with factor validity, quadrant verification, and recommendations."""
    conn = get_conn()
    try:
        summary_rows = conn.execute(text(
            "SELECT forward_days, ic_mean, icir, ic_win_rate, sample_count "
            "FROM ic_summary WHERE preset_id = :pid ORDER BY forward_days"
        ), {"pid": preset_id}).fetchall()

        # Latest quadrant distribution
        latest_row = conn.execute(text(
            "SELECT MAX(trade_date) FROM factor_daily WHERE preset_id = :pid"
        ), {"pid": preset_id}).fetchone()
        latest_date = latest_row[0] if latest_row else None

        latest_factors = []
        if latest_date:
            rows = conn.execute(text(
                "SELECT etf_code, factor, quadrant FROM factor_daily "
                "WHERE preset_id = :pid AND trade_date = :d ORDER BY factor DESC"
            ), {"pid": preset_id, "d": latest_date}).fetchall()
            from config.config import SECTOR_ETF
            for r in rows:
                latest_factors.append({
                    "code": r[0], "name": SECTOR_ETF.get(r[0], r[0]),
                    "factor": round(float(r[1]), 3) if r[1] else 0, "quadrant": int(r[2]),
                })
    finally:
        conn.close()

    # Build summary text
    factor_validity = ""
    decay_period = "未知"
    if summary_rows:
        first_h = summary_rows[0]
        ic_mean = first_h[1]
        icir = first_h[2]
        if ic_mean is not None:
            direction = "正" if ic_mean > 0 else "负"
            strength = "显著" if abs(ic_mean) > 0.03 else "较弱"
            factor_validity = f"IC均值{ic_mean:.3f}({direction}向{strength})"
        if icir is not None:
            stability = "稳定" if abs(icir) > 0.5 else "不稳定"
            factor_validity += f", ICIR {icir:.2f}({stability})"

        # Find decay point (first H where |IC| < 0.02)
        for sr in summary_rows:
            if sr[1] is not None and abs(sr[1]) < 0.02:
                decay_period = f"{sr[0]}日"
                break
        else:
            decay_period = f">{summary_rows[-1][0]}日"

    # Current recommendations
    q1_etfs = [f for f in latest_factors if f["quadrant"] == 1]
    q2_etfs = [f for f in latest_factors if f["quadrant"] == 2]
    strong_buy = "、".join([e["name"] for e in q1_etfs[:5]]) or "无"
    contrarian = "、".join([e["name"] for e in q2_etfs[:5]]) or "无"

    return safe_dict({
        "date": str(latest_date) if latest_date else None,
        "factor_validity": factor_validity,
        "decay_period": decay_period,
        "strong_buy": strong_buy,
        "contrarian": contrarian,
        "q1_count": len(q1_etfs),
        "q2_count": len(q2_etfs),
        "summary_rows": [{"forward_days": r[0], "ic_mean": r[1], "icir": r[2],
                          "ic_win_rate": r[3], "sample_count": r[4]}
                         for r in summary_rows],
    })
```

- [ ] **Step 2: Verify import**

Run: `python -c "from src.analysis.chart_builder import build_factor_distribution; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add src/analysis/chart_builder.py
git commit -m "feat: add chart builder with 7 ECharts JSON transformers"
```

---

## Task 6: Analysis Router + Cache Integration

**Files:**
- Create: `src/web/routers/analysis.py`
- Modify: `src/web/services/cache.py` (add "analysis" category)

- [ ] **Step 1: Add "analysis" cache category to `src/web/services/cache.py`**

Find the `CACHE_CATEGORIES` dict and add the "analysis" entry:

```python
CACHE_CATEGORIES = {
    "overview": ["overview", "heatmap"],
    "etf": ["index_etf_*", "sector_etf_*", "sector_cards"],
    "analysis": ["analysis_*"],
}
```

- [ ] **Step 2: Write `src/web/routers/analysis.py`**

```python
"""FastAPI router for the 可视化分析 module."""
import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.web.services.cache import _cached_persistent
from src.analysis.presets import PRESETS, get_preset, all_preset_ids
from src.analysis import factor_engine, ic_analyzer, chart_builder

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()


@router.get("/analysis", response_class=HTMLResponse)
async def page_analysis(request: Request):
    return templates.TemplateResponse("analysis.html", {"request": request})


@router.get("/api/analysis/presets")
async def api_presets():
    return {"presets": list(PRESETS.values()), "default": "short"}


@router.get("/api/analysis/factor-distribution")
async def api_factor_distribution(preset_id: str = "short"):
    return _cached_persistent(
        f"analysis_factor_dist_{preset_id}",
        lambda: chart_builder.build_factor_distribution(preset_id),
        max_age_hours=4,
    )


@router.get("/api/analysis/ic-series")
async def api_ic_series(preset_id: str = "short", forward_days: int = 5):
    return _cached_persistent(
        f"analysis_ic_series_{preset_id}_{forward_days}",
        lambda: chart_builder.build_ic_series(preset_id, forward_days),
        max_age_hours=4,
    )


@router.get("/api/analysis/ic-decay")
async def api_ic_decay(preset_id: str = "short"):
    return _cached_persistent(
        f"analysis_ic_decay_{preset_id}",
        lambda: chart_builder.build_ic_decay(preset_id),
        max_age_hours=4,
    )


@router.get("/api/analysis/quadrant-heatmap")
async def api_quadrant_heatmap(preset_id: str = "short", forward_days: int = None):
    preset = get_preset(preset_id)
    h = forward_days if forward_days else preset["forward_periods"][0]
    return _cached_persistent(
        f"analysis_qheatmap_{preset_id}_{h}",
        lambda: chart_builder.build_quadrant_heatmap(preset_id, h),
        max_age_hours=4,
    )


@router.get("/api/analysis/group-returns")
async def api_group_returns(preset_id: str = "short", forward_days: int = None):
    preset = get_preset(preset_id)
    h = forward_days if forward_days else preset["forward_periods"][0]
    return _cached_persistent(
        f"analysis_group_ret_{preset_id}_{h}",
        lambda: chart_builder.build_group_returns(preset_id, h),
        max_age_hours=4,
    )


@router.get("/api/analysis/rolling-icir")
async def api_rolling_icir(preset_id: str = "short", forward_days: int = 5, window: int = 60):
    return _cached_persistent(
        f"analysis_rolling_icir_{preset_id}_{forward_days}_{window}",
        lambda: chart_builder.build_rolling_icir(preset_id, forward_days, window),
        max_age_hours=4,
    )


@router.get("/api/analysis/summary")
async def api_summary(preset_id: str = "short"):
    return _cached_persistent(
        f"analysis_summary_{preset_id}",
        lambda: chart_builder.build_summary(preset_id),
        max_age_hours=4,
    )


@router.post("/api/analysis/recompute")
async def api_recompute(preset_id: str = None):
    """Trigger factor + IC recomputation in a background thread."""
    import threading

    def _run():
        try:
            logger.info(f"Starting analysis recomputation (preset={preset_id or 'all'})")
            factor_engine.compute_all_factors(preset_id)
            ic_analyzer.compute_all_ic(preset_id)
            logger.info("Analysis recomputation complete")
        except Exception as e:
            logger.error(f"Analysis recomputation failed: {e}")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"status": "started", "preset_id": preset_id or "all"}
```

- [ ] **Step 3: Verify router loads**

Run: `python -c "from src.web.routers.analysis import router; print(f'Routes: {len(router.routes)}')"`
Expected: Routes: 10

- [ ] **Step 4: Commit**

```bash
git add src/web/routers/analysis.py src/web/services/cache.py
git commit -m "feat: add analysis router with 10 API endpoints and cache integration"
```

---

## Task 7: App Registration

**Files:**
- Modify: `src/web/app.py`

- [ ] **Step 1: Add analysis router import and registration**

In `src/web/app.py`, add the import alongside the existing router imports:

```python
from src.web.routers import overview, etf, fetch, analysis
```

Add the router registration after the existing `app.include_router(fetch.router)`:

```python
app.include_router(analysis.router)
```

- [ ] **Step 2: Verify app starts**

Run: `python -c "from src.web.app import app; print(f'Routes: {len(app.routes)}')"`
Expected: Number increases by ~10 from before.

- [ ] **Step 3: Commit**

```bash
git add src/web/app.py
git commit -m "feat: register analysis router in web app"
```

---

## Task 8: Navigation Updates

**Files:**
- Modify: `src/web/templates/index.html`
- Modify: `src/web/templates/etf.html`
- Modify: `src/web/templates/sector.html`

- [ ] **Step 1: Add nav link to `index.html`**

Find the `<nav>` section containing the existing 3 nav links (首页, 指数ETF, 行业ETF). Add a 4th link after the 行业ETF link:

```html
<a href="/analysis" class="nav-link">可视化分析</a>
```

Also find the `bottom-nav` section with the 3 mobile nav links and add the 4th:

```html
<a href="/analysis" class="bottom-nav-item"><span class="nav-icon">📊</span><span>分析</span></a>
```

- [ ] **Step 2: Add nav link to `etf.html`**

Same pattern — add the link in both top nav and bottom nav. The "active" class stays on 指数ETF.

- [ ] **Step 3: Add nav link to `sector.html`**

Same pattern. The "active" class stays on 行业ETF.

- [ ] **Step 4: Verify nav links appear**

Run the app and check the nav bar shows 4 links.

- [ ] **Step 5: Commit**

```bash
git add src/web/templates/index.html src/web/templates/etf.html src/web/templates/sector.html
git commit -m "feat: add 可视化分析 nav link to all templates"
```

---

## Task 9: Analysis Template

**Files:**
- Create: `src/web/templates/analysis.html`

- [ ] **Step 1: Write `src/web/templates/analysis.html`**

This is the largest file. It follows the same patterns as `sector.html` — Jinja2 template with inline `<script>` that calls APIs and renders ECharts. Uses the Warm Sage theme from `ATMChart` in `app.js`.

The template structure:
1. HTML head (same as sector.html — includes app.css, app.js, vendor.js)
2. Nav bar (4 links, 可视化分析 is active)
3. Bottom nav (4 items)
4. Preset selector bar
5. 4 KPI cards
6. 3 rows of 2 charts each (6 charts)
7. Full-width weight chart
8. Text summary card
9. Inline `<script>` that loads data and renders all 7 ECharts

The inline script follows this pattern for each chart:

```javascript
async function loadChart(chartId, apiUrl) {
    const resp = await fetch(apiUrl);
    const data = await resp.json();
    if (data.error) {
        document.getElementById(chartId).innerHTML = '<p class="no-data">暂无数据</p>';
        return;
    }
    const chart = ATMChart.init(chartId);
    chart.setOption({...data.chart, ...ATMChart.getResponsiveOption()});
}
```

Full template content (this is a large file — see the actual implementation for the complete HTML). The key sections:

```html
{% raw %}
<!-- Preset bar -->
<div class="preset-bar">
  <span class="preset-label">参数预设</span>
  <button class="preset-btn active" data-preset="short" onclick="switchPreset('short')">短期 (N=10, M=20)</button>
  <button class="preset-btn" data-preset="medium" onclick="switchPreset('medium')">中期 (N=20, M=60)</button>
  <button class="preset-btn" data-preset="long" onclick="switchPreset('long')">长期 (N=40, M=120)</button>
  <span class="data-freshness" id="dataFreshness"></span>
</div>

<!-- KPI cards -->
<div class="kpi-row">
  <div class="kpi-card"><div class="kpi-label">IC均值</div><div class="kpi-value" id="kpiIcMean">--</div></div>
  <div class="kpi-card"><div class="kpi-label">ICIR</div><div class="kpi-value" id="kpiIcir">--</div></div>
  <div class="kpi-card"><div class="kpi-label">IC胜率</div><div class="kpi-value" id="kpiWinRate">--</div></div>
  <div class="kpi-card"><div class="kpi-label">强势ETF</div><div class="kpi-value" id="kpiStrongCount">--</div></div>
</div>

<!-- Charts in 2-column grid -->
<div class="chart-grid">
  <div class="chart-cell"><h3>① 因子分布直方图</h3><div id="chart1" class="chart-container"></div></div>
  <div class="chart-cell"><h3>④ 四象限收益热力图</h3><div id="chart4" class="chart-container heatmap-container"></div></div>
  <div class="chart-cell"><h3>② IC序列曲线</h3><div id="chart2" class="chart-container"></div></div>
  <div class="chart-cell"><h3>③ IC衰减图</h3><div id="chart3" class="chart-container"></div></div>
  <div class="chart-cell"><h3>⑤ 分组累计收益曲线</h3><div id="chart5" class="chart-container"></div></div>
  <div class="chart-cell"><h3>⑥ 因子滚动ICIR</h3><div id="chart6" class="chart-container"></div></div>
</div>

<!-- Full width weight chart -->
<div class="chart-full"><h3>⑦ 行业配置权重建议图</h3><div id="chart7" class="chart-container"></div></div>

<!-- Text summary -->
<div class="summary-card" id="summaryCard"></div>
{% endraw %}
```

The CSS for new elements (preset bar, KPI cards, chart grid) is added inline in a `<style>` block within the template, following the Warm Sage color palette:

```css
.preset-bar { /* pill selector bar */ }
.preset-btn { /* pill buttons */ }
.preset-btn.active { background: #5a6f5a; color: #fff; }
.kpi-row { /* 4-column flex */ }
.kpi-card { /* white card with border */ }
.chart-grid { /* 2-column CSS grid */ }
.chart-cell { /* chart container with white bg */ }
.summary-card { /* text summary with warm bg */ }
```

The JavaScript at the bottom:
1. `loadAllData(presetId)` — calls all 8 API endpoints in parallel via `Promise.all`
2. `renderCharts(data)` — creates/updates all 7 ECharts instances
3. `renderKPIs(summary)` — updates KPI card values
4. `renderSummary(summary)` — fills the text summary card
5. `switchPreset(presetId)` — updates active button, reloads data
6. Page load calls `loadAllData('short')`

- [ ] **Step 2: Verify template renders**

Start the app, navigate to `/analysis`, verify the page loads with the correct layout.

- [ ] **Step 3: Commit**

```bash
git add src/web/templates/analysis.html
git commit -m "feat: add analysis page template with 7 ECharts and preset selector"
```

---

## Task 10: Pipeline Integration

**Files:**
- Modify: `src/data_fetchers/tushare_fetcher.py`
- Modify: `src/web/routers/fetch.py`

- [ ] **Step 1: Add analysis computation to tushare_fetcher.py**

At the end of the `main()` function, after all data fetching is complete, add:

```python
# After all fetches complete, run analysis computation
try:
    from src.analysis import factor_engine, ic_analyzer
    logger.info("Starting factor analysis computation...")
    factor_engine.compute_all_factors()
    logger.info("Factor computation done. Starting IC analysis...")
    ic_analyzer.compute_all_ic()
    logger.info("IC analysis done.")
except Exception as e:
    logger.error(f"Analysis computation failed: {e}")
```

This should be added inside `main()` after the last fetch step, only when running the full pipeline (no `--etf`/`--stocks`/`--funda` flags), or when `--etf` flag is used (since analysis depends on ETF data).

Actually, only add it after `fetch_sector_etf()` is called. So add it after the sector ETF fetch block:

```python
if run_etf:
    fetch_index_etf()
    fetch_sector_etf()
    # Compute analysis after fresh ETF data
    try:
        from src.analysis import factor_engine, ic_analyzer
        logger.info("Computing factor analysis...")
        factor_engine.compute_all_factors()
        ic_analyzer.compute_all_ic()
        logger.info("[OK] Analysis computation complete")
    except Exception as e:
        logger.error(f"[SKIP] Analysis computation failed: {e}")
```

- [ ] **Step 2: Add cache invalidation to fetch.py**

In `src/web/routers/fetch.py`, after the fetch completes and `_cache_invalidate()` is called, add analysis cache invalidation:

Find where `_cache_invalidate()` is called and ensure it includes the "analysis" category. The function should already pick it up if we added it to `CACHE_CATEGORIES`, but verify.

- [ ] **Step 3: Verify pipeline runs**

Run a test fetch cycle (or just the recompute endpoint) and verify analysis data is computed and stored.

- [ ] **Step 4: Commit**

```bash
git add src/data_fetchers/tushare_fetcher.py src/web/routers/fetch.py
git commit -m "feat: integrate analysis computation into data fetch pipeline"
```

---

## Task 11: End-to-End Verification

- [ ] **Step 1: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Start the app**

Run: `python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8500 --reload`

- [ ] **Step 3: Trigger recomputation**

```bash
curl -X POST http://localhost:8500/api/analysis/recompute
```

Expected: `{"status":"started","preset_id":"all"}`

- [ ] **Step 4: Check analysis page**

Wait for recomputation to complete, then open `http://localhost:8500/analysis` and verify:
- Preset selector works (切换短期/中期/长期)
- 4 KPI cards show values
- All 7 charts render with data
- Text summary displays correctly
- Navigation works across all 4 pages

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete 可视化分析 module — factor engine, IC analysis, 7 charts"
```
