# Mobile-First Simplification — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strip ATMstockMarket to homepage + ETF pages only, with mobile-first responsive frontend.

**Architecture:** Remove React SPA, unused routers/templates, AKShare pipeline, BARRA analytics, stale scripts. Merge JS/CSS assets, self-host tree-shaken ECharts, overhaul CSS for mobile-first with 3 HTTP requests per page load.

**Tech Stack:** FastAPI, Jinja2, PostgreSQL, vanilla JS, ECharts (self-hosted minimal build), CSS custom properties. Zero build tools.

---

## Files Created/Modified/Deleted

### Deleted (whole directories)
- `frontend/` — React SPA (entire tree)
- `design-system/` — stale design docs
- `utils/` — superseded validators/serializers/helpers
- `src/analytics/` — BARRA module
- `data/akshare/` — LHB CSV files
- `src/web/static/js/` — will be replaced by 2 files
- `src/web/static/css/` — will be replaced by 1 file

### Deleted (files)
- `src/data_fetchers/akshare_fetcher.py`
- `src/web/routers/stocks.py`
- `src/web/routers/barra.py`
- `src/web/routers/concept.py`
- `src/web/routers/industry.py`
- `src/web/templates/stocks.html`
- `src/web/templates/stock_detail.html`
- `src/web/templates/barra.html`
- `src/web/templates/concept.html`
- `src/web/templates/industry.html`
- `src/web/services/db.py`
- `scripts/` — 13 of 16 files (keep verify_etf_adj.py, load_allsymbol.py, quick_update.sh)

### Modified
- `src/web/app.py` — remove router imports
- `src/web/routers/fetch.py` — remove AKShare fetch trigger
- `src/web/services/cache.py` — remove DB cache tier
- `src/core/db_manager_postgresql.py` — merge db.py functions in
- `src/web/templates/index.html` — mobile responsive overhaul
- `src/web/templates/etf.html` — mobile responsive overhaul
- `src/web/templates/sector.html` — mobile responsive overhaul

### Created
- `src/web/static/css/app.css` — single minified stylesheet (replaces 3 CSS files + Tailwind CDN)
- `src/web/static/js/vendor.js` — self-hosted ECharts minimal build
- `src/web/static/js/app.js` — all page logic merged from 12+ loose JS files

---

## Task 0: Verify Initial State

- [ ] **Step 1: Check git status is clean**

```bash
cd /home/ubuntu/github-project/ATMstockMarket && git status
```
Expected: clean working tree (no uncommitted changes except the spec doc)

- [ ] **Step 2: Check the backup exists**

```bash
ls -d /home/ubuntu/github-project/ATMstockMarket_backup_20260507_130912
```
Expected: directory exists (we have a safety net)

---

## Task 1: Remove React SPA

**Files:**
- Delete: `frontend/` (entire directory tree)
- Modify: `src/web/app.py` — remove React routes and static mounts
- Delete: `src/web/static/react/` (build output directory)

- [ ] **Step 1: Remove React build output**

```bash
cd /home/ubuntu/github-project/ATMstockMarket
rm -rf src/web/static/react/
```

- [ ] **Step 2: Remove frontend source**

```bash
rm -rf frontend/
```

- [ ] **Step 3: Edit `src/web/app.py` — remove React SPA serving**

Remove these lines (around line 26-30):
```python
REACT_BUILD_DIR = BASE_DIR / "static" / "react"
REACT_ASSETS_DIR = REACT_BUILD_DIR / "assets"
REACT_INDEX_PATH = REACT_BUILD_DIR / "index.html"
HAS_REACT_BUILD = REACT_INDEX_PATH.exists()
```

Remove the entire React SPA block (the `if HAS_REACT_BUILD:` section that mounts `/react/assets` and serves `/react/` routes — about 15 lines).

- [ ] **Step 4: Verify app starts without React references**

