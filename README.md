# ATMstockMarketSimple 📈

<div align="center">

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14%2B-336791?logo=postgresql&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

**A股ETF量化监控平台 | Chinese A-Share ETF Quantitative Monitoring Platform**

[功能特性](#功能特性) • [快速开始](#快速开始) • [API文档](#api-端点) • [部署](#docker-部署)

</div>

---

## 📖 项目简介

ATMstockMarketSimple 是一个专注于中国A股 **ETF市场** 的量化监控平台，提供指数ETF跟踪、行业轮动可视化、份额变化分析、因子分析等功能。采用 **FastAPI + PostgreSQL** 架构，前端使用 **Jinja2 + Tailwind CSS + ECharts 5**，实现高性能数据展示。

> **核心定位**：专注于ETF市场监控，移除个股数据模块，提供更精准的ETF份额变化分析和趋势判断。

## ✨ 功能特性

- 🎯 **指数ETF监控** - 实时追踪沪深300、中证500、上证50、中证1000、科创50等核心指数
- 📊 **行业ETF轮动** - 可视化13个行业ETF资金流向，发现板块轮动机会
- 📈 **份额变化分析** - 自动计算份额变化标准差，提供趋势判断
- 🔍 **智能趋势判断** - 基于份额变化+量能的综合分析（强势流入/流出、温和流入/流出等）
- 📉 **K线图表展示** - 基于ECharts 5的专业K线图，支持多维度数据分析
- 🔬 **因子分析** - 因子分布可视化、IC值分析、因子收益预测
- 🌡️ **相关性热力图** - 行业ETF份额波动相关性、K线中枢相关性矩阵可视化
- 🔄 **一键数据更新** - ETF份额自动检测更新，智能判断数据新鲜度
- 🐳 **容器化部署** - 完整的Docker支持，一键部署到生产环境

## 🛠️ 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **后端** | Python 3.12 · FastAPI · Uvicorn | 高性能异步Web框架 |
| **数据库** | PostgreSQL · SQLAlchemy | 关系型数据库 + ORM |
| **缓存** | 内存LRU缓存 | 高效数据缓存 |
| **前端** | Jinja2 · Tailwind CSS · vanilla JS | 服务端渲染 + 现代CSS |
| **可视化** | ECharts 5 (bundled) | 无需CDN，离线可用 |
| **数据源** | Tushare Pro | 专业金融数据接口 |

## 📁 项目结构

```
ATMstockMarketSimple/
├── src/
│   ├── web/                    # FastAPI Web应用
│   │   ├── app.py                      # 应用入口 (端口 8000)
│   │   ├── routers/                    # API路由模块
│   │   │   ├── overview.py             # 首页/仪表盘
│   │   │   ├── etf.py                  # ETF详情、行业ETF
│   │   │   ├── fetch.py                # 数据获取端点
│   │   │   ├── analysis.py             # 因子分析端点
│   │   │   └── heatmap.py              # 相关性热力图端点
│   │   ├── templates/                  # Jinja2 HTML模板
│   │   │   ├── index.html              # 首页
│   │   │   ├── etf.html                # 指数ETF K线/异常
│   │   │   ├── sector.html             # 行业ETF轮动
│   │   │   ├── analysis.html           # 因子分析页面
│   │   │   └── heatmap.html            # 相关性热力图页面
│   │   └── services/
│   │       └── cache.py                # 内存LRU缓存
│   ├── analysis/                       # 因子分析模块
│   ├── core/                           # 数据库管理、交易日历
│   └── data_fetchers/                  # Tushare数据获取
├── config/                             # ETF定义、阈值配置
├── data/                               # 本地数据缓存
├── alembic/                            # 数据库迁移
├── docker-compose.yml                  # Docker编排
└── .env.example                        # 环境变量示例
```

## 🚀 快速开始

### 环境要求

- Python 3.12+
- PostgreSQL 14+
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

## 📊 路由 & 页面

| 路由 | 页面 | 功能描述 |
|------|------|----------|
| `/` | index.html | 首页 — 指数ETF行情、行业热力图、数据管理 |
| `/etf` | etf.html | 指数ETF详情 — K线走势、份额分析、异常检测 |
| `/sector` | sector.html | 行业ETF轮动 — 横向对比、份额趋势、排名表格 |
| `/analysis` | analysis.html | 因子分析 — 因子分布、IC值序列、收益预测 |
| `/heatmap` | heatmap.html | 相关性热力图 — 份额波动相关性、K线中枢相关性 |

## 🎯 监控ETF列表

### 指数ETF（5只）

| ETF代码 | 名称 | 说明 |
|---------|------|------|
| 510300.SH | 沪深300ETF | A股核心资产代表 |
| 510500.SH | 中证500ETF | 中盘股风向标 |
| 510050.SH | 上证50ETF | 蓝筹中的蓝筹 |
| 512100.SH | 中证1000ETF | 小盘股代表 |
| 588000.SH | 科创50ETF | 科技创新龙头 |

### 行业ETF（13只）

| ETF代码 | 名称 | ETF代码 | 名称 |
|---------|------|---------|------|
| 512480.SH | 半导体ETF | 515030.SH | 新能源车ETF |
| 512010.SH | 医药ETF | 512800.SH | 银行ETF |
| 512880.SH | 证券ETF | 159928.SZ | 消费ETF |
| 515880.SH | 通信ETF | 159206.SZ | 卫星ETF |
| 512400.SH | 有色ETF | 562500.SH | 机器人ETF |
| 159870.SZ | 化工ETF | 561360.SH | 石油ETF |
| 518880.SH | 黄金ETF | - | - |

## 🔌 API 端点

### 数据查询

| 方法 | 路由 | 描述 |
|------|------|------|
| GET | `/api/overview` | 首页概览（指数ETF + 行业摘要） |
| GET | `/api/heatmap` | 行业板块热力图 |
| GET | `/api/data-range` | 各数据表状态与日期范围 |
| GET | `/api/index-etf/{code}` | 单只指数ETF完整数据 |
| GET | `/api/sector-etf` | 全部行业ETF数据 |
| GET | `/api/share-std/{code}` | ETF份额变化标准差分析 |
| GET | `/api/heatmap/share-std-correlation` | 行业ETF份额变化波动相关性矩阵 |
| GET | `/api/heatmap/kline-pivot-correlation` | 中证500+行业ETF K线中枢相关性矩阵 |

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

## 🔄 数据更新流程

### ETF份额更新

1. 点击首页 **"ETF份额"** 按钮
2. 系统自动检测所有ETF份额是否更新到最新交易日
3. 如已是最新，显示汇总信息
4. 如需更新，尝试从Tushare获取新数据
5. 如Tushare数据不足，反馈哪些ETF待更新
6. 如数据足够，自动更新数据库

### 一键更新

点击 **"一键更新"** 按钮，自动更新所有ETF数据：
- 指数ETF日线 + 份额 + 复权因子
- 行业ETF日线 + 份额 + 复权因子
- 因子分析计算

## 🐛 常见问题

### Docker部署后首页显示"无数据"

```bash
# 1. 建表
docker exec atmstockmarket alembic upgrade head

# 2. 拉取数据
docker exec atmstockmarket python3 -u /app/src/data_fetchers/tushare_fetcher.py --etf

# 3. 重启
docker restart atmstockmarket
```

### ETF份额数据不更新

Tushare份额数据通常在交易日16:00后更新，请稍后再试。

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

**免责声明**: 本项目仅供学习和研究使用，不构成任何投资建议。投资有风险，入市需谨慎。

---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给一个 Star ⭐**

Made with ❤️ by ATMstockMarket Team

</div>
