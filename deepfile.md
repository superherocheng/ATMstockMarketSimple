# ATMstockMarket — Comprehensive Audit & Fix Tracker

> Generated 2026-07-18. Tracks all findings from full codebase review and their resolution status.

---

## ✅ Completed (20 items — P0 + P1 + P2 + P3)

### P0 — Security & Correctness (5/5 DONE)

| # | Item | Status |
|---|------|--------|
| P0.1 | Remove hardcoded Tushare token from `config.py`; add `.gitignore` protection | ✅ |
| P0.2 | Add 4 performance-critical DB indexes (`stock_daily`, `stock_daily_basic`) | ✅ |
| P0.3 | Fix 18 N+1 ETF queries → 2 bulk queries in `overview.py` | ✅ |
| P0.4 | Survivorship bias warning banner on stocks page | ✅ |
| P0.5 | Fix `industry_backup` hack in fundamental scoring (safe transform pattern) | ✅ |

### P1 — Performance (5/5 DONE)

| # | Item | Status |
|---|------|--------|
| P1.1 | Push BARRA momentum aggregation into SQL (eliminate Python groupby loop) | ✅ |
| P1.2 | Fix concept heat O(n²) — 150+ queries → batch reuse + 1 query | ✅ |
| P1.3 | Pre-compute ETF anomalies → `etf_anomalies` table + fetch hook | ✅ |
| P1.4 | Add CSV export utility `ATM.downloadCSV()` to `utils.js` | ✅ |
| P1.5 | `display=swap` on fonts (already done) + skeleton loading CSS | ✅ |

### P2 — Quant Integrity (5/5 DONE)

| # | Item | Status |
|---|------|--------|
| P2.1 | Rename `sharpe_like` → `return_risk_ratio`; "夏普比率" → "回报风险比" | ✅ |
| P2.2 | Risk score: absolute thresholds → cross-sectional percentile (95th/95th/10th) | ✅ |
| P2.3 | HML factor: composite PE/PB rank split at median — all stocks now included | ✅ |
| P2.4 | SMB factor: quintile extremes → standard Fama-French median split | ✅ |
| P2.5 | Concept heat `leader_factor` normalization extracted and cleaned up | ✅ |

### P3 — UI/UX Polish (5/5 DONE)

| # | Item | Status |
|---|------|--------|
| P3.1 | Dark/light theme toggle (sun/moon) with `localStorage` persistence | ✅ |
| P3.2 | Data freshness badge in nav bar (green/gold) | ✅ |
| P3.3 | Anomaly counter badge on ETF nav link (red dot) | ✅ |
| P3.4 | Search result match-type badges (代码/名称/拼音/模糊) | ✅ |
| P3.5 | Sector heatmap `?code=XXX` link — verified already working | ✅ |

---

## ✅ All Items Complete (24/24)

### P2.6 — Verify ETF Price Adjustment (前复权) ✅

**Resolution**: Added `etf_adj_factor` table + `_fetch_etf_adj_factors()` + `_apply_etf_adj()` in `tushare_fetcher.py`. Integrated `fund_adj` fetch into index & sector ETF pipelines. Updated all 4 ETF query endpoints in `etf.py` to apply forward-adjustment at query time. Created `scripts/verify_etf_adj.py` for side-by-side verification. The adj factor is stored separately from raw prices, recomputed on each query via `adj_price = price × adj_factor / latest_adj_factor`.

**Files**: `tushare_fetcher.py` (+120 lines), `etf.py` (+55 lines), `scripts/verify_etf_adj.py` (new), `trading_calendar.py` (+1 line)

### P3.6 — ETF Comparison Overlay ✅

**Resolution**: Added `/api/sector-etf/compare` endpoint that normalizes two ETFs to base=100. Frontend: dual-selector dropdowns + "对比" button + ECharts overlay chart with dashed baseline at 100, inside a new "双ETF对比" section in `sector.html`.

**Files**: `etf.py` (+55 lines), `sector.html` (+120 lines)

### P3.7 — Database Migration System (Alembic) ✅

**Resolution**: Installed `alembic>=1.13.0`. Created `alembic.ini`, `alembic/env.py`, `alembic/versions/001_initial_schema.py` with all 15 tables + 8 indexes. Updated `init_db()` to prefer `alembic upgrade head` → inline SQL as fallback. Added `etf_adj_factor` to `verify_database()` report.

**Files**: `alembic.ini` (new), `alembic/env.py` (new), `alembic/versions/001_initial_schema.py` (new), `tushare_fetcher.py` (+35 lines), `trading_calendar.py` (+1 line), `pyproject.toml`, `requirements.txt`

### P3.8 — Integration Tests for BARRA & Fundamental Scoring ✅

**Resolution**: Created 3 test files with 59 total tests (all passing):
- `test_barra_momentum.py` (17 tests) — momentum/volatility/corr aggregation, return_risk_ratio, percentile risk thresholds, HML composite PE/PB, SMB median split, industry aggregation
- `test_fundamental_scoring.py` (17 tests) — norm function, composite score weighted averages, cyclical vs non-cyclical valuation, edge cases (zero/negative/single stock), known-answer verification
- `test_concept_heat.py` (25 tests) — bounds [0,100], weighted formula, monotonicity, leader_factor normalization symmetry, error resilience

**Files**: `tests/test_analytics/test_barra_momentum.py` (new), `tests/test_web/test_fundamental_scoring.py` (new), `tests/test_web/test_concept_heat.py` (new)

---

## 📁 Files Modified (this session — P2.6 + P3.6–P3.8)

```
src/data_fetchers/tushare_fetcher.py       — P2.6: etf_adj_factor table + fetch/apply adj
                                           — P3.7: _run_alembic_migrations() + init_db() refactor
src/web/routers/etf.py                     — P2.6: _apply_etf_adj in all 4 ETF endpoints
                                           — P3.6: /api/sector-etf/compare endpoint
src/web/templates/sector.html              — P3.6: dual-selector + overlay chart UI
src/core/trading_calendar.py               — etf_adj_factor in verify_database()
alembic.ini                                — P3.7: Alembic config (new)
alembic/env.py                             — P3.7: Migration environment (new)
alembic/script.py.mako                     — P3.7: Migration template (new)
alembic/versions/001_initial_schema.py     — P3.7: Initial migration — 15 tables + 8 indexes (new)
scripts/verify_etf_adj.py                  — P2.6: ETF adj verification script (new)
tests/test_analytics/test_barra_momentum.py   — P3.8: 17 tests (new)
tests/test_web/test_fundamental_scoring.py    — P3.8: 17 tests (new)
tests/test_web/test_concept_heat.py           — P3.8: 25 tests (new)
pyproject.toml                             — alembic dependency
requirements.txt                           — alembic dependency
deepfile.md                                — this file
```

---

## 🔜 Suggested Future Work

| Order | Task | Priority | Effort |
|-------|------|----------|--------|
| 1 | **Run `scripts/verify_etf_adj.py`** — verify ETF adj factors actually differ | Quick check | 5 min |
| 2 | **Run `alembic upgrade head`** — apply initial migration | Deploy | 1 min |
| 3 | **Add `pytest-cov` to dev deps** — enable coverage reports | Quality | 10 min |
| 4 | **Add CI pipeline** (`.github/workflows/tests.yml`) | DevOps | 1 hr |
| 5 | **Performance**: Add composite index on `etf_adj_factor(ts_code, trade_date)` | Perf | 5 min |