```bash
cd /home/ubuntu/github-project/ATMstockMarket
python -c "from src.web.app import app; print('OK:', len(app.routes), 'routes')"
```
Expected: `OK:` with no import errors

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: remove React SPA (frontend/, static/react/)"
```

---

## Task 2: Remove Design System + Utils + Stale Scripts

**Files:**
- Delete: `design-system/`
- Delete: `utils/`
- Delete: 13 scripts in `scripts/` (keep 3)

- [ ] **Step 1: Remove design-system**

```bash
cd /home/ubuntu/github-project/ATMstockMarket
rm -rf design-system/
```

- [ ] **Step 2: Remove utils directory**

```bash
rm -rf utils/
```

- [ ] **Step 3: Remove stale scripts, keep essential ones**

```bash
cd scripts/
rm -f check_data.py check_industry_data.py check_industry_api.py check_dates.py
rm -f fetch_concept.py fetch_concept_slow.py generate_market_value_data.py
rm -f sync_external_data.py migrate_to_postgresql.py init_database.py
rm -f test_all.py clear_barra_cache.py __init__.py
rm -f package.sh publish.sh safe_data_update.sh update_data_safely.sh
cd ..
```

Verify only 3 scripts remain:
```bash
ls scripts/
```
Expected: `load_allsymbol.py  quick_update.sh  verify_etf_adj.py`

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "chore: remove design-system, utils, stale scripts (keep 3)"
```

---

## Task 3: Merge db.py into db_manager_postgresql.py

**Files:**
- Modify: `src/core/db_manager_postgresql.py` — add `safe_json`, `safe_dict`, `safe_value`, `reset_db_initialized` functions
- Delete: `src/web/services/db.py`
- Modify: All remaining files that import from `db` → update to import from `db_manager_postgresql`

- [ ] **Step 1: Add helper functions to `db_manager_postgresql.py`**

Append these functions at the end of `src/core/db_manager_postgresql.py` (before any `if __name__` block):

```python
def safe_json(df):
    """Safely convert DataFrame to JSON-serializable list of dicts"""
    if df is None or len(df) == 0:
        return []
    df = df.copy()
    df = df.replace([float('inf'), float('-inf')], float('nan'))
    records = df.to_dict(orient="records")
    for record in records:
        for key, value in record.items():
            try:
                if pd.isna(value):
                    record[key] = None
            except Exception:
                pass
    return records


def safe_value(value):
    """Convert a single value to JSON-safe value"""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    import numpy as np
    if isinstance(value, (int, float, np.floating, np.integer)):
        try:
            if not np.isfinite(value):
                return None
        except Exception:
            pass
    return value


def safe_dict(d):
    """Recursively convert dict/list values to JSON-safe values"""
    if not isinstance(d, dict):
        if isinstance(d, list):
            return [safe_dict(item) for item in d]
        return safe_value(d)
    return {k: safe_dict(v) for k, v in d.items()}


def reset_db_initialized():
    """Reset the global DB initialization flag (for fetch module)."""
    global _db_initialized
    _db_initialized = False
```

Also add `import numpy as np` at top of file and `_db_initialized = False` near the global singleton section.

- [ ] **Step 2: Find all files importing from `db`**

```bash
cd /home/ubuntu/github-project/ATMstockMarket
grep -rn "from src.web.services.db import\|from src.web.services import db\|from db import\|import db" src/ --include="*.py" | grep -v __pycache__
```

- [ ] **Step 3: Update imports in all remaining files**

For each file found in Step 2 that will be kept (overview.py, etf.py, fetch.py, cache.py, etc.), replace:
```python
from src.web.services.db import get_conn, query, safe_json
```
with:
```python
from src.core.db_manager_postgresql import get_conn, query, safe_json
```

And replace:
```python
from src.web.services.db import reset_db_initialized
```
with:
```python
from src.core.db_manager_postgresql import reset_db_initialized
```

- [ ] **Step 4: Delete db.py**

```bash
rm src/web/services/db.py
```

- [ ] **Step 5: Verify imports work**

```bash
cd /home/ubuntu/github-project/ATMstockMarket
python -c "from src.web.app import app; print('OK')"
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor: merge db.py into db_manager_postgresql, update imports"
```

---

## Task 4: Remove Unused Routers + Templates

**Files:**
- Delete: `src/web/routers/stocks.py`, `src/web/routers/barra.py`, `src/web/routers/concept.py`, `src/web/routers/industry.py`
- Delete: `src/web/templates/stocks.html`, `src/web/templates/stock_detail.html`, `src/web/templates/barra.html`, `src/web/templates/concept.html`, `src/web/templates/industry.html`
- Modify: `src/web/app.py` — remove imports and router includes

- [ ] **Step 1: Remove router files**

