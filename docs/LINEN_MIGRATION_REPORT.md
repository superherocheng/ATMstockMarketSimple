# Linen Design System Migration Report

**Date:** 2026-06-13
**From:** Brutalist Swiss ("Graphite on Chalk")
**To:** Linen ("Hairline editorial — warm cream, ink type, hairline rules")

## Overview

The Linen design system replaces the previous Brutalist Swiss aesthetic with a quiet, paper-like editorial style. The palette shifts from achromatic black/white to a warm cream linen surface (#f1ede3) with near-black ink (#111111) type. All rounded corners are eliminated (strictly orthogonal forms). Shadows and gradients were already `none` in the previous system and remain absent. Typography moves from Geist to Archivo Narrow (display) + Inter (body) + JetBrains Mono (code).

## Design Token Comparison

| Token | Before (Brutalist) | After (Linen) |
|-------|-------------------|--------------|
| Background | #ffffff / #171717 | #f1ede3 / #1a1814 |
| Text | #0a0a0a / #e5e5e5 | #111111 / #e6dfd3 |
| Secondary text | #0a0a0a / #e5e5e5 | #3a3733 / #a09888 |
| Muted text | #737373 / #737373 | #8a857c / #706658 |
| Borders | #e5e5e5 / #333333 | #1f1d1a / #3a3530 |
| Accent/highlight | #0a0a0a | #c8462c (Signal red) |
| Display font | Geist | Archivo Narrow (700) |
| Body font | Geist | Inter |
| Mono font | Geist Mono | JetBrains Mono |
| Border radius | 4-14px | 0px (all) |
| Shadows | none | none |

## Files Modified

### CSS
| File | Change |
|------|--------|
| `src/web/static/css/app.css` | Full rewrite (~2400 lines). Replaced all color tokens with Linen palette, changed font stack, zeroed all border-radius, added Linen component classes (`.t-display-*`, `.t-label`, `.t-mono`, `.stat`, `.card--paper`, `.pill`, `.tabs`, `.field`, `.check`, etc.), adapted dark mode to Linen Night palette. All backward-compatible CSS custom property names preserved. |

### JavaScript
| File | Change |
|------|--------|
| `src/web/static/js/app.js` | Updated `ATM.getChartTheme()` and `ATMChart.getChartTheme()` / `getChartThemeDark()` with Linen colors and font families. Chart tooltips use cream paper backgrounds, hairline borders. Series colors changed to Linen monochrome + signal palette. |

### Templates
| File | Change |
|------|--------|
| `src/web/templates/index.html` | Font import URL: Geist → Archivo Narrow + Inter + JetBrains Mono. Theme-color meta updated to Linen surface. |
| `src/web/templates/analysis.html` | Font import URL updated. |
| `src/web/templates/etf.html` | Font import URL updated. |
| `src/web/templates/sector.html` | Font import URL updated. |
| `src/web/templates/investment_recommendation.html` | Font import URL updated. |
| `src/web/templates/tech_notes.html` | Font import URL updated. |

## Component Transformation

### Navigation → Linen top bar
Signal underline indicator for active state, uppercase tracked labels, hover color change.

### Buttons → Linen hairline
Zero radius, hairline border, hover swaps fill/label colors. `.btn--primary` (solid ink), `.btn--ghost` (transparent).

### Cards → Hairline-framed
Transparent on cream, 1px hairline border, hover fills with Paper (#f7f4ec). New: `.card--paper` for inset panels.

### Tables → Linen data grids
Hairline container, uppercase Stone-colored tracked headers, subtle stripe.

### KPI Cards → Hairline bottom border
Signal 2px underline on hover, Archivo Narrow numerals, Stone uppercase labels.

### Stat Blocks (new)
56px Archivo Narrow value, JetBrains Mono uppercase caption, hairline bottom rule.

### Empty State → Linen
Hairline border, Archivo Narrow title (--headline-md), centered body copy.

### Chart Cells → Hairline-framed
Removed rounded corners, cream/paper backgrounds, hairline borders.

## Dark Mode: Linen Night

| Token | Light | Dark |
|-------|-------|------|
| Surface | #f1ede3 | #1a1814 |
| Ink | #111111 | #e6dfd3 |
| Graphite | #3a3733 | #a09888 |
| Stone | #8a857c | #706658 |
| Hairline | #1f1d1a | #3a3530 |
| Signal | #c8462c | #d66947 |
| On-ink | #f1ede3 | #1a1814 |

## New Linen Components Added

- `.t-display-xl`, `.t-display-lg`, `.t-headline-lg/md/sm` — typographic scale
- `.t-body`, `.t-body-sm` — body copy utilities
- `.t-label` — uppercase 11px tracked labels
- `.t-mono` — JetBrains Mono metadata
- `.l-page`, `.l-grid`, `.l-rule`, `.l-stack`, `.l-row` — layout primitives
- `.card--paper`, `.card--tight`, `.card__*` — card sub-components
- `.btn--primary`, `.btn--ghost`, `.btn--small`, `.btn__arrow` — button variants
- `.pill`, `.pill__arrow` — pill tags
- `.tabs`, `.tabs__item` — tab navigation
- `.field`, `.field__*` — form inputs
- `.check`, `.check__*` — checkboxes
- `.stat`, `.stat__value`, `.stat__caption`, `.stat-grid` — stat blocks
- `.section`, `.section__head`, `.eyebrow` — section helpers
- `.dot` — signal indicator

## Test Results

```
96 passed, 1 skipped in 2.10s
```

All existing unit tests pass — the CSS/JS migration is functionally safe.
