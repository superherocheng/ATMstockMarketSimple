#!/usr/bin/env python3
"""Comprehensive integration test for ATMstockMarket v2.0."""
import subprocess, sys, time, json, os, signal

HOST = "http://localhost:8000"
PASS = 0
FAIL = 0

def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        print(f"  ✅ {label}")
        PASS += 1
    else:
        print(f"  ❌ {label} — {detail}")
        FAIL += 1

def fetch(path):
    import urllib.request
    try:
        req = urllib.request.Request(f"{HOST}{path}")
        resp = urllib.request.urlopen(req, timeout=10)
        body = resp.read().decode("utf-8")
        return resp.status, body, resp.headers
    except Exception as e:
        return 0, str(e), {}

# ── Start server ──
print("=" * 60)
print("ATMstockMarket v2.0 Integration Tests")
print("=" * 60)

# ── 1. Route tests ──
print("\n📄 Page routes (expect 200 + valid HTML):")
for route, label in [
    ("/", "Homepage"),
    ("/etf", "ETF page"),
    ("/sector", "Sector page"),
    ("/stocks", "Stocks page"),
    ("/barra", "Barra page"),
    ("/concept", "Concept page"),
    ("/industry", "Industry page"),
]:
    status, body, _ = fetch(route)
    check(f"{label} ({route})", status == 200 and "</html>" in body.lower(),
          f"status={status}, has_html={'</html>' in body.lower()}")

# ── 2. API endpoint tests ──
print("\n🔌 API endpoints (expect 200 + valid JSON):")
api_routes = [
    ("/api/overview", "Overview"),
    ("/api/heatmap", "Heatmap"),
    ("/api/data-range", "Data range"),
    ("/api/index-etf/510300.SH", "Index ETF detail"),
    ("/api/sector-etf/562500.SH", "Sector ETF detail (RobotETF)"),
    ("/api/sector-cards", "Sector cards"),
    ("/api/barra/summary", "Barra summary"),
    ("/api/barra/industry", "Barra industry"),
    ("/api/concept/list", "Concept list"),
    ("/api/industry/analysis", "Industry analysis"),
]
for route, label in api_routes:
    status, body, _ = fetch(route)
    is_json = False
    try:
        json.loads(body)
        is_json = True
    except:
        pass
    check(f"{label} ({route})", status == 200 and is_json,
          f"status={status}, is_json={is_json}")

# ── 3. Health check ──
print("\n🩺 Health endpoint:")
status, body, _ = fetch("/health")
check("Health check returns 200", status == 200, f"status={status}")

# ── 4. ETF list completeness ──
print("\n🔍 ETF completeness (RobotETF must be present):")
status, body, _ = fetch("/api/sector-cards")
if status == 200:
    try:
        cards = json.loads(body)
        codes = [c["ts_code"] for c in cards]
        names = [c["name"] for c in cards]
        check("RobotETF (562500.SH) in sector cards", "562500.SH" in codes,
              f"codes={codes}")
        check("RobotETF name present", any("机器人" in n for n in names),
              f"names={names}")
    except:
        check("Parse sector cards JSON", False, "JSON parse failed")
else:
    check("Fetch sector cards", False, f"status={status}")

# ── 5. Stock detail page ──
print("\n📈 Stock detail route:")
status, body, _ = fetch("/stock/600519.SH")
check("Stock detail page serves", status == 200 and "stock-header" in body,
      f"status={status}, has_stock_header={'stock-header' in body}")

# ── 6. Gzip compression ──
print("\n📦 Gzip compression:")
import urllib.request
try:
    req = urllib.request.Request(f"{HOST}/")
    req.add_header("Accept-Encoding", "gzip")
    resp = urllib.request.urlopen(req, timeout=10)
    ce = resp.headers.get("Content-Encoding", "")
    check("Gzip enabled", "gzip" in ce, f"Content-Encoding={ce}")
except Exception as e:
    check("Gzip check", False, str(e))

# ── 7. SEO / Mobile meta tags ──
print("\n📱 Mobile meta tags:")
status, body, _ = fetch("/")
if status == 200:
    check("Viewport meta present", 'name="viewport"' in body, "Missing viewport meta")
    check("Theme-color meta present", 'name="theme-color"' in body, "Missing theme-color meta")

# ── 8. CSS variable completeness ──
print("\n🎨 CSS critical variables:")
with open("src/web/static/css/tokens-wiki.css") as f:
    css = f.read()
check("--c-zero defined", "--c-zero:" in css, "Undefined in tokens-wiki.css")
check("--c-up defined", "--c-up:" in css, "Undefined in tokens-wiki.css")
check("--c-down defined", "--c-down:" in css, "Undefined in tokens-wiki.css")

# ── 9. JS file integrity ──
print("\n📜 JavaScript syntax check:")
import re
js_files = [
    "src/web/static/js/utils.js",
    "src/web/static/js/nav.js",
    "src/web/static/js/mobile.js",
    "src/web/static/js/gestures.js",
    "src/web/static/js/perf.js",
    "src/web/static/js/performance.js",
    "src/web/static/js/theme.js",
    "src/web/static/js/cache.js",
    "src/web/static/js/chart-loader.js",
]
for js in js_files:
    try:
        with open(js) as f:
            content = f.read()
        # Basic syntax check: balanced braces
        opens = content.count("{")
        closes = content.count("}")
        check(f"{os.path.basename(js)} braces balanced", opens == closes,
              f"opens={opens}, closes={closes}")
    except FileNotFoundError:
        check(f"{js} exists", False, "File not found")

# ── 10. React build integrity ──
print("\n⚛️ React build:")
react_index = "src/web/static/react/index.html"
try:
    with open(react_index) as f:
        content = f.read()
    check("React index.html exists", True)
    check("React index has root div", 'id="root"' in content)
    check("React references built CSS", '.css"' in content)
    check("React references built JS", '.js"' in content)
except FileNotFoundError:
    check("React index.html exists", False, "File not found")

# ── Summary ──
print("\n" + "=" * 60)
total = PASS + FAIL
print(f"Results: {PASS}/{total} passed, {FAIL}/{total} failed")
if FAIL > 0:
    sys.exit(1)
else:
    print("All tests passed!")
    sys.exit(0)
