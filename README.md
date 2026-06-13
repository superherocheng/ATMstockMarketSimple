# ATMstockMarketSimple

<div align="center">

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14%2B-336791?logo=postgresql&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![ICIR](https://img.shields.io/badge/ICIR-0.91-brightgreen)
![ETF](https://img.shields.io/badge/ETF-32-blue)

**A股ETF量化监控平台 | Chinese A-Share ETF Quantitative Monitoring Platform**

[功能特性](#功能特性) • [因子模型](#-多因子模型) • [快速开始](#快速开始) • [API文档](#api-端点) • [部署](#docker-部署)

</div>

---

## 📖 项目简介

ATMstockMarketSimple 是一个专注于中国A股 **ETF市场** 的量化监控平台，提供指数ETF跟踪、行业轮动可视化、份额变化分析、**多因子分析**、**投资建议**等功能。采用 **FastAPI + PostgreSQL** 架构，前端使用 **Jinja2 + Tailwind CSS + ECharts 5**。

> **核心定位**：基于多因子模型的ETF量化监控与投资决策辅助平台。

## ✨ 功能特性

### 📊 数据监控
- 🎯 **指数ETF监控** - 实时追踪沪深300、中证500、上证50、中证1000、科创50等核心指数
- 📊 **行业ETF轮动** - 可视化32个行业ETF资金流向，发现板块轮动机会
- 📈 **份额变化分析** - 自动计算份额变化标准差，提供趋势判断
- 📉 **K线图表展示** - 基于ECharts 5的专业K线图，支持多维度数据分析

- 🔄 **一键更新+回测** - 更新ETF数据后自动运行因子计算+IC分析，一步到位
- 🛡️ **份额完整性检查** - 因子计算前自动检查截面数据是否齐全，份额不全时跳过计算
- 🏠 **首页因子概览** - 首页IC汇总卡片，展示各预设的IC均值/ICIR/胜率及六因子权重

### 🔬 量化分析
- 🔬 **六因子评分模型** - RSRS(阻力支撑) + 资金流(Flow) + 动量(Mom) + RSI动量(RSI_Mom)，Optimized预设ICIR=0.91
- 💪 **RSRS因子** - 基于高低点滚动OLS回归(β×R²)，衡量支撑/阻力结构强度，与动量极低共线性(Pearson<0.23)
- ⚡ **向量化因子引擎** - 滑动窗口预计算RSRS/Flow/Mom，全量回测从~25s降至~5s，提速5-8x
- 🔄 **并行预设计算+数据共享** - 4组预设并行计算，DB全表扫描仅执行一次，避免重复IO
- 📈 **IC有效性检验** - Spearman Rank IC + ICIR + IC衰减曲线 + **滚动ICIR衰退检测**
- 🎯 **四象限分类+RSRS覆盖** - Q1强势/Q2潜伏/Q3撤离/Q4风险；Q3中RSRS>0.3的品种按信号强度纳入候选
- 🏆 **投资建议引擎** - 因子得分 + RSRS象限覆盖 + IC置信度 + 两阶段相关性惩罚 + 大盘择时 + 滚动ICIR衰减检测 → 仓位配置
- 📡 **大盘择时** - 基于中证500 RSI+动量+份额变化的市场状态判断
- 🛡️ **数据覆盖回退** - 最新交易日数据不全时自动回退到最近完整日期
- 🧪 **泛化性验证** - 32-ETF池滚动3月验证：ICIR=0.91，年化超额22.5%（扣0.10%成本），换手率76%

### 🎨 用户体验
- 📋 **专业投资报告** - 报告式投资建议页，含KPI指标+排名表+风险提示
- 📱 **全端适配** - 响应式布局，桌面+移动端统一体验
- 🌙 **暗色模式** - 完整支持light/dark主题切换
- 🎯 **专业设计系统** - 设计令牌（Design Tokens）驱动的圆角、阴影、间距体系
- 📊 **增强KPI仪表板** - 因子分析页KPI卡片含趋势箭头(▲▼)、悬停蓝色指示条
- ⓘ **富文本信息提示** - 悬停ⓘ图标弹出260px宽度专业解读卡片
- 📡 **数据新鲜度状态栏** - 全站顶部显示数据日期+大盘择时信号
- 🔍 **Sector 页面搜索** - 实时搜索ETF名称/代码，分类分组折叠面板，分页加载
- 📊 **ETF 份额Z-score汇总** - 指数ETF页面显示5只ETF最新份额标准差
- 📌 **固定侧边栏+底部横幅** - 导航栏和底部版权信息固定不随页面滚动
- 🎨 **统一涨跌配色** - 全站统一红涨绿跌（A股惯例），移除可切换配色功能
- 🏠 **增强市场择时横幅** - 带状态图标的择时信号卡片，百分比大字突出显示
- 📭 **引导式空状态** - 投资建议页数据缺失时显示操作引导而非报错

## 🔬 多因子模型

### 因子组合

```
综合因子 = w_rsrs × z_rsrs + w_flow × z_flow + w_mom × z_mom
         + w_quality × z_quality + w_efficiency × z_efficiency
         + w_rsi × z_rsi_momentum
```

| 子因子 | 计算方式 | 说明 |
|--------|----------|------|
| **RSRS(阻力支撑)** | 高低点滚动OLS回归(β×R²)，N日窗口 | 支撑/阻力结构强度，与动量极低共线性(Pearson<0.23) |
| **资金流(Flow)** | EWMA加权斜率 (半衰期3天) → Rank标准化 | 份额变化趋势，近期敏感 |
| **动量(Mom)** | 累计收益率 / 60日波动率 | 风险调整后动量 |
| **财务质量(Quality)** | ROE/毛利率/负债率/现金流质量综合评分 | 基本面防御力（V4） |
| **日内效率(Efficiency)** | OHLC排列熵与趋势效率代理 | 交易结构稳定性（V5） |
| **RSI动量(RSI_Mom)** | RSI(5)-RSI(20)，规模中性化后Rank标准化 | 短期均值回归信号（V6） |

### 权重配置

| 预设 | RSRS | Flow | Mom | Quality | Efficiency | RSI_Mom | 适用场景 |
|------|:----:|:----:|:---:|:-------:|:----------:|:-------:|----------|
| **Optimized** | 0.38 | 0.22 | 0.32 | 0 | 0 | 0.08 | **推荐** (H=15, ICIR=0.91) |
| **short** | 0.258 | 0.129 | 0.258 | 0.184 | 0.092 | 0.08 | 短线 (H=10) |
| **medium** | 0.193 | 0.193 | 0.258 | 0.184 | 0.092 | 0.08 | 中线 (H=20) |
| **long** | 0.161 | 0.161 | 0.322 | 0.184 | 0.092 | 0.08 | 长线 (H=40) |

### Optimized预设回测结果

32-ETF池滚动3月验证（3月训练+1月预测，步长1月，8个窗口）：

| 指标 | 值 | 说明 |
|------|:--:|------|
| **ICIR** | **0.91** | 因子信号稳定性 |
| **胜率** | **71.1%** | 方向正确率 |
| **年化超额** | **22.5%** | 扣除0.10%单边成本后 |
| **夏普比率** | **1.76** | 风险调整后收益 |
| **月换手率** | **76%** | stickiness=1.0组合粘性 |

因子归因（Top-5 vs Bottom-5 收益差）：RSRS +63%, Momentum +22%, Flow -15%, RSI_Mom -25%

### 数据处理

- **Rank秩标准化** — 标准分排名替代Z-Score，更适应小样本(32只)截面
- **横截面标准化** — 所有因子经Rank标准化后合成复合因子
- **RSRS MA20趋势过滤** — 当MA20下降时，z_rsrs信号衰减50%
- **组合粘性(Stickiness)** — 对非持仓ETF的因子得分施加惩罚，降低换手率

### 投资建议引擎

```
因子得分 + RSRS覆盖 + 两阶段相关惩罚 + ICIR衰减检测 + 大盘择时 → 风险预算分配 → 仓位
```

- 主要推荐Q1(强势)+Q2(潜伏)象限ETF；Q3中RSRS>0.3且综合因子>0的品种按信号强度纳入候选
- ETF间相关性采用两阶段惩罚：先取前10名候选，在池内成对惩罚高相关者，重排序后取前5
- 大盘择时信号(RSI+动量+份额流)调整总仓位 ±30%
- 单ETF仓位上限25%
- **滚动ICIR衰退检测** — 近60日滚动ICIR较全样ICIR衰减>40%时提示因子预测力下降

## 🛠️ 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **后端** | Python 3.12 · FastAPI · Uvicorn | 高性能异步Web框架 |
| **数据库** | PostgreSQL · SQLAlchemy | 关系型数据库 + ORM |
| **缓存** | Redis + 内存LRU | 双重缓存策略 |
| **前端** | Jinja2 · Tailwind CSS · vanilla JS | 服务端渲染 + 现代CSS |
| **可视化** | ECharts 5 (bundled) | 无需CDN，离线可用 |
| **数据源** | Tushare Pro | 专业金融数据接口 |

## 🚀 快速开始

### 环境要求

- Python 3.12+
- PostgreSQL 14+
- Redis (可选，用于缓存)
- Tushare Pro Token ([获取地址](https://tushare.pro/))

### Docker 部署（推荐，VPS一键部署）

```bash
# 1. 克隆仓库
git clone https://github.com/superherocheng/ATMstockMarketSimple.git
cd ATMstockMarketSimple

# 2. 配置环境变量（只需填写 Tushare Token）
cp .env.example .env
nano .env
# 必填：TUSHARE_TOKEN=your_token_here
# 可选：修改 POSTGRES_PASSWORD（默认 password）

# 3. 一键启动（含PostgreSQL + Redis + 自动迁移）
docker compose up -d --build

# 4. 查看启动日志
docker logs -f atmstockmarket

# 5. 拉取ETF历史数据（首次部署必须执行）
docker exec atmstockmarket python3 -u /app/src/data_fetchers/tushare_fetcher.py --etf

# 6. 访问 http://your-vps-ip:5656
#    首页点击 "Update + Backtest" 开始使用
```

**日常更新**：直接在首页点击 "Update + Backtest" 按钮即可，无需SSH登录。

**更新代码**：
```bash
cd ATMstockMarketSimple
git pull
docker compose up -d --build
```

### 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入 TUSHARE_TOKEN 和 DATABASE_URL

# 初始化数据库
alembic upgrade head

# 获取ETF数据
python3 -u src/data_fetchers/tushare_fetcher.py --etf

# 启动服务
uvicorn src.web.app:app --reload --port 5656
```

## 📊 路由 & 页面

| 路由 | 页面 | 功能描述 |
|------|------|----------|
| `/` | index.html | 首页 — 快速入门引导、32行业板块数据、数据管理 |
| `/etf` | etf.html | 指数ETF详情 — K线走势、份额分析、异常检测 |
| `/sector` | sector.html | 行业ETF轮动 — 32行业对比、信号排序、份额趋势 |
| `/analysis` | analysis.html | 因子分析 — 因子分布、IC序列、四象限模型、收益预测 |
| `/analysis/investment-recommendation` | investment_recommendation.html | 投资建议 — ETF排名、仓位配置、风险提示 |
| `/analysis/tech-notes` | tech_notes.html | 技术说明 — 因子模型文档、泛化测试结论 |

## 🎯 监控ETF列表

### 指数ETF（5只）

| ETF代码 | 名称 | 说明 |
|---------|------|------|
| 510300.SH | 沪深300ETF | A股核心资产代表 |
| 510500.SH | 中证500ETF | 中盘股风向标（含择时信号） |
| 510050.SH | 上证50ETF | 蓝筹中的蓝筹 |
| 512100.SH | 中证1000ETF | 小盘股代表 |
| 588000.SH | 科创50ETF | 科技创新龙头 |

### 行业ETF（32只）

| ETF代码 | 名称 | ETF代码 | 名称 |
|---------|------|---------|------|
| 512480.SH | 半导体ETF | 515030.SH | 新能源车ETF |
| 512010.SH | 医药ETF | 512800.SH | 银行ETF |
| 512880.SH | 证券ETF | 159928.SZ | 消费ETF |
| 515880.SH | 通信ETF | 159206.SZ | 卫星ETF |
| 515220.SH | 煤炭ETF | 512400.SH | 有色ETF |
| 562500.SH | 机器人ETF | 512690.SH | 白酒ETF |
| 159611.SZ | 电力ETF | 512980.SH | 传媒ETF |
| 515210.SH | 钢铁ETF | 159870.SZ | 化工ETF |
| 561360.SH | 石油ETF | 512710.SH | 军工龙头ETF |
| 515790.SH | 光伏ETF | 159934.SZ | 黄金ETF |
| 159865.SZ | 养殖ETF | 159766.SZ | 旅游ETF |
| 159852.SZ | 软件ETF | 159851.SZ | 金融科技ETF |
| 512170.SH | 医疗ETF | 159869.SZ | 游戏ETF |
| 159755.SZ | 电池ETF | 516150.SH | 稀土ETF |
| 159638.SZ | 高端装备ETF | 159930.SZ | 能源ETF |
| 515000.SH | 科技ETF | 159326.SZ | 电网设备ETF |

## 🔌 API 端点

### 数据查询

| 方法 | 路由 | 描述 |
|------|------|------|
| GET | `/api/overview` | 首页概览（指数ETF + 行业摘要） |
| GET | `/api/data-range` | 各数据表状态与日期范围 |
| GET | `/api/index-etf/{code}` | 单只指数ETF完整数据 |
| GET | `/api/sector-etf` | 全部行业ETF数据（含因子信号标签） |
| GET | `/api/share-std/{code}` | ETF份额变化标准差分析 |

### 量化分析

| 方法 | 路由 | 描述 |
|------|------|------|
| GET | `/api/analysis/presets` | 因子预设列表 |
| GET | `/api/analysis/summary` | 因子摘要（IC均值、ICIR、胜率） |
| GET | `/api/analysis/ic-summary-all` | 首页因子概览（全预设IC汇总） |
| GET | `/api/analysis/factor-distribution` | 因子分布直方图 |
| GET | `/api/analysis/ic-series` | IC时间序列 |
| GET | `/api/analysis/quadrant-heatmap` | 四象限收益热力图 |
| GET | `/api/analysis/group-returns` | 分组累计收益 |
| GET | `/api/analysis/rolling-icir` | 滚动ICIR |
| GET | `/api/investment-recommendation` | 投资建议报告（含仓位配置） |
| GET | `/api/market-timing` | 大盘择时信号 |
| POST | `/api/analysis/recompute` | 触发因子+IC重算 |

### 数据管理

| 方法 | 路由 | 描述 |
|------|------|------|
| POST | `/api/fetch/all` | 一键更新+回测 |
| GET | `/api/fetch/status` | 数据获取+回测任务状态轮询 |
| GET | `/api/etf-share/status` | ETF份额数据状态检查 |
| POST | `/api/etf-share/update` | ETF份额智能更新 |

## 🔬 因子分析术语

| 术语 | 说明 |
|------|------|
| **Q1 强势** | z_flow ≥ 0, z_mom ≥ 0 — 资金流入+价格上涨，趋势最强 |
| **Q2 潜伏** | z_flow ≥ 0, z_mom < 0 — 资金流入但价格下跌，左侧布局 |
| **Q3 撤离** | z_flow < 0, z_mom < 0 — 资金流出+价格下跌，回避 |
| **Q4 风险** | z_flow < 0, z_mom ≥ 0 — 资金流出但价格上涨，警惕诱多 |
| **IC** | 信息系数，衡量因子预测力（>0.03为有效） |
| **ICIR** | IC均值/标准差，衡量因子稳定性（>0.3为可用） |

## 📋 v20.0.0 更新日志

### 🧪 模型泛化性验证 (V8)

| 模块 | 改动 |
|------|------|
| **ETF池扩充** | 从17只扩充至32只行业ETF，覆盖半导体、医药、军工、光伏、黄金、农业、旅游、软件等32个板块 |
| **ETF筛选器** | 新增 `scripts/etf_screener.py` — 基于Tushare API自动筛选高流动性ETF，按行业/跨境/债券分类去重 |
| **泛化测试** | 新增 `scripts/generalization_test.py` — 滚动3月训练+1月预测验证框架，8个窗口 |
| **部署优化器** | 新增 `scripts/deployment_optimizer.py` — 换手率优化、极端窗口稳健性、因子归因三方向测试 |
| **Optimized预设** | Quality/Efficiency因子权重归零（ICIR分别为-0.24/-0.19），RSRS MA20趋势过滤，组合粘性stickiness=1.0 |
| **回测结果** | 32-ETF池ICIR=0.91，年化超额22.5%（扣0.10%成本），胜率71.1%，夏普1.76 |

### 📊 网站更新

| 模块 | 改动 |
|------|------|
| **技术文档** | 新增"模型泛化与回测结果"章节：完整回测指标、因子归因、W5分析 |
| **投资建议** | 策略描述包含ICIR/超额/换手率指标；数据更新后自动重算因子+IC+建议 |
| **首页** | "17 Sectors" → "32 Sectors"；热力图展示32个板块 |
| **分析页** | Optimized preset作为默认；图表自动使用36-ETF数据 |
| **IC重算** | 全部预设IC基于扩大ETF池重新计算 |

### 📝 新增脚本

| 脚本 | 用途 |
|------|------|
| `scripts/etf_screener.py` | Tushare ETF筛选器：流动性≥5000万/日，排除宽基，行业去重 |
| `scripts/generalization_test.py` | 滚动验证框架：3月训练+1月预测，ICIR/WR/超额评估 |
| `scripts/deployment_optimizer.py` | 部署优化器：换手率粘性、W5稳健性、因子归因 |
| `scripts/goal_cost_generalize.py` | 成本侵蚀+泛化测试 |
| `scripts/robustness_tests.py` | 稳健性压力测试 |

## 📋 v21.1.0 更新日志

### 🐛 修复：数据库连接泄露导致网站崩溃

| 模块 | 改动 |
|------|------|
| **fetch.py** | 修复 `份额完整性检查` 中 `conn = get_conn()` 未关闭导致的数据库连接泄露，改为 `with get_conn() as conn:` 确保连接自动归还连接池 |
| **db_manager_postgresql.py** | 连接池优化，增强稳定性 |
| **CSS** | 移动端底部导航栏高度调整 |

**问题现象**：容器运行一段时间后，数据库连接池被耗尽，健康检查 `/health` 阻塞超时，Docker 标记容器为 `unhealthy`，导致 `https://stock.gaodeqingchuda.icu/` 无法访问。

**修复验证**：重启后容器立即恢复 `healthy` 状态，首页 `/` 返回 HTTP 200，健康检查通过。

---

## 📋 v21.0.0 更新日志

### 🎨 UI/UX 全面优化

| 模块 | 改动 |
|------|------|
| **Sector 页面** | 新增实时搜索栏（按名称/代码筛选）、分类分组折叠面板（科技/金融/消费/医药/周期/新能源/公用/商品）、分页加载（每页10只） |
| **ETF 页面** | 新增5只指数ETF份额变化Z-score汇总行，显示在标签按钮下方 |
| **固定布局** | 左侧导航栏改为 `position: fixed`，不随页面滚动；底部版权横幅固定于屏幕底部 |
| **涨跌配色统一** | 全站统一红涨绿跌（`--c-up: #DC2626` / `--c-down: #16A34A`），移除可切换配色开关 |

### 🔧 数据层改进

| 模块 | 改动 |
|------|------|
| **份额日期修正** | `etf_share` 数据日期限制在最后一个交易日，避免T+1数据造成日期显示异常 |
| **数据不完整保护** | 份额数据覆盖<50%时投资建议API返回空状态，防止展示过时推荐 |
| **market_timing 修复** | 修复 `text - interval` PostgreSQL 类型错误（添加 `::date` 类型转换） |

---

## 📋 v21.2.0 更新日志

### 🐛 修复：Migration 008 DATE类型转换导致数据获取全面崩溃

#### 问题描述

Alembic Migration 008（`008_convert_trade_date_to_date.py`）将 `trade_date` 列从 `VARCHAR` 转换为 PostgreSQL 原生 `DATE` 类型。然而，Python 代码中多处日期比较逻辑未同步适配，导致**所有数据获取流程全面崩溃**：

- **`tushare_fetcher.py`** — `_get_max_date()` 返回 `datetime.date` 对象，而 `_is_fresh()` 将其与 `str` 类型比较，引发 `TypeError: '>=' not supported between instances of 'datetime.date' and 'str'`
- **`fetch.py`** — `api_etf_share_status()` 和 `api_etf_share_update()` 中存在同样的 `datetime.date` vs `str` 比较问题

**影响范围**：
- `POST /api/fetch/{task_type}` — Update按钮不可用
- `GET /api/etf-share/status` — 份额状态检查失败
- `POST /api/etf-share/update` — 份额更新失败
- 命令行 `tushare_fetcher.py --etf` — 全部数据获取失败

#### 修复内容

| 模块 | 改动 |
|------|------|
| **`tushare_fetcher.py`** | `_get_max_date()` 增加日期规范化：检测 `datetime.date` 返回值时自动转换为 `YYYYMMDD` 字符串（`strftime`），与 `trading_calendar.get_db_max_date()` 的处理方式保持一致 |
| **`fetch.py`** | 新增 `_normalise_date()` 工具函数，修复 `api_etf_share_status()` 和 `api_etf_share_update()` 中数据库 DATE 值与字符串的比较逻辑 |

**修复验证**：
- 数据获取：37/37 只ETF的6月9日份额数据全部成功写入 ✅
- 因子计算：5857 行 ✅
- IC分析：599 行 ✅
- ETF份额状态API：正常返回 ✅
- 完整 Update+Backtest 流程：正常运行，耗时约16秒 ✅

---

## 📋 v22.0.0 更新日志

### 🛡️ 全方位 BUG 审计 + 修复（212项扫描，42项确认修复）

> 基于6维度并行审计（代码质量、安全、数据库、性能、前端、投资引擎），经对抗性验证后确认修复。

| 优先级 | 修复数 | 关键修复 |
|--------|:------:|----------|
| **P0 阻断性** | 6 | 限流器死锁(RLock)、同步阻塞事件循环(asyncio.to_thread)、asyncio.run崩溃、暗色模式不可读、前视偏差、重复API调用 |
| **P1 严重** | 30 | CSRF/XSS安全加固、DB连接泄漏(9处)、Redis KEYS→SCAN、异常吞没→日志、因子引擎除零防护、NaN→None保留、IC原子化写入 |
| **P2 性能** | 6 | LRU list→OrderedDict O(1)、pool dispose移除、DataFrame预groupby、schema缓存、import优化 |
| **测试修复** | 7 | 通过率 91.8%→**100%**（96/96） |

### 🎨 UI/UX 专业投研工作台改造

> 从"数据面板"升级为"专业投研工作台"，全面优化视觉体验和交互设计。

| 模块 | 改动 |
|------|------|
| **设计令牌系统** | 圆角 0→4/6/8/12px、分层阴影体系（card/card-hover/nav）、按钮悬停上移+蓝色投影 |
| **KPI仪表板** | 卡片悬停蓝色顶部指示条、24px加粗数值、▲▼趋势箭头、●中性点 |
| **ⓘ富文本提示** | 浏览器原生title→CSS悬停弹出框（260px宽、圆角、阴影、深色背景白字） |
| **卡片/表面** | 所有card/glass/data-card/home-card增加border-radius + box-shadow + 悬停阴影升级 |
| **表格** | zebra-table border-collapse:separate + border-radius + overflow:hidden |
| **按钮系统** | border-radius:6px、主按钮蓝色投影+hover translateY(-1px)、tab/标签圆角化 |
| **ECharts图表** | tooltip圆角6px + box-shadow、主题色自动适配暗色模式 |
| **市场择时横幅** | 状态图标(📈📉➡️)+大字百分比(2xl/800)+背景色编码(涨/跌/中性) |
| **投资建议空状态** | 错误→引导式空状态（图标+标题+描述+操作按钮跳转首页） |
| **暗色模式** | 所有新组件圆角/阴影在暗色模式下完整适配 |

**修改统计**：21个文件 +664/-346行（BUG修复）+ 5个文件 UI/UX改造

---

## 📋 v23.1.0 更新日志

### 🎨 字体更换：Times New Roman + 宋体

> 全线字体从 Geist 更换为 Times New Roman（英文/数字）和 SimSun 宋体（中文），提升中文阅读体验。

| 模块 | 改动 |
|------|------|
| **字体变量** | `--font-body/--font-display`: `"Inter", system-ui` → `"Times New Roman", "SimSun", serif` |
| **等宽字体** | `--font-mono`: `"JetBrains Mono"` → `"Times New Roman", "SimSun", monospace` |
| **Favicon** | `font-family`: `system-ui, sans-serif` → `"Times New Roman", "SimSun", serif` |

**修改统计**：2 个文件 +3/-3 行

---

## 📋 v23.0.0 更新日志

### 🎨 Brutalist Swiss UI/UX 重设计 — 单色石墨粉笔风格

> 从多色 Wikipedia 风格全面迁移至严格的消色 Brutalist Swiss 设计体系（Geist 字体、1px 发丝边框、零阴影）。

| 模块 | 改动 |
|------|------|
| **配色** | 蓝色强调色(#2563EB) → 石墨黑(#0a0a0a)、纯白画布(#ffffff) |
| **边框** | #D4D4D8 → 发丝线 #e5e5e5，所有结构分隔改用 1px 边框 |
| **阴影** | 全部 box-shadow → **none**（边框优先哲学） |
| **圆角** | 6/8/12px → 10/14/26px 新标尺 |
| **间距** | rem 基准 → px 基准（4/8/10/12/16/20/24/32/40） |
| **字体** | Inter + Playfair + IBM Plex Mono → **Geist + Geist Mono** |
| **标题** | serif 700/900 → sans 600 紧密字距(-0.05em) |
| **链接** | Wikipedia 蓝 → 石墨色悬停下划线 |
| **暗色模式** | 蓝色强调 → 石墨(#e5e5e5) 在碳黑(#171717) 上 |

**保留项**：涨跌配色(🔴#DC2626 涨 / 🟢#16A34A 跌)、全部功能、响应式断点、导航系统、ECharts 单色图表

**修改统计**：9 个文件 +236/-257 行

---

## 📋 v21.3.0 更新日志

### 🐛 修复：交易日历多表回退 + 异步调用修复

| 模块 | 改动 |
|------|------|
| **`trading_calendar.py`** | 增强交易日判断：新增多表回退机制（`stock_daily` / `sector_etf_daily` / `index_etf_daily`），避免单表过期导致日期错误；优化未收盘时的回退逻辑，优先使用日历数据 |
| **`fetch.py`** | 修复 `api_etf_share_update()` 异步调用问题，使用 `asyncio.run()` 确保协程正确执行 |
| **日志** | 新增结构化日志记录，交易日判定过程可追溯 |

**修复验证**：
- 多表回退：任一数据表最新日期可用即可作为候选 ✅
- ETF份额更新：异步调用正常完成 ✅
- 完整 Update+Backtest 流程正常运行 ✅

---

## 📄 License

MIT License

---

<p align="center">数据来源: Tushare Pro / AKShare | 仅供学习研究，不构成投资建议</p>
