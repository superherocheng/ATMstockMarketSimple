# UI Modern Minimalist Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the "Linen" warm editorial design system into a modern minimalist fintech dashboard with cool gray/white palette, sans-serif fonts, soft shadows, and improved chart/UX details.

**Architecture:** CSS token-driven approach — overwrite design tokens in `app.css`, update component styles, fix chart theme in JS, then patch inline styles in 5 templates. No backend logic changes.

**Tech Stack:** CSS custom properties, ECharts 5, Jinja2 templates, vanilla JS

---

## File Map

| File | Action | Scope |
|------|--------|-------|
| `src/web/static/css/app.css` | Modify | Design tokens + component styles (~3042 lines) |
| `src/web/static/js/app.js` | Modify | Chart theme colors (ATMChart.getChartTheme/getChartThemeDark) |
| `src/web/templates/investment_recommendation.html` | Modify | Inline `<style>` block (lines 16-153) |
| `src/web/templates/rotation.html` | Modify | Inline `<style>` block (lines 14-94) |
| `src/web/templates/sector.html` | Modify | Inline `<style>` block (lines 19-72) |
| `src/web/templates/tech_notes.html` | Modify | Inline `<style>` block (lines 16-26) |
| `src/web/templates/etf.html` | Modify | Inline `<style>` block (lines 19-25) |

---

## Task 1: Design Tokens + Base Styles (CSS)

**Covers:** Global Design System — Color palette, Typography, Spacing, Shadows

**Files:**
- Modify: `src/web/static/css/app.css:14-173` (root tokens)
- Modify: `src/web/static/css/app.css:180-267` (dark mode tokens)
- Modify: `src/web/static/css/app.css:269-328` (base reset + body)

- [ ] **Step 1: Overwrite `:root` design tokens**

Replace lines 14-173 in `app.css`. Key changes:
- Colors: `--color-surface: #F5F7FA`, `--color-neutral: #FFFFFF`, `--color-ink: #1A1A1A`, `--color-graphite: #666666`, `--color-stone: #999999`
- Signal colors: `--c-up: #FF4D4F`, `--c-down: #52C41A`, `--c-warning: #FAAD14`
- Fonts: replace serif references with `Inter, system-ui, -apple-system, sans-serif`
- Remove `--color-hairline` (replace with transparent)
- Update all backward-compat aliases to match new tokens
- Card shadow: `--shadow-card: 0 4px 16px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.06)`
- Add sidebar collapse token: `--sidebar-width: 240px`, `--sidebar-collapsed: 64px`
- Remove border radius zeroing (set `--radius-sm: 6px`, `--radius-md: 8px`, `--radius-lg: 12px`)

- [ ] **Step 2: Update dark mode tokens**

Replace lines 180-267. Update dark palette:
- `--color-surface: #0F1117`, `--color-neutral: #1A1D27`, `--color-ink: #E8EAED`
- `--c-up: #FF4D4F`, `--c-down: #52C41A`
- Update shadow tokens for dark mode

- [ ] **Step 3: Update base body styles**

Modify lines 269-328:
- Body font: `font-family: var(--font-body)` (now sans-serif)
- Body line-height: `1.8` (was 1.55)
- Body background: `var(--color-surface)` (now `#F5F7FA`)
- Remove `a` tag `border-bottom: 1px solid currentColor`

- [ ] **Step 4: Verify base renders correctly**

Run the dev server: `python -m src.web.app` or check via browser. Verify:
- Background is `#F5F7FA`
- Text is `#1A1A1A`
- Fonts are sans-serif (Inter/system)
- No visual breakage in base layout

---

## Task 2: Typography System Update (CSS)

**Covers:** Typography hierarchy, Line height, Font sizing

**Files:**
- Modify: `src/web/static/css/app.css:354-478` (typography section)

- [ ] **Step 1: Update typography scale**

Replace font size tokens:
- `--text-headline-lg` → 24px (was 72px — this is the page title)
- `--text-headline-md` → 16px (was 36px — card title)
- `--text-body-md` → 14px (was 20px — body)
- `--text-body-sm` → 13px (was 18px)
- `--text-label-sm` → 12px (was 14px)
- `--text-mono-sm` → 12px (was 14px)
- Update all font-family declarations to sans-serif

- [ ] **Step 2: Update heading styles**

Update h1-h6 and .t-* classes:
- Line-height: 1.8 for body text
- Letter-spacing: normal (remove editorial tracking)
- Remove `text-transform: uppercase` from labels (keep but make optional)

- [ ] **Step 3: Update body/paragraph styles**

- `p` line-height: 1.8
- `p` margin-bottom: 16px

