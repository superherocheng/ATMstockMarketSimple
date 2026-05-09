# ATMstockMarket — A股量化分析平台

A focused Chinese A-share ETF analysis web application. Built with **FastAPI** + **Jinja2** + **vanilla JS** + **ECharts 5**, providing ETF index tracking and sector rotation visualization.

> **Simplified edition** — removed React SPA, BARRA analytics, AKShare fetcher, stock/concept/industry routers, and redundant CSS/JS. Three pages, one dependency chain.

## 技术栈

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.9+ · FastAPI · Uvicorn |
| Database | PostgreSQL · SQLAlchemy |
| Frontend | Jinja2 · Tailwind CSS · vanilla JS · ECharts 5 (bundled) |
| Data Source | Tushare Pro |

## 项目结构

```
ATMstockMarket/
├── src/
│   ├── web/                    # FastAPI web application
│   │   ├── app.py                      # FastAPI entry point
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
│   │   └── services/                   # Cache, middleware, validators
│   ├── core/                           # Database manager, trading calendar
│   ├── data_fetchers/                  # Tushare data ingestion
│   └── __init__.py
├── config/                             # ETF definitions, thresholds
├── tests/                              # Unit tests
├── scripts/                            # Utility scripts
├── docs/                               # Architecture & deployment docs
├── data/                               # Local data cache (AKShare CSVs)
├── pyproject.toml
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## 快速开始

### 环境要求

- Python 3.9+
- PostgreSQL 14+

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/superherocheng/ATMstockMarket.git
cd ATMstockMarket

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填写 DATABASE_URL 和 TUSHARE_TOKEN

# 3. 安装依赖
pip install -r requirements.txt

# 4. 初始化数据库
python -c "from src.core.db_manager_postgresql import _ensure_db; _ensure_db()"

# 5. 启动
cd src/web && python app.py
# → http://localhost:8000
```

### Docker 部署

```bash
docker compose up -d
```

## 路由 & 页面

| Route | Page | Description |
|-------|------|-------------|
| `/` | index.html | 首页 — 三大指数ETF行情、行业热力图、数据管理 |
| `/etf` | etf.html | 指数ETF详情 — K线走势、份额分析、异常检测 |
| `/sector` | sector.html | 行业ETF轮动 — 横向对比、份额趋势、资金流向矩阵 |

## API 端点

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/overview` | 首页概览（指数ETF + 行业摘要） |
| GET | `/api/heatmap` | 行业板块热力图 |
| GET | `/api/data-range` | 各数据表状态与日期范围 |
| GET | `/api/index-etf/{code}` | 单只指数ETF完整数据（K线+份额+异常） |
| GET | `/api/sector-etf` | 全部行业ETF数据 |
| GET | `/api/sector-etf/{code}` | 单只行业ETF数据 |
| GET | `/api/sector-cards` | 行业ETF卡片摘要 |
| GET | `/api/analysis/validate` | 数据完整性校验 |
| GET | `/health` | 健康检查 |
| POST | `/api/fetch/all` | 全量数据获取 |
| POST | `/api/fetch/tushare` | Tushare数据获取 |
| POST | `/api/fetch/akshare` | AKShare数据获取 |
| GET | `/api/fetch/status` | 数据获取任务状态轮询 |

## 许可证

MIT — 仅供学习和研究使用，不构成投资建议。
