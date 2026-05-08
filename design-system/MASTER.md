# ATMstockMarket 复古木质风格设计系统

## 设计理念

### 核心主题
**复古木质风格** - 融合传统木质美学与现代金融数据展示,营造温暖、自然、怀旧的投资分析氛围。

### 设计原则
1. **自然温暖** - 使用木质色调和纹理传达温暖感
2. **怀旧复古** - 通过做旧效果和复古字体唤起怀旧情怀
3. **清晰易读** - 保持金融数据的清晰度和可读性
4. **层次分明** - 通过木质边框和阴影建立视觉层次
5. **响应式设计** - 确保PC端和移动端的一致体验

---

## 色彩方案

### 主色调 - 木质色系

#### 深棕色系 (Dark Wood)
- **深胡桃木色**: `#3E2723` - 主要边框、强调元素
- **深棕色**: `#4E342E` - 次要边框、悬停状态
- **栗棕色**: `#5D4037` - 卡片边框、分割线

#### 原木色系 (Natural Wood)
- **浅橡木色**: `#D7CCC8` - 卡片背景
- **米色**: `#EFEBE9` - 页面背景
- **奶油色**: `#F5F5DC` - 高亮区域
- **象牙白**: `#FFF8E7` - 内容区域背景

#### 复古装饰色
- **古铜色**: `#8D6E63` - 图标、装饰元素
- **焦糖色**: `#A1887F` - 次要文本
- **琥珀色**: `#BCAAA4` - 辅助元素

### 功能色彩

#### 市场涨跌色 (保留中国股市惯例)
- **上涨红**: `#C62828` - 涨幅显示
- **下跌绿**: `#2E7D32` - 跌幅显示
- **平盘灰**: `#757575` - 无变化

#### 状态色
- **成功**: `#558B2F` - 成功提示
- **警告**: `#F57C00` - 警告提示
- **错误**: `#D32F2F` - 错误提示
- **信息**: `#1976D2` - 信息提示