---

## Task 3: Component Styles — Cards, Sidebar, Buttons (CSS)

**Covers:** Card shadows, Sidebar redesign, Button gradient, Navigation cleanup

**Files:**
- Modify: `src/web/static/css/app.css:1047-1180` (cards)
- Modify: `src/web/static/css/app.css:2482-2622` (sidebar)
- Modify: `src/web/static/css/app.css:881-1014` (buttons)

- [ ] **Step 1: Update card styles**

Replace card styling:
- Remove `border: var(--rule-hairline)` from `.card`, `.glass`, `.data-card`
- Add `box-shadow: var(--shadow-card)`
- Add `border-radius: var(--radius-md)`
- Background: `#FFFFFF`
- Padding: 24px
- Hover: subtle translate + enhanced shadow

- [ ] **Step 2: Update sidebar to minimal list**

Replace sidebar styles:
- Remove gray background on menu items
- Active state: left 2px colored border (`#FF4D4F`), no background fill
- Add collapsible mode: `--sidebar-width: 64px` when collapsed
- Text hidden when collapsed, icon-only

- [ ] **Step 3: Update buttons**

Replace button styles:
- Primary CTA: `background: linear-gradient(135deg, #FF4D4F, #F97316)`
- White bold text, border-radius: 8px
- Hover: `translateY(-2px)` + enhanced shadow
- Ghost/secondary: clean border, no heavy fill

- [ ] **Step 4: Update navigation bar**

- Remove all dark borders from nav elements
- Clean, minimal top/side navigation
- Active indicator: left colored bar only

- [ ] **Step 5: Add colored top borders to home page quick cards**

Add to app.css for `.home-card--quick` elements:
```css
.home-card--quick:nth-child(1) { border-top: 3px solid #4F46E5; }  /* blue — Factor Analysis */
.home-card--quick:nth-child(2) { border-top: 3px solid #7C3AED; }  /* purple — Sector Rotation */
.home-card--quick:nth-child(3) { border-top: 3px solid #F97316; }  /* orange — Investment Advice */
```

---

## Task 4: Chart, Table, Badge Component Styles (CSS)

**Covers:** Table cleanup, Badge capsule tags, Chart grid styling, Anomaly badges

**Files:**
- Modify: `src/web/static/css/app.css:1229-1300` (tables)
- Modify: `src/web/static/css/app.css:1560-1604` (badges/tags)
- Modify: `src/web/static/css/app.css:1856-1962` (chart grid)

- [ ] **Step 1: Update table styles**

- Remove all `border: var(--rule-hairline)` from tables
- Add subtle row separators: `border-bottom: 1px solid #F0F2F5`
- Header background: `#F5F7FA`
- Hover: `#F5F7FA`

- [ ] **Step 2: Update badge/tag styles**

Replace `.tag-green`, `.tag-red`, `.tag-amber` with capsule tags:
- Rounded: `border-radius: 999px`
- Light background: `#FFF1F0` (red), `#F6FFED` (green), `#FFFBE6` (amber)
- Text color: matching bright color
- No dark borders

- [ ] **Step 3: Update anomaly badges**

Replace `.anomaly-badge`:
- Capsule style: rounded, light background
- Text color: red/green based on status
- Remove `color: var(--color-on-ink)` and dark background

- [ ] **Step 4: Update chart cell styles**

- Remove `border: var(--rule-hairline)` from `.chart-cell`
- Add soft shadow
- Add subtle rounded corners

---

## Task 5: Chart Theme (JS)

**Covers:** ECharts color palette, Chart visual consistency

**Files:**
- Modify: `src/web/static/js/app.js:1189-1330` (getChartTheme)
- Modify: `src/web/static/js/app.js:1332-1473` (getChartThemeDark)
- Modify: `src/web/static/js/app.js:321-370` (ATM.getChartTheme)

- [ ] **Step 1: Update getChartTheme() light mode**

Update colors in ATMChart.getChartTheme():
- `axisLineColor`: `#E8EAED` (light gray)
- `splitLineColor`: `#F0F2F5` (very light gray)
- `axisLabelColor`: `#999999`
- `upColor`: `#FF4D4F`
- `downColor`: `#52C41A`
- `accentColor`: `#FF4D4F`
- `seriesColors`: use new palette
- `tooltip.backgroundColor`: `#FFFFFF`
- `tooltip.borderColor`: `#E8EAED`
- `line.lineStyle.width`: `2.5` (thicker lines)
- `line.symbolSize`: `6`
- `bar.itemStyle.barBorderRadius`: `[4, 4, 0, 0]`

- [ ] **Step 2: Update getChartThemeDark() dark mode**

