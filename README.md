# ATMstockMarket — A股量化分析平台

A focused Chinese A-share ETF analysis web application. Built with **FastAPI** + **Jinja2** + **vanilla JS** + **ECharts 5**, providing ETF index tracking and sector rotation visualization.

> **Simplified edition** — removed React SPA, BARRA analytics, AKShare fetcher, stock/concept/industry routers, and redundant CSS/JS. Three pages, one dependency chain. Added Redis two-tier cache for better performance.

## 技术栈

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.9+ · FastAPI · Uvicorn |
| Database | PostgreSQL · SQLAlchemy |
| Cache | Redis (主) + 内存LRU (回退) |
| Frontend | Jinja2 · Tailwind CSS · vanilla JS · ECharts 5 (bundled) |
| Data Source | Tushare Pro |

## 项目结构

```
ATMstockMarket/
├── src/
│   ├── web/                    # FastAPI web application
│   │   ├── app.py                      # FastAPI entry point (port 8500)
│   │   ├── routers/                    # API route modules
│   │   │   ├── overview.py             # Homepage / dashboard
│   │   │   ├── etf.py                  # ETF detail, sector ETF
│   │   │   └── fetch.py                # Data fetching endpoints
│   │   ├── templates/                  # Jinja2 HTML templates
│   │   │   ├── index.html              # Homepage
│   │   │   ├── etf.html                # Index ETF K-line / anomaly
│   │   │   └── sector.html             # Sector ETF rotation
│   │   ├── static/                     # CSS, JS
│   │   │   ├── css/app.css             # All styles (consolidated)
│   │   │   ├── js/app.js               # All app JS (consolidated)
│   │   │   ├── js/vendor.js            # ECharts 5 (bundled, no CDN)
│   │   │   └── favicon.svg
│   │   └── services/
│   │       └── cache.py                # Redis + 内存LRU 两级缓存
│   ├── core/                           # Database manager, trading calendar
│   ├── data_fetchers/                  # Tushare data ingestion
│   └── __init__.py
├── config/                             # ETF definitions, thresholds
├── tests/                              # Unit tests
├── docs/                               # Architecture & deployment docs
├── data/                               # Local data cache
├── pyproject.toml
├── requirements.txt
├── Dockerfile                          # Single-stage (no React build)
├── docker-compose.yml
└── .env.example
```

## 快速开始

### 环境要求

- Python 3.9+
- PostgreSQL 14+
- Redis (可选，自动回退到内存缓存)

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/superherocheng/ATMstockMarket.git
cd ATMstockMarket

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填写 DATABASE_URL 和 TUSHARE_TOKEN
# 可选：配置 REDIS_HOST / REDIS_PORT / REDIS_DB

# 3. 安装依赖
pip install -r requirements.txt

# 4. 初始化数据库
python -c "from src.core.db_manager_postgresql import _ensure_db; _ensure_db()"

# 5. 启动
cd src/web && python app.py
# → http://localhost:8500
```

### Docker 部署

```bash
docker compose up -d
```

## 路由 & 页面

| Route | Page | Description |
|-------|------|-------------|
| `/` | index.html | 首页 — 指数ETF行情、行业热力图、数据管理 |
| `/etf` | etf.html | 指数ETF详情 — K线走势、份额分析、异常检测 |
| `/sector` | sector.html | 行业ETF轮动 — 横向对比、份额趋势、资金流向矩阵 |

## 监控指标

| ETF代码 | 名称 | 说明 |
|---------|------|------|
| 510300.SH | 沪深300ETF | 大盘蓝筹 |
| 510500.SH | 中证500ETF | 中盘成长 |
| 510050.SH | 上证50ETF | 超大盘 |
| 512100.SH | 中证1000ETF | 小盘成长 |
| 588000.SH | 科创50ETF | 科创板 |

## API 端点

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/overview` | 首页概览（指数ETF + 行业摘要，缓存5分钟） |
| GET | `/api/heatmap` | 行业板块热力图 |
| GET | `/api/data-range` | 各数据表状态与日期范围（缓存5分钟） |
| GET | `/api/index-etf/{code}` | 单只指数ETF完整数据（K线+份额+异常） |
| GET | `/api/sector-etf` | 全部行业ETF数据 |
| GET | `/api/sector-etf/{code}` | 单只行业ETF数据 |
| GET | `/api/sector-cards` | 行业ETF卡片摘要 |
| GET | `/api/analysis/validate` | 数据完整性校验 |
| GET | `/health` | 健康检查 |
| POST | `/api/fetch/all` | 全量数据获取 |
| POST | `/api/fetch/tushare` | Tushare数据获取 |
| GET | `/api/fetch/status` | 数据获取任务状态轮询 |

## 缓存策略

平台采用 **Redis + 内存LRU** 两级缓存：

- **Redis**: 主缓存层，支持应用重启后缓存预热
- **内存LRU**: 当Redis不可用时自动回退，避免单点故障
- 缓存分类：`overview`（首页）、`etf`（ETF详情）、`sector`（行业）
- 数据范围接口缓存5分钟，避免频繁查询数据库

## 许可证

MIT — 仅供学习和研究使用，不构成投资建议。
