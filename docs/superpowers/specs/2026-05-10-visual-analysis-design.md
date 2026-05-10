# 可视化分析模块 — 行业ETF四象限因子构建与IC分析

## Overview

Add a new "可视化分析" navigation module to the website. This module computes cross-sectional factor values (Flow × Momentum) for sector ETFs, runs IC (Information Coefficient) analysis to validate factor predictive power, and presents 7 interactive ECharts visualizations plus a text summary with investment guidance.

All computation is pre-computed during the data fetch pipeline and stored in DB tables. The frontend serves pre-computed results instantly.

## Architecture

### Backend Module: `src/analysis/`

```
src/analysis/
  __init__.py
  factor_engine.py    — Flow, Mom, Z_Flow, Z_Mom, Factor per ETF per day per preset
  ic_analyzer.py      — IC series, ICIR, IC win rate, IC decay per preset
  chart_builder.py    — Transforms DB results into ECharts-ready JSON dicts
  presets.py          — Preset definitions and registry
```

### Preset System

Pre-defined parameter combinations. User picks from preset buttons on the page; each preset has its own pre-computed results.

| Preset ID | Label | N (Flow lookback) | M (Momentum lookback) | Forward periods H |
|-----------|-------|--------------------|-----------------------|-------------------|
| `short` | 短期 | 10 | 20 | [1, 5, 10, 20] |
| `medium` | 中期 | 20 | 60 | [1, 5, 10, 20, 40, 60] |
| `long` | 长期 | 40 | 120 | [5, 10, 20, 40, 60] |

### Database Tables (Alembic migration)

**`factor_daily`** — Factor values per ETF per trading day per preset.

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PK | Auto-increment |
| `etf_code` | VARCHAR(20) | Sector ETF code (e.g., '512480.SH') |
| `trade_date` | DATE | Trading date |
| `preset_id` | VARCHAR(20) | Preset identifier ('short', 'medium', 'long') |
| `flow` | FLOAT | Raw flow value (OLS slope / mean shares) |
| `mom` | FLOAT | Raw momentum value |
| `z_flow` | FLOAT | Cross-sectional Z-score of flow |
| `z_mom` | FLOAT | Cross-sectional Z-score of momentum |
| `factor` | FLOAT | Z_Flow * Z_Mom |
| `quadrant` | SMALLINT | 1=强势, 2=潜伏, 3=逃顶, 4=风险 |

Unique constraint: `(etf_code, trade_date, preset_id)`.

**`ic_daily`** — Daily IC values per preset and forward period.

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PK | Auto-increment |
| `trade_date` | DATE | Trading date |
| `preset_id` | VARCHAR(20) | Preset identifier |
| `forward_days` | SMALLINT | Forward return period H |
| `ic_value` | FLOAT | Spearman rank IC |
| `forward_ret_mean` | FLOAT | Mean forward return across ETFs |

Unique constraint: `(trade_date, preset_id, forward_days)`.

**`ic_summary`** — Aggregate IC statistics per preset and forward period.

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PK | Auto-increment |
| `preset_id` | VARCHAR(20) | Preset identifier |
| `forward_days` | SMALLINT | Forward return period H |
| `ic_mean` | FLOAT | Mean of IC series |
| `ic_std` | FLOAT | Std of IC series |
| `icir` | FLOAT | IC_mean / IC_std |
| `ic_win_rate` | FLOAT | Proportion of IC > 0 |
| `sample_count` | INT | Number of IC observations |
| `updated_at` | TIMESTAMP | Last computation time |

Unique constraint: `(preset_id, forward_days)`.

**`quadrant_perf`** — Quadrant-level average forward returns per day.

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PK | Auto-increment |
| `trade_date` | DATE | Trading date |
| `preset_id` | VARCHAR(20) | Preset identifier |
| `forward_days` | SMALLINT | Forward return period H (default: first H in preset) |
| `quadrant` | SMALLINT | Quadrant number (1-4) |
| `avg_forward_ret` | FLOAT | Average forward return for ETFs in this quadrant |
| `etf_count` | SMALLINT | Number of ETFs in this quadrant |

Unique constraint: `(trade_date, preset_id, forward_days, quadrant)`.

## Factor Computation Logic

### Flow (Share Trend)

```
Flow = OLS_slope(recent N days of shares) / mean(recent N days of shares)
```

Uses linear regression slope of daily share counts over the lookback window, normalized by the mean. This captures the trend strength of capital inflows/outflows.

### Momentum (Price Trend)

```
Mom = close_today / close_{M days ago} - 1
Mom_adj = Mom / std(daily_returns over 60 days)
```

Price return over the momentum lookback window, volatility-adjusted using 60-day return standard deviation. Falls back to unadjusted Mom if fewer than 30 days of data available.

### Cross-sectional Standardization

On each trading day, across all sector ETFs:

```
Z_Flow = (Flow_i - mean(Flow)) / std(Flow)
Z_Mom  = (Mom_i - mean(Mom)) / std(Mom)
```

### Interaction Factor

```
Factor = Z_Flow * Z_Mom
```

Positive factor → aligned inflow + momentum (bullish or reversal potential).

### Quadrant Classification

