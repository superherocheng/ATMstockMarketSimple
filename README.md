# ATMstockMarketSimple 📈

<div align="center">

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14%2B-336791?logo=postgresql&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![ICIR](https://img.shields.io/badge/ICIR-0.35-success)

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
- 📊 **行业ETF轮动** - 可视化15个行业ETF资金流向，发现板块轮动机会
- 📈 **份额变化分析** - 自动计算份额变化标准差，提供趋势判断
- 📉 **K线图表展示** - 基于ECharts 5的专业K线图，支持多维度数据分析
- 🌡️ **相关性热力图** - 行业ETF份额波动相关性、K线中枢相关性矩阵可视化
- 🔄 **一键数据更新** - ETF份额自动检测更新，智能判断数据新鲜度

### 🔬 量化分析
- 🔬 **多因子评分模型** - 资金流(Flow) + 动量(Mom)因子线性组合，ICIR=0.35
- 📈 **IC有效性检验** - Spearman Rank IC + ICIR + IC衰减曲线
- 🎯 **四象限分类** - Q1强势/Q2潜伏/Q3撤离/Q4风险，直观定位ETF
- 🏆 **投资建议引擎** - 多因子得分 + IC置信度 + 大盘择时 + ETF间相关惩罚 → 仓位配置
- 📡 **大盘择时** - 基于中证500 RSI+动量+份额变化的市场状态判断

### 🎨 用户体验
- 📋 **专业投资报告** - 报告式投资建议页，含KPI指标+排名表+风险提示
- 📱 **全端适配** - 响应式布局，桌面+移动端统一体验
- 🌙 **暗色模式** - 完整支持light/dark主题切换
- 📡 **数据新鲜度状态栏** - 全站顶部显示数据日期+大盘择时信号

## 🔬 多因子模型

### 因子组合

```
综合因子 = 0.30 × z_flow(EWMA) + 0.70 × z_mom(vol-adj)
```

| 子因子 | 计算方式 | 说明 |
|--------|----------|------|
| **资金流(Flow)** | EWMA加权斜率 (半衰期3天) → Tanh压缩 | 份额变化趋势，近期敏感 |
| **动量(Mom)** | 累计收益率 / 60日波动率 | 风险调整后动量 |

### 数据处理

- **Winsorize 10%** — 截断极端值，消除小样本(15只)噪声
- **Cross-sectional Z-score** — 横截面标准化
- **行业中性化** — 按行业分组去均值（预留）

### IC表现 (短期预设, H=10天)

| 指标 | 旧值(交互项) | 新值(加性模型) |
|------|:-----------:|:-------------:|
| IC均值 | 0.008 | **0.121** |
| ICIR | 0.02 | **0.35** |
| IC胜率 | 52% | **61.2%** |

### 投资建议引擎

```
因子得分 + 象限 × 相关惩罚 + 大盘择时 → 风险预算分配 → 仓位
```

- 只推荐Q1(强势)+Q2(潜伏)象限ETF，剔除Q3/Q4高风险
- ETF间相关系数 > 0.6时自动降低权重
- 大盘择时信号(RSI+动量+份额流)调整总仓位 ±30%
- 单ETF仓位上限25%，Q1:Q2总权重比例 6:4

## 🛠️ 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **后端** | Python 3.12 · FastAPI · Uvicorn | 高性能异步Web框架 |
| **数据库** | PostgreSQL · SQLAlchemy | 关系型数据库 + ORM |
| **缓存** | Redis + 内存LRU | 双重缓存策略 |
| **前端** | Jinja2 · Tailwind CSS · vanilla JS | 服务端渲染 + 现代CSS |
| **可视化** | ECharts 5 (bundled) | 无需CDN，离线可用 |
| **数据源** | Tushare Pro | 专业金融数据接口 |

## 📁 项目结构

```
ATMstockMarketSimple/
├── src/
│   ├── web/                         # FastAPI Web应用
│   │   ├── app.py                   # 应用入口 (端口 8000)
│   │   ├── routers/                 # API路由模块
│   │   │   ├── analysis.py          # 因子分析 + 投资建议 + 市场择时端点
│   │   │   ├── etf.py               # ETF详情、行业ETF（含信号标签对齐）
│   │   │   ├── overview.py          # 首页/仪表盘
│   │   │   ├── fetch.py             # 数据获取端点
│   │   │   ├── heatmap.py           # 相关性热力图端点
│   │   │   └── telemetry.py         # 匿名使用统计埋点
│   │   ├── templates/               # Jinja2 HTML模板（7个页面）
│   │   ├── static/
│   │   │   ├── css/app.css          # 完整CSS设计系统 (Warm Sage)
│   │   │   └── js/app.js            # 通用JS + 骨架屏 + 导航等
│   │   └── services/
│   │       └── cache.py             # Redis + 内存缓存
│   ├── analysis/                    # 量化分析模块
│   │   ├── factor_engine.py         # 因子计算 (EWMA Flow + Mom + Winsorize)
│   │   ├── ic_analyzer.py           # IC/ICIR分析 + 象限收益
│   │   ├── chart_builder.py         # ECharts数据转换
│   │   ├── market_timing.py         # 中证500大盘择时
│   │   ├── recommendation_engine.py # 投资建议引擎
│   │   └── presets.py               # 因子预设配置
│   ├── core/                        # 数据库管理、交易日历
│   └── data_fetchers/              # Tushare数据获取
├── config/                          # ETF定义、阈值配置
├── data/                            # 本地数据缓存
├── alembic/                         # 数据库迁移
├── docs/                            # 设计文档
│   ├── IMPROVEMENT_ROADMAP.md       # 改进路线图
│   ├── INVESTMENT_RECOMMENDATION_DESIGN.md  # 投资建议设计评审
│   └── ...                          # 其他技术文档
├── docker-compose.yml               # Docker编排
└── .env.example                     # 环境变量示例
```

## 🚀 快速开始

### 环境要求

- Python 3.12+
- PostgreSQL 14+
- Redis (可选，用于缓存)
- Tushare Pro Token ([获取地址](https://tushare.pro/))

### Docker 部署（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/superherocheng/ATMstockMarketSimple.git
cd ATMstockMarketSimple

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填写 TUSHARE_TOKEN

# 3. 启动服务
docker compose up -d

# 4. 初始化数据库
docker exec atmstockmarket alembic upgrade head

# 5. 拉取ETF数据
docker exec atmstockmarket python3 -u /app/src/data_fetchers/tushare_fetcher.py --etf

# 6. 重启应用
docker restart atmstockmarket

# 访问 http://localhost:8000
```

### 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件

# 初始化数据库
alembic upgrade head

# 获取ETF数据
python3 -u src/data_fetchers/tushare_fetcher.py --etf

# 计算因子和IC
python3 -c "
from src.core.db_manager_postgresql import init_db_manager
from src.analysis import factor_engine, ic_analyzer
import os; os.environ['DATABASE_URL'] = 'postgresql://...'
init_db_manager(os.environ['DATABASE_URL'])
factor_engine.compute_all_factors()
ic_analyzer.compute_all_ic()
"

# 启动服务
uvicorn src.web.app:app --reload --port 8000
```

## 📊 路由 & 页面

| 路由 | 页面 | 功能描述 |
|------|------|----------|
| `/` | index.html | 首页 — 快速入门引导、行业热力图、数据管理 |
| `/etf` | etf.html | 指数ETF详情 — K线走势、份额分析、异常检测 |
| `/sector` | sector.html | 行业ETF轮动 — 15行业对比、信号排序、份额趋势 |
| `/analysis` | analysis.html | 因子分析 — 因子分布、IC序列、四象限模型、收益预测 |
| `/analysis/investment-recommendation` | investment_recommendation.html | 📋 **投资建议** — ETF排名、仓位配置、风险提示 |
| `/analysis/tech-notes` | tech_notes.html | 技术说明 — 因子模型文档 |
| `/heatmap` | heatmap.html | 相关性热力图 — 份额波动相关、K线中枢相关 |

## 🎯 监控ETF列表

### 指数ETF（5只）

| ETF代码 | 名称 | 说明 |
|---------|------|------|
| 510300.SH | 沪深300ETF | A股核心资产代表 |
| 510500.SH | 中证500ETF | 中盘股风向标（含择时信号） |
| 510050.SH | 上证50ETF | 蓝筹中的蓝筹 |
| 512100.SH | 中证1000ETF | 小盘股代表 |
| 588000.SH | 科创50ETF | 科技创新龙头 |

### 行业ETF（15只）

| ETF代码 | 名称 | ETF代码 | 名称 |
|---------|------|---------|------|
| 512480.SH | 半导体ETF | 515030.SH | 新能源车ETF |
| 512010.SH | 医药ETF | 512800.SH | 银行ETF |
| 512880.SH | 证券ETF | 159928.SZ | 消费ETF |
| 515880.SH | 通信ETF | 159206.SZ | 卫星ETF |
| 515220.SH | 煤炭ETF | 512400.SH | 有色ETF |
| 562500.SH | 机器人ETF | 512690.SH | 酒ETF |
| 159934.SZ | 黄金ETF | 159611.SZ | 电力ETF |
| 512980.SH | 传媒ETF | - | - |

## 🔌 API 端点

### 数据查询

| 方法 | 路由 | 描述 |
|------|------|------|
| GET | `/api/overview` | 首页概览（指数ETF + 行业摘要） |
| GET | `/api/heatmap` | 行业板块热力图 |
| GET | `/api/data-range` | 各数据表状态与日期范围 |
| GET | `/api/index-etf/{code}` | 单只指数ETF完整数据 |
| GET | `/api/sector-etf` | 全部行业ETF数据（含因子信号标签） |
| GET | `/api/share-std/{code}` | ETF份额变化标准差分析 |
| GET | `/api/heatmap/share-std-correlation` | 行业ETF份额变化波动相关性矩阵 |
| GET | `/api/heatmap/kline-pivot-correlation` | 中证500+行业ETF K线中枢相关性矩阵 |

### 量化分析

| 方法 | 路由 | 描述 |
|------|------|------|
| GET | `/api/analysis/presets` | 因子预设列表 |
| GET | `/api/analysis/summary` | 因子摘要（IC均值、ICIR、胜率） |
| GET | `/api/analysis/factor-distribution` | 因子分布直方图 |
| GET | `/api/analysis/ic-series` | IC时间序列 |
| GET | `/api/analysis/ic-decay` | IC衰减曲线 |
| GET | `/api/analysis/quadrant-heatmap` | 四象限收益热力图 |
| GET | `/api/analysis/group-returns` | 分组累计收益 |
| GET | `/api/analysis/rolling-icir` | 滚动ICIR |
| GET | `/api/analysis/weight-recommendation` | 权重推荐（旧版） |
| **GET** | **`/api/investment-recommendation`** | **📋 投资建议报告（含仓位配置）** |
| **GET** | **`/api/market-timing`** | **📡 大盘择时信号** |
| POST | `/api/analysis/recompute` | 触发因子+IC重算 |

### 数据管理

| 方法 | 路由 | 描述 |
|------|------|------|
| GET | `/api/etf-share/status` | ETF份额数据状态检查 |
| POST | `/api/etf-share/update` | ETF份额智能更新 |
| POST | `/api/fetch/etf` | ETF数据获取 |
| GET | `/api/fetch/status` | 数据获取任务状态轮询 |

## 📈 份额变化分析

### 核心指标

- **份额变化百分比**：每日份额变化 / 前一日份额 × 100%
- **标准差**：近N日份额变化百分比的标准差
- **Z-Score**：(最新变化 - 均值) / 标准差

### 趋势判断逻辑

| 判断结果 | 条件 |
|----------|------|
| 强势流入 | ZScore > 1.5 且趋势向上且量能放大 |
| 持续流入 | ZScore > 1.5 且趋势向上 |
| 温和流入 | ZScore > 0.5 且趋势向上 |
| 强势流出 | ZScore < -1.5 且趋势向下且量能放大 |
| 持续流出 | ZScore < -1.5 且趋势向下 |
| 温和流出 | ZScore < -0.5 且趋势向下 |
| 分歧加大 | ZScore > 0.5 但趋势向下 |
| 企稳回升 | ZScore < -0.5 但趋势向上 |
| 震荡整理 | 其他情况 |

## 🔬 因子分析术语

| 术语 | 说明 |
|------|------|
| **Q1 强势** | z_flow ≥ 0, z_mom ≥ 0 — 资金流入+价格上涨，趋势最强 |
| **Q2 潜伏** | z_flow ≥ 0, z_mom < 0 — 资金流入但价格下跌，左侧布局 |
| **Q3 撤离** | z_flow < 0, z_mom < 0 — 资金流出+价格下跌，回避 |
| **Q4 风险** | z_flow < 0, z_mom ≥ 0 — 资金流出但价格上涨，警惕诱多 |
| **IC** | 信息系数，衡量因子预测力（>0.03为有效） |
| **ICIR** | IC均值/标准差，衡量因子稳定性（>0.3为可用） |

## 📄 License

MIT License

---

<p align="center">数据来源: Tushare Pro / AKShare | 仅供学习研究，不构成投资建议</p>