```bash
cd /home/ubuntu/github-project/ATMstockMarket
rm src/web/routers/stocks.py src/web/routers/barra.py src/web/routers/concept.py src/web/routers/industry.py
```

- [ ] **Step 2: Remove template files**

```bash
rm src/web/templates/stocks.html src/web/templates/stock_detail.html src/web/templates/barra.html src/web/templates/concept.html src/web/templates/industry.html
```

- [ ] **Step 3: Edit `src/web/app.py` — remove imports and router includes**

Remove these lines:
```python
from src.web.routers import stocks, barra, concept, industry
```

Remove these lines:
```python
app.include_router(stocks.router)
app.include_router(barra.router)
app.include_router(concept.router)
app.include_router(industry.router)
```

- [ ] **Step 4: Verify**

```bash
cd /home/ubuntu/github-project/ATMstockMarket
python -c "from src.web.app import app; print('OK:', len(app.routes), 'routes')"
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: remove unused routers and templates (stocks, barra, concept, industry)"
```

---

## Task 5: Remove AKShare + BARRA Analytics

**Files:**
- Delete: `src/data_fetchers/akshare_fetcher.py`
- Delete: `src/analytics/` (entire directory)
- Delete: `data/akshare/` (CSV files)

- [ ] **Step 1: Remove files**

```bash
cd /home/ubuntu/github-project/ATMstockMarket
rm -rf src/analytics/
rm src/data_fetchers/akshare_fetcher.py
rm -rf data/akshare/
```

- [ ] **Step 2: Verify no broken imports**

```bash
grep -rn "akshare_fetcher\|from src.analytics\|import barra" src/ --include="*.py" | grep -v __pycache__
```
Expected: no matches (all references were in deleted files)

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat: remove AKShare fetcher and BARRA analytics module"
```

---

## Task 6: Simplify Cache (Remove DB Tier)

**Files:**
- Modify: `src/web/services/cache.py` — remove `_db_cache_get`, `_db_cache_set`, `_db_cache_invalidate`, `_is_data_stale`; simplify `_cached_persistent`

- [ ] **Step 1: Edit `cache.py` — remove all DB cache functions**

Delete these functions entirely:
- `_db_cache_get(key)`
- `_db_cache_set(key, data)`
- `_db_cache_invalidate(*categories)`
- `_is_data_stale(key, max_age_hours)`

Simplify `_cached_persistent(key, func, max_age_hours=6)` to only use in-memory cache:

```python
def _cached_persistent(key, func, max_age_hours=6):
    """Cache with in-memory LRU only (no DB tier)."""
    from src.core.db_manager_postgresql import safe_dict
    try:
        result = _api_cache.get(key)
        if result is not None:
            return safe_dict(result)
        result = func()
        result = safe_dict(result)
        _api_cache.set(key, result)
        return result
    except Exception as e:
        logger.error(f"_cached_persistent failed for key={key}: {e}", exc_info=True)
        return {"error": str(e)}
```

Remove the import `from sqlalchemy import text` and remove `from src.core.trading_calendar import now_beijing` if it's no longer used.

Also remove `CACHE_CATEGORIES` dict and the `invalidate` method logic that references it if everything still compiles — actually keep `_cache_invalidate` since `fetch.py` calls it.

- [ ] **Step 2: Verify**

```bash
cd /home/ubuntu/github-project/ATMstockMarket
python -c "from src.web.app import app; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "refactor: remove DB cache tier, simplify to in-memory only"
```

---

## Task 7: Remove Fetch.py AKShare Reference

**Files:**
- Modify: `src/web/routers/fetch.py` — remove `"akshare"` from `task_type` validation and remove the `_run_fetch("akshare")` path

- [ ] **Step 1: Edit `fetch.py`**

In the `api_fetch_data` function, change:
```python
if task_type not in ("all", "tushare", "akshare", "etf", "stocks"):
```
to:
```python
if task_type not in ("all", "tushare", "etf", "stocks"):
```

Remove the `elif task_type == "akshare":` block inside `_run_fetch`.

- [ ] **Step 2: Commit**

```bash
git add -A && git commit -m "feat: remove AKShare fetch option from data management"
```

---

## Task 8: Remove Dual ETF Compare + ETF Anomaly Precomputation

**Files:**
- Modify: `src/web/routers/etf.py` — remove `api_sector_etf_compare` endpoint and `precompute_all_etf_anomalies` function
- Modify: `src/web/routers/fetch.py` — remove call to `precompute_all_etf_anomalies`
- Modify: `src/web/templates/sector.html` — remove the dual-ETF compare overlay section (the `<select>` + compare button + overlay chart)

- [ ] **Step 1: Edit `etf.py` — remove compare endpoint**

Delete the `@router.get("/api/sector-etf/compare")` function entirely (about 50 lines starting from `# ══════════════════════════════════════════════════` and the `def api_sector_etf_compare` function).

