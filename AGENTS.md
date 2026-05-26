# ATMstockMarketSimple — Project Map

> Auto-generated from CodeGraph. Update via `codegraph sync && codegraph context` when the codebase changes substantially.

## Overview

**A股ETF量化监控平台** — Chinese A-Share ETF Quantitative Monitoring Platform.

- **Stack**: Python 3.12 + FastAPI + PostgreSQL + Jinja2 + Tailwind CSS + ECharts 5 + Redis
- **Data source**: Tushare Pro
- **DB migration**: Alembic (6 migration versions)
- **Indexed by CodeGraph**: 969 nodes, 878 edges, 59 files, 874ms index time

## Architecture (Layered)

```
src/web/routers/     ← HTTP API layer (FastAPI routes)
src/web/services/    ← Cache, middleware (rate limiter)
src/web/templates/   ← Jinja2 SSR pages
src/analysis/        ← Factor models, IC analysis, recommendations
src/data_fetchers/   ← Tushare Pro data ingestion
src/core/            ← DB connection pool, trading calendar
ale.../versions/     ← DB schema migrations
scripts/             ← Backtest tools, verification scripts
tests/               ← pytest unit tests
```

### Module Dependency Direction

```
routers → services/cache → db_manager_postgresql
routers → analysis/* → db_manager_postgresql
data_fetchers → db_manager_postgresql, trading_calendar
```

**Core dependency** (most-called functions): `execute()` (105×), `get_db_manager()` (23×), `get_conn()` (21×), `get_connection()` (18×), `query()` (12×), `upsert_dataframe()` (8×), `insert_dataframe()` (5×).

## Module Breakdown

### `src/core/` — Infrastructure

#### `db_manager_postgresql.py` — DB Connection Pool
- **class** `PostgreSQLConnectionManager` (L26–234): Singleton connection pool manager. Methods:
  - `execute(sql, params)` — generic SQL exec (105 calls across codebase)
  - `query(sql, params)` — returns pd.DataFrame
  - `insert_dataframe(df, table, if_exists, primary_key)` — batch insert
  - `upsert_dataframe(df, table, primary_key)` — upsert via INSERT ... ON CONFLICT
  - `execute_batch(operations)` — multi-statement
- Module-level helpers: `init_db_manager(db_url)`, `get_db_manager()`, `get_conn()`, `close_db_manager()`, `query(sql, params)`, `safe_json(df)`, `safe_value(value)`, `safe_dict(d)`
- **Connection**: Psycopg2 with positional-param adapter (`%s` → `?`)

#### `trading_calendar.py` — A-Share Calendar
- `now_beijing()` — current time in Asia/Shanghai
- `get_open_trade_dates(start, end)` — trade calendar from DB
- `get_latest_trading_date()` — most recent trade date
- `get_db_max_date(table, ts_code)` — latest date in a DB table
- `is_fresh(table, ts_code)` — check if table has data up to yesterday
- `get_dates_to_fetch(table, ts_code, start_date)` — date range gap detection
- `verify_database()` — full DB health check

### `src/data_fetchers/` — Data Ingestion

#### `tushare_fetcher.py` (49 nodes, largest src file)
- **26 functions**, heavily modularized by data domain:
  - `init_db()` — DB init + alembic migrations
  - `fetch_index_etf()` — 核心指数ETF (沪深300/中证500/上证50/中证1000/科创50)
  - `fetch_sector_etf()` — 15 行业ETF + 商品ETF
  - `fetch_stock_list()` — A股股票列表
  - `fetch_stock_daily()` — 个股日线行情 (复权处理)
  - `fetch_daily_basic()` — 每日估值数据 (PE/PB/市值)
  - `fetch_fina_indicator()` — 季度财务指标 (ROE/净利率/负债率等)
  - Helper pattern: `_fetch_etf_shares_write_ready()`, `_fetch_etf_adj_factors()`, `_apply_etf_adj()` for ETF data
  - Batch-writing: `_write_fina_batch()` for financial data
  - Internal tools: `_api_call()` (rate-limited Tushare proxy), `_validate()`, `_upsert_write()`, `_get_max_date()`, `_is_fresh()`
- **Main entry**: `main()` — orchestrated data pipeline

#### `external_loader.py` — External CSV Data
- `load_csv_data(csv_path)` — load external symbol CSV
- `normalize_column_names(df)` — column normalization
- `extract_and_load_data(df)` — structured extraction from CSV concepts
- `verify_data()`, `update_meta_file()`, `main()`

### `src/analysis/` — Quantitative Analysis

#### `factor_engine.py` — Multi-Factor Model (kernel component)
**10 functions, vectorized batch computation**:

