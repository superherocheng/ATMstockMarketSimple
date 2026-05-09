# Mobile-First Simplification — ATMstockMarket

**Date:** 2026-05-09
**Status:** Draft (awaiting user review)
**Version:** 1.0

---

## 1. Objective

Transform the ATMstockMarket web application from a desktop-oriented dual-frontend (Jinja2 + React) platform into a **lightweight, mobile-first** single-frontend app that:
- Loads and renders in under 2 seconds on 4G
- Is maintainable by one person
- Has zero build step for the frontend
- Works perfectly on iOS Safari and Android Chrome

The target feature set is the **homepage (overview dashboard)** and **ETF pages** (index ETF detail + sector ETF rotation/comparison).

---

## 2. Scope — What Stays vs What Goes

### 2.1 Pages — Kept

| Route | Template | Description |
|-------|----------|-------------|
| `/` | `index.html` | ETF overview cards, sector heatmap, data management panel |
| `/etf` | `etf.html` | Index ETF K-line, share chart, anomaly detection |
| `/sector` | `sector.html` (shared with etf.py router) | Sector ETF cards, compare chart, share comparison, fund flow matrix, dual-ETF overlay |

### 2.2 Backend — Kept (trimmed)

| Module | Reason |
|--------|--------|
| `src/web/app.py` | Entry point — remove dead router imports |
| `src/web/routers/overview.py` | Homepage API |
| `src/web/routers/etf.py` | ETF + sector APIs |
| `src/web/routers/fetch.py` | Data management panel |
| `src/core/db_manager_postgresql.py` | Database engine |
| `src/core/trading_calendar.py` | Trade date logic |
| `src/data_fetchers/tushare_fetcher.py` | Primary data source |
| `src/data_fetchers/external_loader.py` | ALLSYMBOL classification loader |
| `config/config.py` | ETF definitions, thresholds |
| `src/web/services/cache.py` | In-memory cache (remove DB tier) |
| `src/web/services/middleware.py` | Rate limiting, cache headers |
| `src/web/services/validators.py` | Input validation |

### 2.3 Removed — Complete

| Layer | What | Impact |
|-------|------|--------|
| Frontend | `frontend/` directory (React SPA) | Removes 2.5MB `node_modules`, Vite build, TypeScript compilation |
| Pages | `/stocks`, `/stock/{code}`, `/barra`, `/concept`, `/industry` | 5 routers, 5 templates, 5 frontend pages |
| Routers | `stocks.py`, `barra.py`, `concept.py`, `industry.py` | 4 Python files + their imports |
| Data | AKShare fetcher, LHB CSV pipeline | `akshare_fetcher.py`, LHB endpoint, CSV directory |
| Analytics | `src/analytics/barra.py` | Entire BARRA factor module (4 factor models) |
| Scripts | 13 of 16 scripts | Keep: `verify_etf_adj.py`, `load_allsymbol.py`, `quick_update.sh` |
| Cache | `precomputed_cache` DB table, `_db_cache_*` functions | Eliminates DB cache tier entirely |
| Services | `utils/` directory, `src/web/services/db.py` | Merged into `db_manager_postgresql.py` |
| Docs | `design-system/` directory | Stale handover artifacts |
| Features | Dual ETF compare, ETF anomaly precomputation, `etf_anomalies` table | Niche features not used on kept pages |

### 2.4 Removed — Partial (consolidated into core)

- `db.py` → merged into `db_manager_postgresql.py`
- Cache DB tier → removed, only in-memory LRU remains
- Static JS: 12+ files → merged into 2 bundles
- Static CSS: 3 files → merged into 1 file

---

## 3. Architecture — Mobile-First Frontend

### 3.1 Principles

- **Zero build tools.** No npm, no Vite, no webpack, no TypeScript compiler. Raw HTML + vanilla JS.
- **Self-hosted dependencies.** No CDN calls for ECharts or fonts. Everything ships with the app.
- **3 requests per page load.** HTML (with inline critical CSS) → app.css → app.js.
- **Tree-shaken ECharts.** Only includes candlestick, bar, line, scatter, treemap, tooltip, dataZoom — the chart types used by the kept pages.

### 3.2 File Structure

```
src/web/static/
├── css/
│   └── app.css              # Single minified stylesheet (merged from 3 files)
├── js/
│   ├── vendor.js             # ECharts minimal build + polyfills (defer)
│   └── app.js                # All page logic: nav, utils, chart-loader, cache, perf
├── fonts/                    # System font fallback only (no Google Fonts download)
└── favicon.svg
```

### 3.3 Mobile Responsiveness

**Layout:**
- Bottom tab bar on mobile (≤768px) — 3 tabs: Home, Index ETFs, Sector ETFs
- Top nav bar on desktop (>768px) — same tabs, horizontal
- All interactive elements ≥44px tap target (Apple HIG compliant)
- Tables horizontally scrollable with sticky headers
- Chart containers use `dvh` units for height, never fixed px

**Performance:**
- ECharts bundled with only required chart types (~150KB vs ~400KB full)
- API responses cached in `sessionStorage` with TTL (revisit loads from cache instantly)
- Lazy-load charts: chart container shows skeleton until ECharts loads
- `IntersectionObserver` pauses chart rendering for offscreen sections

**Offline:**
- Data from last successful API call stored in `localStorage`
- If network fails, page renders with stale data + "last updated" timestamp
- User can still navigate and review cached charts

### 3.4 CSS Strategy