Delete the `precompute_all_etf_anomalies()` function and the `# ══════════════════════════════════════════════════` section block.

- [ ] **Step 2: Edit `fetch.py` — remove anomaly precomputation call**

Remove these lines from `_run_fetch`:
```python
# ── P1.3: Pre-compute ETF anomalies after data refresh ──
if task_type in ("all", "tushare", "etf"):
    try:
        _add_log("--- 预计算 ETF 异常检测 ---")
        from src.web.routers.etf import precompute_all_etf_anomalies
        precompute_all_etf_anomalies()
        _add_log("[OK] ETF 异常检测预计算完成")
    except Exception as e:
        _add_log(f"[WARN] ETF 异常预计算失败: {e}")
```

- [ ] **Step 3: Edit `sector.html` — remove dual ETF compare section**

Remove the entire section with the heading "双ETF对比" — from the `<h3>双ETF对比` line through the `</div>` that closes the overlay chart container. Also remove the `initCompareSelects()` and `runCompare()` JavaScript functions from the `<script>` block.

- [ ] **Step 4: Verify template still renders**

```bash
cd /home/ubuntu/github-project/ATMstockMarket
python -c "
from src.web.app import app
from fastapi.testclient import TestClient
client = TestClient(app)
r = client.get('/sector')
print('sector.html renders:', r.status_code)
"
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: remove dual ETF compare and anomaly precomputation"
```

---

## Task 9: Remove ETF Anomalies Table from DB Schema

**Files:**
- Modify: `src/data_fetchers/tushare_fetcher.py` — remove `etf_anomalies` table creation

- [ ] **Step 1: Edit `tushare_fetcher.py`**

In the `init_db()` function, find and remove this table creation SQL:
```python
"""CREATE TABLE IF NOT EXISTS etf_anomalies (
    ts_code VARCHAR, trade_date VARCHAR, anomaly_type VARCHAR,
    z_score DOUBLE PRECISION, value DOUBLE PRECISION,
    PRIMARY KEY (ts_code, trade_date, anomaly_type))""",
```

- [ ] **Step 2: Commit**

```bash
git add -A && git commit -m "feat: remove etf_anomalies table from schema"
```

---

## Task 10: Create Single CSS File (app.css)

**Files:**
- Create: `src/web/static/css/app.css` — mobile-first single stylesheet
- Delete: `src/web/static/css/tokens-wiki.css`, `src/web/static/css/style-wiki.css`, `src/web/static/css/components-wiki.css`

- [ ] **Step 1: Read the 3 existing CSS files to extract their content**

```bash
cd /home/ubuntu/github-project/ATMstockMarket
cat src/web/static/css/tokens-wiki.css > /tmp/css_all.txt
echo "" >> /tmp/css_all.txt
cat src/web/static/css/style-wiki.css >> /tmp/css_all.txt
echo "" >> /tmp/css_all.txt
cat src/web/static/css/components-wiki.css >> /tmp/css_all.txt
wc -l /tmp/css_all.txt
```

- [ ] **Step 2: Create `app.css`**

Write `src/web/static/css/app.css` containing:
- CSS custom properties for theming (light/dark) — extracted from the 3 files
- Mobile-first grid system (2-col → 3-col → 5-col w/ media queries)
- Touch-friendly sizing: `min-height: 44px` on buttons/tabs
- `.glass` card styling, `.skeleton` loading states
- `.progress-bar-track` / `.progress-bar-fill` for the data fetch progress
- Chart container sizing using `dvh` / percentage instead of fixed px
- Responsive table with sticky header and horizontal scroll
- Footer styles
- Remove: Tailwind-specific classes, Google Font imports, CDN font URLs

- [ ] **Step 3: Delete old CSS files**