| Function | Purpose | Lookback |
|----------|---------|----------|
| `_compute_rsrs_series(highs, lows, N)` | RSRS: 阻力支撑相对强度 | N=18 (default) |
| `_compute_flow_series(shares, N, halflife=3)` | Flow: 资金流向 (EWMA斜率) | N=20 |
| `_compute_mom_series(closes, N, vol_window=60)` | Mom: 波动率调整动量 | N=20 |
| `_cross_sectional_zscore(values)` | Rank秩标准化 (rank → percentile → z) | — |
| `_classify_quadrant(z_flow, z_mom)` | Q1/Q2/Q3/Q4 四象限分类 | — |
| `_compute_preset_factors(pid, kline_df, share_df, has_rsrs)` | 向量化批量计算全量ETF因子 (core loop) | — |
| `compute_all_factors(preset_id)` | Public entry: 并行计算4组预设 | — |

Supporting: `_fetch_factor_base_data()` (DB全表扫描仅一次), `_get_latest_financial_factors()`, `_get_adjusted_weights()`.

#### `financial_factor.py` — Fundamental Quality Factor
**12 functions** — computes Quality sub-scores per ETF:
- `_stock_code_to_tushare(code)` — 股票代码格式转换
- `_fetch_latest_roe()`, `_fetch_pb_data()`, `_fetch_latest_netprofit_yoy()`, `_fetch_latest_circ_mv()` — Tushare data fetchers
- `_aggregate_by_sector(constituent_codes, factor_dict, weight_dict)` — 从成分股聚合到ETF
- `compute_financial_factors(calc_date)` → `persist_financial_factors()` → `load_latest_financial_factors()` → `compute_and_persist()`

#### `ic_analyzer.py` — IC Analysis
- `_compute_ic_for_date(factors, forward_returns)` — Spearman Rank IC per date
- `_compute_ic_summary(ic_series)` → dict with IC mean, ICIR, win rate, t-stat
- `_compute_preset_ic(pid, price_df, all_dates, date_idx)` — 向量化批量IC计算
- `compute_all_ic(preset_id)` — public entry point

#### `intraday_efficiency.py` — Intraday Efficiency Factor
- `_daily_efficiency_ohlc(opens, highs, lows, closes)` — OHLC-based排列熵代理
- `_smooth_5(efficiency)` — 5-day SMA
- `_ewma_halflife(series, halflife)` — MACD式EWMA差值
- `_compute_intraday_efficiency_series(opens, highs, lows, closes)` — full pipeline
- `compute_efficiency_for_etf(etf_df)` — batch interface

#### `market_timing.py` — Market Timing
- `_compute_rsi(closes, period=14)` — RSI计算
- `compute_market_timing()` → dict with RSI + momentum + share flow signals

#### `barra_neutralization.py` — Risk Factor Neutralization
- `compute_risk_factors(etf_returns, market_returns, size_proxy, window=60)` — Barra-style risk factors
- `neutralize_factors(factor_z_scores, risk_factors)` → industry/market-neutralized scores
- Internal: `_ols_residual()`, `_ridge_residual()`, `_composite_orthogonalize()`, `Z_score()`

#### `presets.py` — Preset Configuration
- `get_preset(preset_id)` → weight dict (RSRS/Flow/Mom/Quality/Efficiency/RSI_Mom)
- `all_preset_ids()` → ['short', 'medium', 'long']

#### `rsi_factor.py` — RSI Momentum Factor (V6)
- `compute_rsi_momentum_for_etf(close, fd_share)` → RSI(5)-RSI(20) series per ETF

#### `recommendation_engine.py` — Investment Recommendation
- `build_investment_recommendation(preset_id="short")` → full recommendation dict:
  - Six-factor scoring + RSRS quadrant coverage
  - Two-stage correlation penalty (candidate pool → top 10 → pairwise → top 5)
  - Market timing overhead (adjusts position ±30%)
  - Single ETF position cap 25%
  - Rolling ICIR decay detection (60d window)

#### `chart_builder.py` — Data for Charts (ECharts backend)
- `build_factor_distribution(preset_id)` → radar/bar chart data
- `build_ic_series(preset_id)` → IC time series
- `build_quadrant_heatmap(preset_id)` → quadrant scatter
- `build_group_returns(preset_id)` → group return curves
- `build_rolling_icir(preset_id, window=60)` → rolling ICIR
- `build_summary(preset_id)` → IC summary card

### `src/web/` — Web Layer

#### Routes

| Route (src/web/routers/) | Endpoints |
|--------------------------|-----------|
| **overview.py** (10 fn) | `GET /` (index), `GET /api/overview`, `GET /api/heatmap`, `GET /api/validate-analysis`, `GET /health`, `GET /api/data-range`, `GET /api/data-range` (validate_analysis_data) |
| **analysis.py** (16 fn) | `GET /analysis`, `GET /analysis/tech-notes`, `GET /analysis/investment-recommendation`,<br>`GET /api/analysis/presets`, `/factor-distribution`, `/ic-series`, `/quadrant-heatmap`, `/group-returns`, `/rolling-icir`, `/ic-summary-all`, `/summary`,<br>`GET /api/investment-recommendation`,<br>`GET /api/market-timing`,<br>`GET /api/analysis/financial-factors`,<br>`POST /api/analysis/recompute-financial`,<br>`POST /api/analysis/recompute` |
| **etf.py** (14 fn) | `GET /etf`, `GET /sector`,<br>`GET /api/index-etf/{ts_code}`,<br>`GET /api/sector-etf/all`, `/sector-etf/{ts_code}`, `/sector-cards`, `/share-std/{ts_code}` |
| **fetch.py** (11 fn) | `GET /fetch`,<br>`POST /api/fetch`,<br>`GET /api/fetch-status`,<br>`GET /api/etf-share-status`,<br>`POST /api/etf-share-update`,<br>`POST /api/cache-invalidate` |
| **telemetry.py** (1 fn) | Telemetry endpoint |

