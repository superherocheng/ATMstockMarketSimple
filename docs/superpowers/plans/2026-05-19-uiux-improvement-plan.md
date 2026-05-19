# UI/UX 改进计划

基于 `tweaks.html` 参考 + 当前项目审计，制定以下分块改进计划。

---

## 当前状态审计

### 已做好的
- ✅ 设计 Tokens 体系（CSS 变量：颜色、间距、字体）
- ✅ 暗色模式（`data-theme` 切换）
- ✅ 响应式布局（grid/flex 断点）
- ✅ ECharts 5 可视化（bundled，无需 CDN）
- ✅ Glass morphism 卡片效果（`.glass` class）
- ✅ 骨架屏加载态
- ✅ 底部导航（移动端）

### 需要改进的

| # | 模块 | 问题 | 优先级 |
|---|------|------|--------|
| UX01 | **排版系统** | 全站统 -apple-system，缺乏层级对比。数据仪表盘应搭配衬线体显示数字 | P1 |
| UX02 | **导航栏** | 顶端导航仅文字链接，缺少品牌感；无暗色模式切换开关；移动端汉堡菜单样式简陋 | P1 |
| UX03 | **KPI 指标卡** | 首页/投资建议页的指标卡无图标、无微动效、hover 无反馈 | P1 |
| UX04 | **行业卡片** | 四列网格在移动端过挤，卡片无阴影/投影层级 | P1 |
| UX05 | **数据表格** | 份额排名表/ETF 推荐表为原生 HTML 表格，缺少斑马纹/行悬停强调 | P2 |
| UX06 | **Loading 态** | 骨架屏（skeleton）无动画，出现突兀 | P2 |
| UX07 | **图表区** | 图表容器在 loading 时无占位轮廓，加载完成后会跳动 | P2 |
| UX08 | **一致性** | 大量 inline style 散落在 `.html` 中，与 CSS 变量未统一 | P2 |
| UX09 | **暗色模式** | 已支持但无切换开关在 UI 上，用户需通过 JS 切换 | P2 |
| UX10 | **动效系统** | `tweaks.html` 的 motion-mult + prefers-reduced-motion 未使用 | P3 |
| UX11 | **财务因子面板** | 新加的财务质量四指标卡片无图表化呈现（当前仅为文字数字） | P3 |
| UX12 | **投资建议页** | 推荐理由列表过长，可以用折叠/标签分组 | P3 |

---

## 分块实施计划

### Block 1 — 排版系统 + 导航栏重构（P1）
- 引入 Source Serif 4 用于数据数字/KPI 数值、Inter 用于正文（参考 tweaks.html）
- 优化顶部 nav：品牌 logo + 导航链接 + 暗色模式切换开关
- 移除被注释掉的冗余导航项
- 统一 heading 层级（h1/h2/h3 样式）

### Block 2 — KPI 卡片 + 行业卡片 UI 升级（P1）
- 为指标卡添加：渐变背景、icon、hover lift 效果
- 行业卡片：阴影深度、hover 时 translateY(-2px)、选中态指示器
- 卡片响应式断点优化（5列→3列→2列→1列）

### Block 3 — 数据表格 + Loading 态（P2）
- 表格：斑马纹、行 hover 高亮、数字右对齐 + 等宽字体
- 骨架屏：CSS animation pulse + shimmer 效果
- 图表容器：固定高宽比占位，消除加载后跳动

### Block 4 — 财务因子可视化 + 一致性清理（P2-P3）
- 财务四指标卡改为迷你仪表盘（圆环或进度条）
- 统一所有 inline style 到 CSS 变量
- 暗色模式切换按钮接入 nav

### Block 5 — 动效系统 + 投资建议页优化（P3）
- 引入 motion-mult CSS 变量 + prefers-reduced-motion
- 投资建议理由折叠/分页
- 为因子排名表添加微柱状图（sparkline）

---

## 开始顺序

```
Block 1 (排版+导航) → Block 2 (卡片) → Block 3 (表格+loading) 
→ Block 4 (财务因子+一致性) → Block 5 (动效+建议页)
```

每个 Block 独立交付，完成后即可上线预览。