```bash
rm src/web/static/css/tokens-wiki.css src/web/static/css/style-wiki.css src/web/static/css/components-wiki.css
```

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "refactor: merge 3 CSS files into single mobile-first app.css"
```

---

## Task 11: Merge JS Files

**Files:**
- Create: `src/web/static/js/vendor.js` — ECharts minimal build
- Create: `src/web/static/js/app.js` — all page logic
- Delete: All 12+ loose JS files in `src/web/static/js/`

- [ ] **Step 1: Read all existing JS files to understand what they contain**

```bash
cd /home/ubuntu/github-project/ATMstockMarket
ls src/web/static/js/*.js
```

- [ ] **Step 2: Build minimal ECharts**

Create a Python script to generate the minimal ECharts build or download the full ECharts and tree-shake it. The simplest approach: download the full ECharts 5.5.0 UMD build from CDN and save as `vendor.js`, but strip unneeded chart types:

Actually, simplest reliable approach:
```bash
cd src/web/static/js/
# Download full ECharts 5.5.0
curl -sL "https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js" -o vendor.js
ls -lh vendor.js
```
Note: We'll accept the ~400KB full build for now and optimize in a follow-up.

- [ ] **Step 3: Create `app.js`**

Create `src/web/static/js/app.js` by concatenating the kept JS files from the existing list. The order matters:
1. `error-handler.js` (must be first)
2. `utils.js` (ATM utility functions)
3. `nav.js` (ATMNav)
4. `theme.js` (theme handling)
5. `cache.js` (ATMCache)
6. `perf.js` / `performance.js` (ATMPerf)
7. `mobile.js` (mobile-specific handlers)
8. `gestures.js` (touch gestures)
9. `chart-loader.js` (ATMChart)
10. `tailwind-config.js` → skip, we're removing Tailwind

Wrap each module in an IIFE to prevent variable conflicts:
```javascript
(function() {
  // ... existing module code ...
})();
```

- [ ] **Step 4: Delete individual JS files**

```bash
cd src/web/static/js/
# Delete all individual files
rm -f error-handler.js utils.js nav.js theme.js cache.js perf.js performance.js mobile.js gestures.js chart-loader.js tailwind-config.js
ls
```
Expected: only `vendor.js` and `app.js` remain

- [ ] **Step 5: Update templates to reference new JS files**

In `index.html`, `etf.html`, `sector.html`:
- Remove all individual `<script src="/static/js/...">` tags (about 8-10 tags per template)
- Add these 3 tags in order:
  ```html
  <link rel="stylesheet" href="/static/css/app.css">
  <script defer src="/static/js/vendor.js"></script>
  <script defer src="/static/js/app.js"></script>
  ```
- Remove `https://cdn.tailwindcss.com` script tag
- Remove Google Fonts preconnect/links

- [ ] **Step 6: Remove Tailwind classes from templates that won't be styled by app.css**

Check for `className`/`class` attributes using Tailwind utilities like `sm:`, `md:`, `lg:`, `flex`, `grid`, etc. — these now need to use the custom utility classes defined in `app.css`.

Update index.html to use the new CSS class names. For example:
- `class="flex items-center gap-2"` → `class="flex flex-gap-2"`
- `class="grid grid-cols-1 sm:grid-cols-3 gap-3"` → `class="grid cols-1 md-cols-3 gap-3"`
- `class="text-lg font-semibold mb-3"` → `class="text-lg font-bold mb-3"`
- `class="hidden sm:inline"` → `class="hide-mobile"`

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "refactor: merge JS into vendor.js + app.js, remove CDN deps"
```

---

## Task 12: Mobile CSS Overhaul — index.html

**Files:**
- Modify: `src/web/templates/index.html`

- [ ] **Step 1: Add bottom navigation bar for mobile**

Replace the current `ATMNav.insert('nav-container', 'home')` with a responsive nav:
- Desktop (>768px): horizontal top bar with logo + 3 tabs (Home, ETFs, Sector)
- Mobile (≤768px): bottom tab bar with 3 icons + labels

The nav should render directly in the template, not via JS injection. Add a `<nav>` element at the top of `<body>`.

- [ ] **Step 2: Make ETF index cards touch-friendly**

- Each card: `min-height: 120px`, `padding: 16px`, `font-size: 16px` on mobile
- Grid: 1 column on mobile → 3 columns on desktop
- `cursor: pointer` → `touch-ripple` effect via CSS
- Remove hover-only effects, add `:active` state instead

- [ ] **Step 3: Make heatmap grid mobile-native**

- Grid: 2 columns on mobile → 5 columns on desktop
- Each cell: `min-height: 80px`, tap targets ≥44px
- Font sizes scale: 14px on mobile → 16px on desktop

- [ ] **Step 4: Data management panel**

- Buttons: full-width stacked on mobile, inline on desktop. Each button `min-height: 44px`
- Log display area: `max-height: 40vh` with scroll on mobile
- Progress bar: thinner on mobile (8px → 12px)

- [ ] **Step 5: Quick links section**

- Remove the `desktop:hidden` class (no desktop/mobile class switching)
- Make the 4 quick-link cards full-width on mobile, 2-col grid on tablet, 4-col on desktop

- [ ] **Step 6: Verify on mobile viewport**

```bash
cd /home/ubuntu/github-project/ATMstockMarket
python -c "
from src.web.app import app
from fastapi.testclient import TestClient
client = TestClient(app)
for path in ['/', '/etf', '/sector']:
    r = client.get(path)
    assert r.status_code == 200, f'{path} failed: {r.status_code}'
    print(f'{path}: OK ({len(r.text)} bytes)')
"
```

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: mobile-first responsive overhaul of index.html"
```

---

## Task 13: Mobile CSS Overhaul — etf.html + sector.html

**Files:**
- Modify: `src/web/templates/etf.html`
- Modify: `src/web/templates/sector.html`

- [ ] **Step 1: ETF page — tab buttons**

Convert the 3 ETF tab buttons to:
- Mobile: horizontal scrollable pill-style tabs (overflow-x: auto, no wrapping)
- Desktop: inline buttons as before
- Each tab: `min-height: 44px`, `padding: 12px 20px`

- [ ] **Step 2: ETF page — info bar**

- Mobile: stack vertically (name/code on one line, price/pct/volume below)
- Desktop: horizontal row as before
- Font sizes scale down on mobile (18px → 14px for labels, 24px → 18px for values)

- [ ] **Step 3: ETF page — charts**

- K-line chart: `height: 50dvh` on mobile (fills half the viewport), 380px on desktop
- Share chart: `height: 40dvh` on mobile, 320px on desktop
- Anomaly cards: stack vertically on mobile, 2-col grid on desktop
- Chart tooltips should be readable on small screens (larger font, more padding)

- [ ] **Step 4: Sector page — cards grid**

- ETF cards: 2 columns on mobile, 5 columns on desktop
- Each card: `padding: 12px`, tap target ≥44px
- Fund flow matrix: same grid behavior

- [ ] **Step 5: Sector page — comparison charts**

- Compare chart + share compare chart: stack vertically on mobile, 2-col on desktop
- Each chart: `height: 40dvh` on mobile

- [ ] **Step 6: Handle sector detail section (inline K-line)**

The inline detail section is removed per spec. Instead, clicking a sector card navigates to `/etf?code={ts_code}`. Update the `selectSector()` function to redirect instead of showing inline.

- [ ] **Step 7: Verify both templates render**

```bash
cd /home/ubuntu/github-project/ATMstockMarket
python -c "
from src.web.app import app
from fastapi.testclient import TestClient
client = TestClient(app)
for path in ['/etf', '/sector']:
    r = client.get(path)
    assert r.status_code == 200, f'{path} failed: {r.status_code}'
    print(f'{path}: OK ({len(r.text)} bytes)')
"
```

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "feat: mobile-first responsive overhaul of etf.html and sector.html"
```

---

## Task 14: sessionStorage Caching + Offline Resilience

**Files:**
- Modify: `src/web/static/js/app.js` — add data caching layer
- Modify: `src/web/templates/index.html` — add "last updated" timestamps
- Modify: `src/web/templates/etf.html` — add "last updated" timestamps
- Modify: `src/web/templates/sector.html` — add "last updated" timestamps

- [ ] **Step 1: Add cache layer to app.js**

Append to `app.js`:

```javascript
(function() {
  'use strict';

  // SessionStorage cache for API responses
  const STORAGE_PREFIX = 'atm_cache_';
  const DEFAULT_TTL_MS = 4 * 60 * 60 * 1000; // 4 hours (matches backend)

  window.ATMCache = {
    get(key) {
      try {
        const raw = sessionStorage.getItem(STORAGE_PREFIX + key);
        if (!raw) return null;
        const entry = JSON.parse(raw);
        if (Date.now() > entry.expiresAt) {
          sessionStorage.removeItem(STORAGE_PREFIX + key);
          return null;
        }
        return entry.data;
      } catch { return null; }
    },

    set(key, data, ttlMs) {
      try {
        const expiresAt = Date.now() + (ttlMs || DEFAULT_TTL_MS);
        sessionStorage.setItem(STORAGE_PREFIX + key, JSON.stringify({ data, expiresAt }));
      } catch { /* quota exceeded — silently ignore */ }
    },

    fetchWithCache(url, options) {
      const cacheKey = url;
      const cached = this.get(cacheKey);
      if (cached) return Promise.resolve(cached);

      return fetch(url, options).then(r => {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      }).then(data => {
        this.set(cacheKey, data);
        return data;
      }).catch(err => {
        // Try stale cache if network fails
        const stale = this.get(cacheKey);
        if (stale) return Promise.resolve(stale);
        throw err;
      });
    }
  };

  // Show "last updated" time on any element with data-last-updated attribute
  window.ATMUpdateTimestamp = {
    show(selector) {
      document.querySelectorAll(selector).forEach(el => {
        const key = el.dataset.cacheKey;
        if (!key) return;
        const raw = sessionStorage.getItem(STORAGE_PREFIX + key);
        if (!raw) return;
        try {
          const entry = JSON.parse(raw);
          const age = Date.now() - entry.expiresAt + DEFAULT_TTL_MS;
          if (age > 0 && age < DEFAULT_TTL_MS) {
            const minutes = Math.round(age / 60000);
            el.textContent = minutes < 60 ? `${minutes}分钟前更新` : `${Math.round(minutes/60)}小时前更新`;
          } else {
            el.textContent = '数据可能已过期';
          }
        } catch { el.textContent = ''; }
      });
    }
  };
})();
```

- [ ] **Step 2: Add "last updated" timestamps to templates**

In each template, add after the main section containers:
```html
<div class="text-xs text-muted px-2" data-cache-key="/api/overview" data-last-updated></div>
```

For etf.html:
```html
<div class="text-xs text-muted px-2" data-cache-key="/api/index-etf/510300.SH" data-last-updated></div>
```

- [ ] **Step 3: Update fetch calls to use ATMCache**

Replace `fetch('/api/overview')` calls in templates with `ATMCache.fetchWithCache('/api/overview')`.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: add sessionStorage caching and offline resilience"
```