#### `app.py` — FastAPI App
- `lifespan(app)` — startup/shutdown: init DB, warm cache

#### `services/cache.py` — Dual Cache
- **Redis** (optional): `_redis_get()`, `_redis_set()`, `_redis_delete()`
- **Memory LRU** (always): class `LRUCache` (maxsize=1000, TTL-aware, lru eviction)
- Tiered: `_cache_get()`, `_cache_set()`, `_cached(key, fn, ttl)`, `_cached_persistent(key, fn, max_age_hours=6)`

#### `services/middleware.py` — Middleware
- class `RateLimiter` (token bucket, 60 req/min per client)
- `rate_limit_middleware()` — applies rate limiter
- `add_cache_headers()` — Cache-Control headers

### Database Schema (6 Alembic migrations)

1. **001_initial_schema**: `etf_daily`, `etf_share`, `trade_dates`, `stock_daily`, `stock_list`, `daily_basic`, `fina_indicator`
2. **002_analysis_tables**: `factor_daily`, `ic_analysis`, `factor_preset_weights`
3. **003_add_rsrs_columns**: RSRS columns into `factor_daily`
4. **004_add_financial_factor_table**: `financial_factors`
5. **005_add_quality_to_factor_daily**: Quality score column
6. **006_add_intraday_efficiency**: Intraday efficiency columns

### Five-Factor Model

```
Composite = w_rsrs × z_rsrs + w_flow × z_flow + w_mom × z_mom
          + w_quality × z_quality + w_efficiency × z_efficiency
```

Presets:

| Preset | RSRS | Flow | Mom | Qual | Eff | RSI_Mom | Horizon |
|--------|:----:|:----:|:---:|:----:|:---:|:-------:|:-------:|
| short | 0.258 | 0.129 | 0.258 | 0.184 | 0.092 | 0.08 | H=10 |
| medium | 0.193 | 0.193 | 0.258 | 0.184 | 0.092 | 0.08 | H=20 |
| long | 0.161 | 0.161 | 0.322 | 0.184 | 0.092 | 0.08 | H=40 |

### Test Structure

| Test file | Test classes |
|-----------|-------------|
| tests/unit/test_cache.py | 13 methods (LRU, TTL, concurrency) |
| tests/unit/test_config.py | 12 methods (env, ETF lists, cache config) |
| tests/unit/test_db_manager.py | 5 methods (positional params, upsert) |
| tests/unit/test_factor_engine.py | 17 methods (RSRS/Flow/Mom/zscore/quadrant) |
| tests/unit/test_financial_factor.py | 29 methods (code conversion, aggregation, quality) |
| tests/unit/test_ic_analyzer.py | 5 methods (IC computation, summary) |
| tests/unit/test_rate_limiter.py | 7 methods (bucket, TTL, concurrency) |

### Hot Paths & Optimization Notes

1. **Data fetch** (`tushare_fetcher.py` → `db_manager_postgresql.py`): 40 intra-module + 40 cross-module calls. Batch writes via `upsert_dataframe`.
2. **Factor computation** (`factor_engine.py`): vectorized numpy, single DB scan for base data, 5-8× faster than original per-ETF loop.
3. **Cache-first**: Routers call `_cached_persistent()` before hitting DB. Memory LRU is always-on; Redis is optional.
4. **DB bottleneck**: `execute()` is the #1 called function (105×). Any optimization to PostgreSQL interaction yields outsized gains.

### Config (`config/config.py`)

- `TUSHARE_TOKEN` (env or default)
- `INDEX_ETF_DICT` — 5 core index ETFs
- `SECTOR_ETF_DICT` — 15 sector ETFs + commodity ETFs
- `LOOKBACK_WINDOWS` — RSRS/Mom lookback presets
- `ANOMALY_THRESHOLD` — share change anomaly detection
- `CACHE_DEFAULT_TTL` / `CACHE_MAXSIZE`
- `REDIS_URL` / `REDIS_TTL`
- `DB_URL` (env: `DATABASE_URL`)

### CodeGraph Refresh

When the codebase changes significantly:
```bash
codegraph sync
# or for a full rebuild:
codegraph index
```

To refresh this file, run:
```bash
codegraph context "ATMstockMarketSimple full project summary" -n 200 --no-code > AGENTS.md
```
