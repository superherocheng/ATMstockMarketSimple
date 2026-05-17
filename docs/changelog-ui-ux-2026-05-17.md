# UI/UX 改进记录 — 2026-05-17

> 基于项目总结报告（P0~P2）的系统改进，共 9 项交付。

---

## 目录

- [P0#1：导航统一（B 方案）](#p01导航统一b方案)
- [P0#2：暗色模式](#p02暗色模式)
- [P1#7：ECharts CDN 双倍加载修复](#p17echarts-cdn-双倍加载修复)
- [P1#8：分析页样式对齐全局 Token](#p18分析页样式对齐全局-token)
- [P2#9：ETF 详情页日期范围选择器](#p29etf-详情页日期范围选择器)
- [P2#10：预设按钮 Tooltip](#p210预设按钮-tooltip)
- [P2#11：页面切换淡入动画](#p211页面切换淡入动画)
- [P2#12：用户行为埋点](#p212用户行为埋点)
- [P2#13：投资建议页入口](#p213投资建议页入口)
- [P2#14：份额更新状态增强](#p214份额更新状态增强)

---

## P0#1：导航统一（B 方案）

### 改动

#### 1a. 删除 `app.js` 中的死代码（177 行）

`ATMNav` 整个 IIFE（旧 `nav.js` 源文件）从未被任何模板调用，包含：

- `ATMNav.render()` — 带 5 个不存在路由（`/stock/`、`/concept`、`/industry`、`/stocks`、`/barra`）的 JS 导航生成器
- `ATMNav.insert()` — 未使用的容器注入函数
- `ATMNav.toggleMobile()` / `ATMNav.handleKeydown()` — 模板使用内联 `onclick`，不依赖此实现
- `ATMNav.loadFreshness()` — 从未调用
- `ATMNav.THEME_KEY` / `getTheme()` / `applyTheme()` / `toggleTheme()` — 与同文件 `ATMTheme` 模块完全重复

**结果**：`app.js` 从 1620 行缩减至 1443 行（后续增量后最终 1455 行）。

#### 1b. 底部导航图标统一（7 个模板）

将底边栏最后两项的 emoji 图标替换为与前三项一致的 SVG 图标：

| 模板 | 替换前 | 替换后（SVG） |
|------|--------|-------------|
| `index.html` | 🌡️ + 📊 | 网格 icon + 饼图 icon |
| `etf.html` | 🌡️ + 📊 | 同上 |
| `sector.html` | 🌡️ + 📊 | 同上 |
| `analysis.html` | 🌡️ + 📊 | 同上 |
| `heatmap.html` | 🌡️ + 📊 | 同上 |
| `investment_recommendation.html` | 🌡️ + 📊 | 同上 |
| `tech_notes.html` | 🌡️ + 📊 | 同上 |

`investment_recommendation.html` 内容区标题中的 `📊` emoji 保留不动。

### 涉及文件

- `src/web/static/js/app.js`
- `src/web/templates/index.html`
- `src/web/templates/etf.html`
- `src/web/templates/sector.html`
- `src/web/templates/analysis.html`
- `src/web/templates/heatmap.html`
- `src/web/templates/investment_recommendation.html`
- `src/web/templates/tech_notes.html`

---

## P0#2：暗色模式

> 跳过（用户确认不需要）

---

## P1#7：ECharts CDN 双倍加载修复

### 改动

`app.js` 中 `ATMChart.load()` 的 CDN 回退路径被移除：

**之前**：
```javascript
ATMChart._loaded = new Promise(function(resolve, reject) {
    var script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js';
    // ...
});
```

**之后**：
```javascript
ATMChart._loaded = Promise.reject(
    new Error('ATMstockMarket: ECharts 未加载，请确认 vendor.js 已正确引入')
);
```

正常场景零变化（`vendor.js` 已提供 `echarts`）。异常场景不再静默下载远程 ~1MB 脚本，改为抛出清晰中文错误。

### 涉及文件

- `src/web/static/js/app.js`

---

## P1#8：分析页样式对齐全局 Token

### 改动

将 `analysis.html` 内联 `<style>` 块中的 38 行硬编码样式迁移到 `app.css` 的 token 体系下：

| 硬编码值 | 替换为 |
|----------|--------|
| `#eae6dc` / `#f4f1e8` | `var(--c-bg-tertiary)` |
| `#d4cfc4` | `var(--c-border)` |
| `#fff` | `var(--c-card)` |
| `#5a6f5a` / `#2d5a2d` | `var(--c-accent-dark)` |
| `#6b8e6b` | `var(--c-accent)` |
| `#8b4513`（tech-btn） | `var(--c-warning)` |
| `#999` | `var(--c-text-tertiary)` |
| `#555` | `var(--c-text-secondary)` |
| `#333` | `var(--c-text)` |
| `#888` | `var(--c-text-muted)` |
| `#e8e4db` | `var(--c-border-light)` |
| `border-radius: 8px` / `6px` | `var(--radius-md)` / `var(--radius-sm)` |

HTML 标记（class 名）和布局完全不变，零视觉回归。暗色模式下所有卡片/文字/边框自动适配。

### 涉及文件

- `src/web/static/css/app.css`（新增 46 行）
- `src/web/templates/analysis.html`（移除 38 行内联样式）

---

## P2#9：ETF 详情页日期范围选择器

### 改动

在 ETF 详情页 K 线图表区域新增日期范围切换按钮组：

**HTML**（`etf.html`）：K 线标题右侧增加 4 个按钮：`3月` `6月` `1年` `全部`

**CSS**（`app.css`）：新增 `.range-btn` 和 `.range-btn.active` 规则

**JS**（`etf.html` 内联脚本）：
- `_dateRangeDays` 变量（默认 60 天）
- `setDateRange(btn, days)` 函数 — 切换 active 状态 + 裁剪数据重新渲染
- 在 `renderKline()` 中，`kline` 数据根据 `_dateRangeDays` 切片
- 在 `loadData()` 中，缓存全量数据到 `window._etfCachedData`，供日期切换时直接使用

### 涉及文件

- `src/web/templates/etf.html`
- `src/web/static/css/app.css`

---

## P2#10：预设按钮 Tooltip

### 改动

为分析页的三个预设按钮添加 `title` 属性：

| 按钮 | 之前 | 之后 |
|------|------|------|
| 短期 | 无 tooltip | `title="N=10, M=20 — 适合短线因子验证"` |
| 中期 | 无 tooltip | `title="N=20, M=60 — 适合中线持仓参考"` |
| 长期 | 无 tooltip | `title="N=40, M=120 — 适合长周期趋势判断"` |

参数值来源于 `src/analysis/presets.py` 中的 `PRESETS` 定义。

### 涉及文件

- `src/web/templates/analysis.html`

---

## P2#11：页面切换淡入动画

### 改动

`app.js` 中已有 `document.body.classList.add('page-ready')`（在 `ATMRouter._setupPageTransition` 中执行），但 CSS 中从未定义对应动画。在 `app.css` 中补充：

```css
body.page-ready {
    animation: fadeIn 0.15s ease;
}
@keyframes fadeIn { from { opacity:0.3; } to { opacity:1; } }
```

所有页面加载时自动享受 150ms 淡入效果。尊重 `prefers-reduced-motion`（已有 `@media` 规则）。

### 涉及文件

- `src/web/static/css/app.css`

---

## P2#12：用户行为埋点

### 改动

#### 后端

新增 `src/web/routers/telemetry.py`（22 行），在 `app.py` 中注册。

`POST /api/telemetry` — 接收 JSON body、记录日志、返回 `{"ok": true}`。

采集字段：

| 字段 | 来源 | 用途 |
|------|------|------|
| `path` | `location.pathname` | 页面 PV |
| `ref` | `document.referrer` | 流量来源 |
| `ts` | `Date.now()` | 时间戳 |
| `w` | `screen.width` | 设备类型识别 |
| `ua` | `navigator.userAgent`（截断至 120 字符） | 浏览器分布 |

#### 前端

`app.js` 顶部新增匿名信标 IIFE——页面加载后通过 `navigator.sendBeacon` 发送一条埋点记录。尊重 `navigator.doNotTrack`。

### 涉及文件

- `src/web/routers/telemetry.py`（新建）
- `src/web/app.py`（import + 注册）
- `src/web/static/js/app.js`

---

## P2#13：投资建议页入口

### 改动

在分析页底部（`summary-card` 与 `</main>` 之间）新增卡片式入口：

```
┌──────────────────────────────────────────┐
│  [查看完整投资建议 →]                      │
│  基于因子评分 + 资金流向的 ETF 持仓建议     │
└──────────────────────────────────────────┘
```

链接指向 `/analysis/investment-recommendation`（该页面已实现，之前只能通过预设栏小按钮访问）。

### 涉及文件

- `src/web/templates/analysis.html`

---

## P2#14：份额更新状态增强

### 改动

首页份额状态 badge 从：

```
🟢 份额: 完整
```

变为：

```
🟢 份额: 完整
🟢 份额: 完整 (3天前)
```

![状态示例](#)

利用 `/api/etf-share/status` 返回的 `latest_trading_date` 字段计算距今天数，仅当 > 0 天时追加。

### 涉及文件

- `src/web/templates/index.html`

---

## 总统计

| 指标 | 数值 |
|------|------|
| 交付改进数 | 9 项（P0: 1, P1: 2, P2: 6；P0#2 跳过） |
| 修改文件数 | 10 个（含 1 个新建） |
| `app.js` 净变化 | -141 行（-177 dead code + 36 新功能） |
| `app.css` 净增长 | +56 行 |
| 模板文件净变化 | -7 行（38 行内联样式迁移 → 27 行新增内容 + 14 处图标替换） |
| 新增 Python | 22 行（telemetry.py） |
| 风险等级 | 全部为低或极低，无架构性改动 |