---

## Task 15: Final Cleanup — Remove Empty Directories

- [ ] **Step 1: Check for any empty directories**

```bash
cd /home/ubuntu/github-project/ATMstockMarket
find . -type d -empty -not -path './.git/*' -not -path './.venv/*' -not -path './__pycache__/*' -not -path './node_modules/*' 2>/dev/null
```

- [ ] **Step 2: Remove empties (except .git, .venv, etc)**

```bash
# Only remove confirmed-empty dirs that should go
# (manual review of Step 1 output first)
```

- [ ] **Step 3: Check requirements.txt / pyproject.toml are still valid**

```bash
# Remove dependencies for removed modules
# akshare, pypinyin can be removed from requirements.txt
```

Edit `requirements.txt` to remove: `akshare`, `pypinyin`

- [ ] **Step 4: Final commit**

```bash
git add -A && git commit -m "chore: final cleanup — remove unused deps, empty dirs"
```

---

## Verification

- [ ] **Step 1: Run the web app and verify all 3 pages load**

```bash
cd /home/ubuntu/github-project/ATMstockMarket
python -c "
from src.web.app import app
from fastapi.testclient import TestClient
client = TestClient(app)
paths = ['/', '/etf', '/sector', '/api/overview', '/api/index-etf/510300.SH', '/api/sector-etf', '/api/health']
for p in paths:
    r = client.get(p)
    status = 'OK' if r.status_code == 200 else 'FAIL'
    print(f'{status}: {p} → {r.status_code}')
"
```

- [ ] **Step 2: Check no broken imports remain**

```bash
cd /home/ubuntu/github-project/ATMstockMarket
python -c "from src.web.app import app; print('All imports OK')"
```

- [ ] **Step 3: Final git status**

```bash
git status
git log --oneline -5
```