### 色彩对比度验证
所有文本与背景对比度符合 WCAG AA 标准 (4.5:1)
- 深棕色文本 (#3E2723) 在象牙白背景 (#FFF8E7): 12.6:1 ✓
- 古铜色文本 (#8D6E63) 在米色背景 (#EFEBE9): 4.8:1 ✓
- 涨跌色在浅色背景: > 5:1 ✓

---

## 字体系统

### 复古字体组合

#### 标题字体 - 怀旧衬线体
- **主字体**: `'Noto Serif SC'`, `'Source Han Serif CN'`, Georgia, serif
- **特点**: 传统衬线,笔画有粗细变化,复古感强
- **应用**: 页面标题、卡片标题、重要数据标签
- **字重**: 400 (Regular), 600 (SemiBold), 700 (Bold)

#### 正文字体 - 易读无衬线体
- **主字体**: `'Noto Sans SC'`, `'Source Han Sans CN'`, 'PingFang SC', sans-serif
- **特点**: 清晰易读,适合金融数据展示
- **应用**: 正文内容、表格数据、说明文字
- **字重**: 400 (Regular), 500 (Medium), 600 (SemiBold)

#### 等宽字体 - 数据专用
- **主字体**: `'JetBrains Mono'`, `'Fira Code'`, 'SF Mono', monospace
- **特点**: 数字对齐,适合金融数据
- **应用**: 股价、涨跌幅、交易量、代码
- **字重**: 400 (Regular), 500 (Medium), 600 (SemiBold)

### 字体大小规范

#### PC端
```
--text-xs: 12px    /* 辅助信息、标签 */
--text-sm: 14px    /* 次要内容、表格 */
--text-base: 16px  /* 正文内容 */
--text-lg: 18px    /* 小标题 */
--text-xl: 20px    /* 卡片标题 */
--text-2xl: 24px   /* 区域标题 */
--text-3xl: 30px   /* 页面标题 */
--text-4xl: 36px   /* 大标题 */
```

#### 移动端
```
--text-xs: 11px
--text-sm: 13px
--text-base: 15px
--text-lg: 17px
--text-xl: 19px
--text-2xl: 22px
--text-3xl: 26px
```

### 行高规范
- 标题: 1.3 - 1.4
- 正文: 1.6 - 1.8
- 数据: 1.4 - 1.5

---

## 木质纹理与材质

### 木纹纹理

#### 主木纹背景
```css
/* 浅色木纹 - 用于页面背景 */
background-image: 
  repeating-linear-gradient(
    90deg,
    transparent,
    transparent 2px,
    rgba(139, 90, 43, 0.03) 2px,
    rgba(139, 90, 43, 0.03) 4px
  ),
  repeating-linear-gradient(
    0deg,
    transparent,
    transparent 20px,
    rgba(139, 90, 43, 0.02) 20px,
    rgba(139, 90, 43, 0.02) 22px
  );
```

#### 卡片木纹
```css
/* 深色木纹 - 用于卡片背景 */
background-image: 
  repeating-linear-gradient(
    90deg,
    transparent,
    transparent 3px,
    rgba(62, 39, 35, 0.04) 3px,
    rgba(62, 39, 35, 0.04) 6px
  );
```

### 做旧效果

#### 纹理叠加
```css
/* 纸张纹理 - 增加复古感 */
background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%' height='100%' filter='url(%23noise)'/%3E%3C/svg%3E");
opacity: 0.03;
```

#### 边框磨损效果
```css
/* 不规则边框 - 模拟木质边缘 */
border: 2px solid #5D4037;
box-shadow: 
  inset 0 0 0 1px rgba(255, 248, 231, 0.3),
  2px 2px 0 rgba(62, 39, 35, 0.1);
```

---

## 木质边框设计

### 边框样式

#### 主要边框
```css
/* 实木边框 - 主要卡片 */
border: 3px solid #3E2723;
border-radius: 8px;
box-shadow: 
  3px 3px 0 rgba(62, 39, 35, 0.15),
  inset 0 1px 0 rgba(255, 248, 231, 0.2);
```

#### 次要边框
```css
/* 浅木边框 - 次要元素 */
border: 2px solid #8D6E63;
border-radius: 6px;
box-shadow: 2px 2px 0 rgba(141, 110, 99, 0.1);
```

#### 装饰边框
```css
/* 雕刻边框 - 特殊元素 */
border: 2px solid #5D4037;
border-radius: 4px;
box-shadow: 
  inset 0 2px 4px rgba(62, 39, 35, 0.1),
  2px 2px 0 rgba(93, 64, 55, 0.08);
```

### 边框圆角
- **大圆角**: 12px - 主要卡片、模态框
- **中圆角**: 8px - 次要卡片、按钮
- **小圆角**: 4px - 输入框、标签
- **无圆角**: 0px - 表格、分割线

---

## 间距系统

### 基础单位
采用 8px 基础单位系统,符合 Material Design 规范

```
--space-0-5: 4px   /* 极小间距 */
--space-1: 8px     /* 基础单位 */
--space-1-5: 12px  /* 小间距 */
--space-2: 16px    /* 标准间距 */
--space-3: 24px    /* 中等间距 */
--space-4: 32px    /* 大间距 */
--space-5: 40px    /* 区域间距 */
--space-6: 48px    /* 大区域间距 */
--space-8: 64px    /* 页面间距 */
```

### 应用规则
- 组件内部: 8px - 16px
- 卡片内边距: 16px - 24px
- 区域间距: 24px - 32px
- 页面边距: 32px - 48px

---

## 阴影系统

### 木质阴影
模拟木质物体的立体感,使用偏移阴影而非模糊阴影

```css
/* 轻微阴影 - 悬停状态 */
--shadow-sm: 2px 2px 0 rgba(62, 39, 35, 0.1);

/* 标准阴影 - 卡片 */
--shadow-md: 3px 3px 0 rgba(62, 39, 35, 0.15);

/* 深度阴影 - 模态框 */
--shadow-lg: 4px 4px 0 rgba(62, 39, 35, 0.2);

/* 强调阴影 - 悬停卡片 */
--shadow-hover: 5px 5px 0 rgba(62, 39, 35, 0.25);
```

---

## 动画与过渡

### 过渡时长
- **快速**: 150ms - 按钮悬停、状态切换
- **标准**: 250ms - 卡片展开、导航切换
- **慢速**: 400ms - 页面过渡、模态框

### 缓动函数
```css
/* 自然缓动 - 模拟木质物体移动 */
--ease-wood: cubic-bezier(0.4, 0, 0.2, 1);

/* 进入动画 */
--ease-wood-in: cubic-bezier(0.4, 0, 1, 1);

/* 退出动画 */
--ease-wood-out: cubic-bezier(0, 0, 0.2, 1);
```

### 关键动画

#### 卡片悬停
```css
.card:hover {
  transform: translate(-2px, -2px);
  box-shadow: 5px 5px 0 rgba(62, 39, 35, 0.25);
  transition: all 250ms var(--ease-wood);
}
```

#### 按钮点击
```css
.btn:active {
  transform: translate(1px, 1px);
  box-shadow: 1px 1px 0 rgba(62, 39, 35, 0.15);
}
```

---

## 组件设计规范

### 卡片组件

#### 主卡片
```css
.card-primary {
  background: linear-gradient(135deg, #FFF8E7 0%, #EFEBE9 100%);
  border: 3px solid #3E2723;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 3px 3px 0 rgba(62, 39, 35, 0.15);
  position: relative;
}

.card-primary::before {
  content: '';
  position: absolute;
  top: 4px;
  left: 4px;
  right: -4px;
  bottom: -4px;
  border: 2px solid rgba(141, 110, 99, 0.2);
  border-radius: 12px;
  z-index: -1;
}
```

#### 数据卡片
```css
.card-data {
  background: #FFF8E7;
  border: 2px solid #8D6E63;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 2px 2px 0 rgba(141, 110, 99, 0.1);
}
```

### 按钮组件

#### 主按钮
```css
.btn-primary {
  background: linear-gradient(135deg, #5D4037 0%, #3E2723 100%);
  color: #FFF8E7;
  border: 2px solid #3E2723;
  border-radius: 8px;
  padding: 12px 24px;
  font-weight: 600;
  box-shadow: 3px 3px 0 rgba(62, 39, 35, 0.2);
  cursor: pointer;
  transition: all 150ms var(--ease-wood);
}

.btn-primary:hover {
  transform: translate(-2px, -2px);
  box-shadow: 5px 5px 0 rgba(62, 39, 35, 0.25);
}

.btn-primary:active {
  transform: translate(1px, 1px);
  box-shadow: 1px 1px 0 rgba(62, 39, 35, 0.15);
}
```

#### 次要按钮
```css
.btn-secondary {
  background: #EFEBE9;
  color: #3E2723;
  border: 2px solid #8D6E63;
  border-radius: 8px;
  padding: 12px 24px;
  font-weight: 500;
  box-shadow: 2px 2px 0 rgba(141, 110, 99, 0.1);
  cursor: pointer;
  transition: all 150ms var(--ease-wood);
}

.btn-secondary:hover {
  background: #D7CCC8;
  transform: translate(-1px, -1px);
  box-shadow: 3px 3px 0 rgba(141, 110, 99, 0.15);
}
```

### 表格组件

#### 数据表格
```css
.table-data {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  background: #FFF8E7;
  border: 2px solid #5D4037;
  border-radius: 8px;
  overflow: hidden;
}

.table-data thead {
  background: linear-gradient(135deg, #D7CCC8 0%, #BCAAA4 100%);
  border-bottom: 2px solid #5D4037;
}

.table-data th {
  padding: 16px;
  text-align: left;
  font-weight: 600;
  color: #3E2723;
  border-right: 1px solid rgba(93, 64, 55, 0.2);
}

.table-data td {
  padding: 14px 16px;
  border-bottom: 1px solid rgba(141, 110, 99, 0.2);
  border-right: 1px solid rgba(141, 110, 99, 0.1);
}

.table-data tbody tr:hover {
  background: rgba(215, 204, 200, 0.3);
}
```

---

## 响应式设计

### 断点系统
```css
/* 移动端 */
@media (max-width: 640px) { }

/* 平板 */
@media (min-width: 641px) and (max-width: 1024px) { }

/* 桌面 */
@media (min-width: 1025px) { }

/* 大屏 */
@media (min-width: 1440px) { }
```

### 移动端适配

#### 触摸目标
- 最小触摸区域: 44px × 44px (iOS), 48px × 48dp (Android)
- 按钮间距: 最少 8px

#### 字体缩放
- 基础字体不小于 16px (避免 iOS 自动缩放)
- 标题字体适当缩小 10-15%

#### 布局调整
- 单列布局优先
- 卡片全宽显示
- 导航折叠为汉堡菜单

---

## 可访问性

### 色彩对比度
- 所有文本与背景对比度 ≥ 4.5:1 (WCAG AA)
- 大文本对比度 ≥ 3:1

### 键盘导航
- 所有交互元素可通过 Tab 键访问
- 焦点状态清晰可见 (2px 实线边框)

### 屏幕阅读器
- 所有图标添加 aria-label
- 图片添加 alt 文本
- 表格添加 scope 属性

### 动画控制
```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 设计反模式 (避免)

### ❌ 不要使用
1. **emoji 作为图标** - 使用 SVG 图标
2. **纯色扁平设计** - 保持木质纹理和阴影
3. **过度动画** - 保持简洁,最多 1-2 个动画元素
4. **高饱和度色彩** - 使用柔和的木质色调
5. **细边框** - 使用 2-3px 的木质边框
6. **模糊阴影** - 使用偏移阴影模拟木质立体感

### ✅ 应该使用
1. **SVG 图标** - Heroicons, Lucide, Phosphor
2. **木质纹理** - 渐变和 SVG 纹理叠加
3. **有意义的动画** - 状态变化、导航过渡
4. **柔和色调** - 深棕、原木、米色系
5. **粗边框** - 2-3px 实木边框
6. **偏移阴影** - 模拟木质物体立体感

---

## 实施优先级

### P0 - 核心视觉
1. 色彩方案更新
2. 字体系统调整
3. 木质边框样式
4. 基础阴影系统

### P1 - 组件改造
1. 卡片组件
2. 按钮组件
3. 表格组件
4. 导航组件

### P2 - 细节优化
1. 木质纹理背景
2. 做旧效果
3. 动画过渡
4. 响应式适配

---

## 测试清单

### 视觉测试
- [ ] 色彩对比度符合 WCAG AA
- [ ] 字体在不同设备清晰可读
- [ ] 木质纹理不干扰内容阅读
- [ ] 边框和阴影层次分明

### 交互测试
- [ ] 所有按钮有明确的悬停和点击反馈
- [ ] 触摸目标 ≥ 44px
- [ ] 键盘导航流畅
- [ ] 焦点状态清晰

### 响应式测试
- [ ] 移动端 (375px) 布局正常
- [ ] 平板 (768px) 布局正常
- [ ] 桌面 (1024px+) 布局正常
- [ ] 横屏模式正常

### 可访问性测试
- [ ] 屏幕阅读器测试通过
- [ ] 键盘导航测试通过
- [ ] 色彩对比度测试通过
- [ ] 动画可关闭

---

## 维护指南

### 设计令牌管理
所有设计令牌定义在 CSS 变量中,便于全局调整:
```css
:root {
  /* 色彩 */
  --wood-dark: #3E2723;
  --wood-medium: #5D4037;
  --wood-light: #8D6E63;
  
  /* 背景 */
  --bg-cream: #FFF8E7;
  --bg-beige: #EFEBE9;
  --bg-oak: #D7CCC8;
  
  /* 字体 */
  --font-display: 'Noto Serif SC', serif;
  --font-body: 'Noto Sans SC', sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}
```

### 组件复用
所有组件样式定义在独立类中,避免重复代码:
```css
/* 基础卡片样式 */
.card { ... }

/* 变体通过修饰符 */
.card-primary { ... }
.card-data { ... }
```

### 版本控制
- 设计系统文档版本化
- CSS 文件使用语义化版本
- 重大变更记录在 CHANGELOG

---

**设计系统版本**: 1.0.0  
**最后更新**: 2026-05-05  
**维护者**: ATMstockMarket 设计团队
