# Claude-Inspired Warm Sage UI Redesign

**Date**: 2026-05-10
**Scope**: CSS-only restyle of ATMstockMarket web UI
**Files affected**: `src/web/static/css/app.css`, `src/web/static/js/app.js` (chart theme only)

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Color palette | Warm Sage | Distinctive identity, warm feel matching Claude's approach |
| Border radius | Pill Soft (12-16px, 9999px for pills) | Most Claude-like, soft and approachable |
| Table style | Soft Rows (no cell borders) | Clean, modern, matches pill-soft direction |

## Color System

### Light Mode

```
Backgrounds:
  --c-bg:            #F7F6F3    (page background, warm off-white)
  --c-bg-secondary:  #FFFFFF    (cards, nav)
  --c-bg-tertiary:   #EDEBE6    (subtle fills, hover states)

Text:
  --c-text:            #1A1C19  (primary text)
  --c-text-secondary:  #5C5A55  (secondary text)
  --c-text-tertiary:   #94928A  (muted/hint text)
  --c-text-muted:      #B5B3AC  (disabled/placeholder)

Borders:
  --c-border:          #CCC9BF  (default borders)
  --c-border-light:    #E2E0D8  (light/soft borders)
  --c-border-strong:   #9E9B92  (emphasis borders)

Links:
  --c-link:            #4A7050  (normal)
  --c-link-hover:      #3A5D40  (hover)
  --c-link-visited:    #3A5D40  (visited)

Accent (Sage Green):
  --c-accent:          #6B8F71
  --c-accent-light:    #7BA882
  --c-accent-dark:     #4A7050
  --c-accent-bg:       rgba(107, 143, 113, 0.1)

Market (unchanged):
  --c-up:              #dd3333  (red, up)
  --c-down:            #00af00  (green, down)
  (all up/down-bg variants updated to match new base palette)

Surfaces:
  --c-card:            #FFFFFF
  --c-card-hover:      #F5F3EE

Tables:
  --c-table-header:    #F0EDE7  (warm beige header)
  --c-table-stripe:    transparent (no striping)
  --c-table-hover:     #F5F3EE

Input:
  --c-input-bg:        #FFFFFF
  --c-input-border:    #E2E0D8
  --c-input-focus:     #6B8F71
  --c-input-focus-ring: rgba(107, 143, 113, 0.2)

Scrollbar:
  --c-scrollbar-track: #EDEBE6
  --c-scrollbar-thumb: #CCC9BF
  --c-scrollbar-thumb-hover: #9E9B92

Skeleton:
  --c-skeleton:        #EDEBE6
  --c-skeleton-shine:  #F7F6F3
```

### Dark Mode

```
Backgrounds:
  --c-bg:            #141613
  --c-bg-secondary:  #1C1F1A
  --c-bg-tertiary:   #252823

Text:
  --c-text:            #E8E6E1
  --c-text-secondary:  #B5B3AC
  --c-text-tertiary:   #8A8880

Surfaces:
  --c-card:            #1C1F1A
  --c-card-hover:      #252823

Borders:
  --c-border:          #3A3D35
  --c-border-light:    #333630

Links:
  --c-link:            #7BA882
  --c-link-hover:      #8FBF97

Accent:
  --c-accent-bg:       rgba(123, 168, 130, 0.12)

Tables:
  --c-table-header:    #252823
  --c-table-stripe:    transparent
  --c-table-hover:     #2A2D26

Input:
  --c-input-bg:        #1C1F1A
  --c-input-border:    #3A3D35

Scrollbar:
  --c-scrollbar-track: #1C1F1A
  --c-scrollbar-thumb: #3A3D35
```

## Border Radius

| Element | Current | New |
|---------|---------|-----|
| Cards / `.glass` | `12px` | `16px` |
| Primary buttons | `8px` | `9999px` (pill) |
| Secondary buttons | `8px` | `12px` |
| Tab buttons | `8px` | `9999px` (pill) |
| Input fields | `6px` | `12px` |
| Logo icon | `6px` | `10px` |
| Heat cells | `8px` | `14px` |
| Sector cards | `12px` | `14px` |
| Nav links (active) | `6px` | `9999px` (pill) |
| Mobile nav links | `8px` | `12px` |
| Status/badges | `0` (square) | `9999px` (pill) |
| Rank badges | `0` (square) | `8px` |
| Tags | `0` (square) | `9999px` (pill) |
| Progress bar track | `9999px` | `9999px` (unchanged) |
| Pagination items | `0` (square) | `10px` |
| Toast/messages | `0` (square) | `12px` |

## Table Styling (Soft Rows)

- Remove all cell borders (`border: none` on `th`, `td`)
- Header: bold uppercase labels (10-11px), bottom 2px border in `--c-border-light`, warm muted color
- Row separators: thin line in `#F0EDE7` (light mode) / `#2A2D26` (dark mode)
- No zebra striping
- Status badges: pill-shaped with transparent colored backgrounds
- Hover: subtle warm highlight (`--c-table-hover`)
- Outer table border: remove the `border: 1px solid var(--c-border)` on `.zebra-table` (the enclosing `.glass` card provides the visual boundary)

## Cards & Surfaces

- Remove visible borders; use soft shadows for elevation
- Default shadow: `0 1px 3px rgba(26, 28, 25, 0.06)`
- Hover shadow: `0 4px 12px rgba(26, 28, 25, 0.08)`
- Hover adds `translateY(-1px)` lift
- Card hover background: `#F5F3EE` (warm off-white)
- Border on hover only: `1px solid var(--c-border-light)`

## Navigation

- Active nav link: pill-shaped `background: var(--c-accent-bg)`, `color: var(--c-accent)`, `border-radius: 9999px`
- Inactive nav link: transparent, `color: var(--c-text-secondary)`
- Nav link hover: `background: var(--c-bg-tertiary)`, no underline
- Mobile nav links: rounded cards (`border-radius: 12px`)
- Bottom nav active: sage color text, no background
- Nav shadow: very subtle (`0 1px 2px rgba(26, 28, 25, 0.04)`)

## Typography

- Keep existing system font stack
- Section title accent bar: `background: var(--c-accent)` (sage green instead of blue)
- Chart title text color: `#1A1C19` (warm dark)

## Buttons

- Primary: `background: var(--c-accent)` (sage), white text, pill shape, `box-shadow: 0 1px 2px rgba(107, 143, 113, 0.15)`
- Primary hover: `background: var(--c-accent-dark)`, stronger shadow, `translateY(-1px)`
- Secondary: `background: var(--c-card)`, `border: 1px solid var(--c-border-light)`, rounded
- Secondary hover: `background: var(--c-bg-tertiary)`, soft shadow
- All buttons: `min-height: 40px` on desktop, `44px` on mobile

## ECharts Theme Updates

Update `ATM.getChartTheme()` in `app.js`:

- Tooltip background: `#2A2D28` (warm dark)
- Tooltip border: `#3A3D35`
- Tooltip text: `#E8E6E1`
- Axis label: `#5C5A55`
- Split line: `#E2E0D8`
- Legend text: `#5C5A55`
- Keep red/green for candlestick and market data
- Accent chart color: `#6B8F71` (sage) for non-market data series
- Compare chart bar colors: sage palette (`#6B8F71`, `#8FBF97`, `#4A7050`)

## Out of Scope

- No HTML template changes
- No JavaScript logic changes (except chart theme colors)
- No API/backend changes
- No new features
- Market colors (red up / green down) remain unchanged
- Responsive breakpoints unchanged
- Dark mode toggle mechanism unchanged