Same color updates adapted for dark palette.

- [ ] **Step 3: Update ATM.getChartTheme()**

Update the legacy ATM.getChartTheme function (lines 321-370) with matching new colors.

- [ ] **Step 4: Update line chart defaults**

In getChartTheme(), update line chart config:
- `line.lineStyle.width`: `2.5` (thicker lines for better visibility)
- `line.lineStyle.opacity`: `0.75` (transparency for overlapping lines)
- `line.symbolSize`: `6`
- `line.smooth`: `false`

- [ ] **Step 5: Update radar chart config for investment page**

In template JS for investment_recommendation.html, update radar chart:
- `radar.axisName.color`: `#666666`
- `radar.axisName.fontSize`: `12`
- `radar.axisName.position`: `'outside'` (labels outside the pentagon)
- Add `radar.axisLine` with `lineStyle.color: '#E8EAED'`
- Add `radar.splitLine` with `lineStyle.color: '#F0F2F5'`

- [ ] **Step 6: Update pie chart config for investment page**

In template JS, update pie chart:
- `series.label.show`: `true`
- `series.label.position`: `'outside'` (labels outside sectors)
- `series.label.formatter`: `'{b} {d}%'`
- `series.labelLine.show`: `true` (external leader lines)
- `series.labelLine.length`: `15`
- `series.labelLine.length2`: `10`
- Remove `series.label.position: 'inside'` if present

- [ ] **Step 7: Update scatter chart config for investment page**

In template JS, update scatter chart:
- `series.symbolSize`: function to scale by value
- `series.label.show`: `true`
- `series.label.position`: `'top'` (labels above bubbles)
- `series.label.distance`: `5`
- Ensure labels are close to bubbles (minimal distance)

- [ ] **Step 8: Add data labels at line endpoints**

For sector comparison charts, update line series:
- `series.endLabel.show`: `true` (show value at end of each line)
- `series.endLabel.formatter`: `'{a}'` or value
- `series.endLabel.color`: match line color
- `series.endLabel.fontSize`: `11`

- [ ] **Step 9: Update weight bar chart gradient colors**

For the home page recommendation weight bar chart, update the bar colors to use a hue gradient:
- Low weight → `#4F46E5` (indigo)
- High weight → `#FF4D4F` (red)
- Use ECharts `visualMap` or `itemStyle.color` with a linear gradient per bar
- Replace the current solid-color depth approach

---

## Task 6: Per-Template Inline Styles — investment_recommendation.html

**Covers:** Investment advice page redesign (Figure 5)

**Files:**
- Modify: `src/web/templates/investment_recommendation.html:16-153` (inline style block)

- [ ] **Step 1: Update inline styles**

Update the inline `<style>` block to use new design tokens:
- `.report-section`: replace `border: 1px solid var(--c-border)` with `box-shadow: var(--shadow-card)`
- `.report-header`: update gradient to new palette, add `border-radius: var(--radius-md)`
- `.badge-green/red/amber`: convert to capsule style with light backgrounds
- `.kpi-card`: remove hard borders, add soft shadow, add colored accent bar (green for positive, red for negative values)
- `.rec-table`: subtle row separators, no hard borders
- `.pos-bar-fill`: update colors to new palette
- `.conf-score` / `.conf-bar-fill`: update gradient colors
- `.vis-chart`: height: 320px (was 300px)

---

## Task 7: Per-Template Inline Styles — rotation.html

**Covers:** Rotation strategy page (Figure 7)

**Files:**
- Modify: `src/web/templates/rotation.html:14-94` (inline style block)

- [ ] **Step 1: Update rotation matrix styles**

- `.regime-matrix`: remove internal grid lines, keep external border
- `.regime-cell`: use soft background color blocks (light gray for low-low, light green for high-high)
- Current cell highlight: `background: #F6FFED` + `box-shadow: 0 0 0 2px #52C41A`
- `.report-section`: same card treatment as investment page
- `.kpi-card`: soft shadow, colored accent bars
- `.pos-bar`: update to new gradient colors

---

## Task 8: Per-Template Inline Styles — sector.html, tech_notes.html, etf.html

**Covers:** Sector page (Figure 3), Tech notes (Figure 6), ETF detail (Figure 2)

**Files:**
- Modify: `src/web/templates/sector.html:19-72`
- Modify: `src/web/templates/tech_notes.html:16-26`
- Modify: `src/web/templates/etf.html:19-25`

- [ ] **Step 1: Update sector.html inline styles**

- `.category-header`: remove hard borders, add soft hover
- `.category-count` pill: capsule style
- Grid responsive rules: keep but update border references