| Quadrant | Z_Flow | Z_Mom | Label | Interpretation |
|----------|--------|-------|-------|----------------|
| Q1 | > 0 | > 0 | 强势 | Strong inflow + rising price |
| Q2 | > 0 | < 0 | 潜伏 | Inflow but declining price (accumulation) |
| Q3 | < 0 | < 0 | 逃顶 | Outflow + declining price |
| Q4 | < 0 | > 0 | 风险 | Outflow but rising price (distribution) |

## IC Analysis Logic

### Forward Return

```
Forward_Ret_H = close_{t+H} / close_t - 1
```

Computed for each ETF on each day, for each H in the preset's forward_periods list.

### Spearman Rank IC

On each trading day t, for a given H:

```
IC_t = spearmanr([Factor_1,t, Factor_2,t, ...], [Forward_Ret_H_1,t, ..., Forward_Ret_H_n,t])
```

Uses `scipy.stats.spearmanr`. Requires at least 8 ETFs with valid data for a meaningful IC.

### Evaluation Metrics

- **IC Mean**: `mean(IC_series)` — average predictive strength
- **ICIR**: `IC_mean / IC_std` — factor stability (|ICIR| > 0.5 is meaningful)
- **IC Win Rate**: `count(IC > 0) / len(IC)` — proportion of positive IC days
- **IC Decay**: IC Mean computed separately for each forward period H, showing how quickly predictive power fades

### Rolling ICIR

```
Rolling_ICIR_t = rolling_mean(IC, window=60) / rolling_std(IC, window=60)
```

60-day rolling window applied to the IC series.

## API Endpoints

Router: `src/web/routers/analysis.py`, prefix: `/api/analysis`

| Endpoint | Method | Params | Description |
|----------|--------|--------|-------------|
| `/analysis` | GET | — | Render `analysis.html` template |
| `/api/analysis/presets` | GET | — | List presets with descriptions |
| `/api/analysis/factor-distribution` | GET | `preset_id` | Factor histogram data for latest date |
| `/api/analysis/ic-series` | GET | `preset_id`, `forward_days` | IC time series + mean/std lines |
| `/api/analysis/ic-decay` | GET | `preset_id` | IC mean vs H curve |
| `/api/analysis/quadrant-heatmap` | GET | `preset_id` | Quadrant return matrix |
| `/api/analysis/group-returns` | GET | `preset_id` | Cumulative return per quadrant |
| `/api/analysis/rolling-icir` | GET | `preset_id`, `window` | Rolling ICIR time series |
| `/api/analysis/summary` | GET | `preset_id` | Text summary with recommendations |
| `/api/analysis/recompute` | POST | `preset_id` (optional) | Trigger recomputation |

All GET endpoints read from pre-computed DB tables. The `recompute` endpoint triggers the factor_engine + ic_analyzer pipeline in a background thread.

## Frontend

### Template: `src/web/templates/analysis.html`

Single scrollable page following the existing Warm Sage design system. Layout (top to bottom):

1. **Preset selector bar** — pill buttons for 短期/中期/长期, data freshness timestamp, "刷新计算" link
2. **4 KPI cards** — IC均值, ICIR, IC胜率, 强势象限ETF数 (sourced from `ic_summary` + latest `factor_daily`)
3. **Row 1** (2-column): 因子分布直方图 + 四象限收益热力图
4. **Row 2** (2-column): IC序列曲线 + IC衰减图
5. **Row 3** (2-column): 分组累计收益曲线 + 因子滚动ICIR
6. **Full width**: 行业配置权重建议图
7. **Full width**: 分析总结与投资指导 (text card)

Charts rendered with ECharts 5 using the existing `ATMChart` helper system and Warm Sage theme from `app.js`.

### Navigation Update

Add "可视化分析" as the 4th nav link in all templates (index.html, etf.html, sector.html, analysis.html). The active link is hardcoded per template as in the existing pattern.

## Computation Pipeline Integration

The analysis computation is triggered at two points:

1. **During data fetch**: After `tushare_fetcher` completes fetching sector ETF daily data and ETF shares, it calls `factor_engine.compute_all()` followed by `ic_analyzer.compute_all()`. This runs for all presets.
2. **Manual trigger**: The `/api/analysis/recompute` endpoint allows on-demand recomputation without a full data refresh.

### Minimum Data Requirements

Factor computation requires:
- At least N days of share data for Flow calculation
- At least M days of price data for Momentum calculation
- At least 8 sector ETFs with valid data on a given date for IC calculation

## Text Summary Logic

The `/api/analysis/summary` endpoint generates a structured summary:

1. **Factor validity**: IC mean significance, ICIR threshold (|ICIR| > 0.5 = meaningful), decay period (H where IC drops below 0.02)
2. **Quadrant verification**: Q1 positive return confirmed, Q3 negative return confirmed, Q2/Q3 reversal effect detected
3. **Current allocation**: List ETFs in Q1 (strong buy) and Q2 (contrarian entry) from the latest date
4. **Risk warning**: Flag when market-wide Flow and Mom are highly correlated (reducing factor discrimination)

## Scope Boundaries

**In scope:**
- Factor computation for sector ETFs only (not index ETFs or individual stocks)
- 3 preset parameter combinations
- 7 chart types as specified
- Text summary with investment guidance
- Alembic migration for 4 new tables
- Navigation update across all 4 templates

**Out of scope:**
- User-configurable custom parameters beyond presets
- Index ETF or individual stock factor analysis
- Backtesting with actual portfolio construction
- Email/alert notifications
- Authentication or role-based access for recompute endpoint