Replace Tailwind CDN + 3 custom CSS files with:
- A single `app.css` using CSS custom properties for theming (light/dark)
- Utility classes only for what we use (grid, flex, spacing, colors)
- No external dependencies. No font download.
- Media queries: mobile-first, breakpoints at 640px, 768px, 1024px

---

## 4. Backend Changes

### 4.1 Removed Imports & Routers

In `app.py`:
```python
# Remove these imports:
from src.web.routers import stocks, barra, concept, industry

# Remove these includes:
app.include_router(stocks.router)
app.include_router(barra.router)
app.include_router(concept.router)
app.include_router(industry.router)
```

Remove router files: `stocks.py`, `barra.py`, `concept.py`, `industry.py`

### 4.2 Cache Simplification

In `cache.py`:
- Remove `_db_cache_get()`, `_db_cache_set()`, `_db_cache_invalidate()`, `_is_data_stale()`
- Remove `precomputed_cache` table from DB schema
- Simplify `_cached_persistent()` to only use in-memory `ThreadSafeCache`

### 4.3 DB Consolidation

- Move `get_conn()`, `query()`, `safe_json()`, `safe_dict()` from `db.py` into `db_manager_postgresql.py`
- Delete `src/web/services/db.py`
- Update all imports across remaining files

### 4.4 Removed Data Pipelines

- Delete `src/data_fetchers/akshare_fetcher.py`
- Delete `data/akshare/` directory
- Remove `POST /api/fetch/akshare` from `fetch.py`
- Remove LHB-related endpoints from `stocks.py` (router removed, so automatically gone)

### 4.5 Removed Analytics

- Delete `src/analytics/` directory entirely (only contained `barra.py`)

### 4.6 Script Cleanup

Delete these from `scripts/`:
- `check_data.py`, `check_industry_data.py`, `check_industry_api.py`, `check_dates.py`
- `fetch_concept.py`, `fetch_concept_slow.py`, `generate_market_value_data.py`
- `sync_external_data.py`, `migrate_to_postgresql.py`, `init_database.py`
- `test_all.py`, `clear_barra_cache.py`, `__init__.py`
- `package.sh`, `publish.sh`, `safe_data_update.sh`, `update_data_safely.sh`

Keep:
- `verify_etf_adj.py`
- `load_allsymbol.py`
- `quick_update.sh`

---

## 5. Data Flow

```
Browser                          FastAPI Server                   PostgreSQL
──────                            ────────────                    ──────────
GET /                              → overview.py
  ← HTML (app.css + app.js refs)     → _compute_overview()
                                       → get_conn()
                                         → SQL: index_etf_daily
                                         → SQL: sector_etf_daily
                                       ← cache.in-memory (4h TTL)
                                     ← JSON response
                                   render index.html with data
                                 
GET /etf                           → etf.py
  ← HTML                             → _compute_index_etf()
                                       → get_conn()
                                         → SQL: index_etf_daily
                                         → SQL: etf_share
                                       → _apply_etf_adj()
                                       → _detect_anomalies()
                                       ← cache.in-memory (4h TTL)
                                     ← JSON response
                                   render etf.html with data
```

No complexity beyond what already exists. The simplification is in what's **removed**, not what's added.

---

## 6. No-Regret Early Steps (Phase 0)

These can be done immediately without waiting for any design decision:

1. Remove React SPA (`frontend/` directory)
2. Remove `design-system/` directory
3. Remove stale scripts
4. Remove `utils/` directory
5. Merge `db.py` into `db_manager_postgresql.py`

These are pure cleanup: no feature loss, no risk of breaking active pages.

---

## 7. Implementation Order

| Phase | What | Risk | Est. Effort |
|-------|------|------|-------------|
| 0 | No-regret cleanup (React SPA, scripts, design-system, utils) | None | 30 min |
| 1 | Cache simplification (remove DB tier) | Low | 20 min |
| 2 | Remove unused routers + templates (stocks, barra, concept, industry) | Low | 30 min |
| 3 | Remove AKShare + analytics | Low | 15 min |
| 4 | Merge JS/CSS files, remove CDN deps, self-host ECharts | Medium | 1 hr |
| 5 | Mobile responsive CSS overhaul of index.html + etf.html + sector.html | Medium | 2 hr |
| 6 | sessionStorage caching, offline resilience | Medium | 1 hr |
| 7 | Final testing on iOS + Android + desktop | Low | 30 min |

**Total estimated effort:** ~6 hours of focused work.

---

## 8. Success Criteria

- Homepage loads in <2s on 4G (measured from navigation start)
- All ETF charts render correctly on 375px (iPhone SE) and 414px (iPhone Plus) viewports
- All tap targets ≥44px
- Page works fully offline after first load (cached data)
- No CDN calls during page load
- Zero npm/node dependencies
- Server footprint: 4 routers instead of 8, 6 data tables instead of 12, ~40 Python files instead of ~80

---

## 9. Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| ECharts self-hosting breaks on older iOS | Low | Test on iOS 15+; Safari has 95%+ market share among iOS users |
| Merge of JS files introduces variable conflicts | Medium | Wrap each module in an IIFE or use ES modules (native `type="module"`) |
| Removing React SPA breaks `/react/` links | Low | Remove the route from `app.py`; visitors to `/react/` get 404 which redirects to `/` via error handler |
| sessionStorage cache shows stale data | Low | Show "last updated" timestamp on every chart; user can pull-to-refresh |