- [ ] **Step 2: Update tech_notes.html inline styles**

- `.tech-section`: replace hard borders with soft shadow
- `.tech-formula`: update background to `#F8F9FA`, add inner shadow, font-size: 18px, centered
- Paragraph spacing: `margin-bottom: 16px`

- [ ] **Step 3: Update etf.html inline styles**

- Responsive rules: keep but update border references to new palette
- Add chart spacing: ensure K-line, volume, fund flow charts have `gap: 32px` between them
- Add light gray divider lines (`border-top: 1px solid #F0F2F5`) between chart sections

- [ ] **Step 4: Add section headers between chart groups in sector.html**

For sector comparison page (Figure 3), add a prominent section header between "K-Line Trend" and "Share Value" chart sections:
```html
<div style="margin: 32px 0 16px; padding-bottom: 8px; border-bottom: 1px solid #F0F2F5;">
  <h3 style="font-size: 14px; font-weight: 600; color: #1A1A1A;">资金流向分析</h3>
</div>
```
This tells users these are two different analytical dimensions.

---

## Task 9: Sidebar Collapse Logic (JS + CSS)

**Covers:** Sidebar auto-collapse on detail pages

**Files:**
- Modify: `src/web/static/css/app.css:2482-2622` (sidebar styles)
- Modify: `src/web/static/js/app.js` (add collapse logic)

- [ ] **Step 1: Add sidebar collapse CSS**

Add to app.css:
```css
.sidebar-nav.collapsed {
  width: var(--sidebar-collapsed, 64px);
}
.sidebar-nav.collapsed .sidebar-nav-link span,
.sidebar-nav.collapsed .sidebar-logo-sub,
.sidebar-nav.collapsed .sidebar-nav-label {
  display: none;
}
.sidebar-nav.collapsed .sidebar-nav-link {
  justify-content: center;
}
```

- [ ] **Step 2: Add sidebar collapse JS**

Add to app.js after DOMContentLoaded:
```js
(function() {
  var detailPages = ['/etf', '/sector', '/analysis', '/investment-recommendation', '/rotation', '/tech-notes'];
  var sidebar = document.querySelector('.sidebar-nav');
  if (!sidebar) return;
  var path = location.pathname;
  var isDetail = detailPages.some(function(p) { return path.startsWith(p); });
  if (isDetail) {
    sidebar.classList.add('collapsed');
  }
})();
```

---

## Task 10: KPI Card Accent Bars (JS)

**Covers:** Analysis page (Figure 4) — IC MEAN cards with positive/negative color bars

**Files:**
- Modify: `src/web/static/js/app.js` (analysis page rendering functions)

- [ ] **Step 1: Add accent bar rendering**

In the IC summary rendering function (renderIcSummary or equivalent), after computing `meanColor`:
- If value > 0: add `border-left: 3px solid #52C41A` to KPI card
- If value < 0: add `border-left: 3px solid #FF4D4F`
- If value == 0: neutral border

This applies to the analysis page KPI cards.

---

## Task 11: Final Verification

**Covers:** All sections — full integration check

- [ ] **Step 1: Run dev server and verify all pages**

Start server and visually verify:
- `/` — Index page: white cards, soft shadows, new colors
- `/etf` — ETF detail: chart spacing, new chart colors
- `/sector` — Sector comparison: line chart opacity 0.75, stroke-width 2.5
- `/analysis` — Analysis: KPI accent bars, IC summary
- `/rotation` — Rotation: regime matrix without internal lines, highlighted recommendation
- `/investment-recommendation` — Investment: radar/pie chart fixes, confidence bar
- `/tech-notes` — Tech notes: formula block styling

- [ ] **Step 2: Verify responsive behavior**

Check at 1440px, 1024px, 768px, 480px, 375px breakpoints.

- [ ] **Step 3: Verify dark mode**

Toggle dark mode and verify all color tokens adapt correctly.

- [ ] **Step 4: Commit all changes**

```bash
git add -A
git commit -m "feat: modern minimalist UI redesign — new color palette, sans-serif fonts, soft shadows, collapsible sidebar"
```

---

## Commit Strategy

1. `feat: redesign CSS tokens — new color palette, fonts, shadows` (Tasks 1-4)
2. `feat: update ECharts chart theme for new design system` (Task 5)
3. `feat: update investment recommendation page inline styles` (Task 6)
4. `feat: update rotation matrix and report page styles` (Task 7)
5. `feat: update sector, tech notes, etf template styles` (Task 8)
6. `feat: add sidebar collapse logic for detail pages` (Task 9)
7. `feat: add KPI accent bars for positive/negative values` (Task 10)
