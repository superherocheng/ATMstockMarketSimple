# ATMstockMarket — A股量化分析平台

A comprehensive Chinese A-share quantitative analysis web application built with FastAPI (backend) + Jinja2/React (dual frontend), providing ETF analysis, sector rotation, factor models, stock screening, and data management.

## 技术栈

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+ · FastAPI · Uvicorn |
| Database | PostgreSQL · SQLAlchemy · Alembic |
| Frontend (Primary) | Jinja2 · Tailwind CSS · vanilla JS · ECharts 5 |
| Frontend (React SPA) | React 19 · Vite 6 · Tailwind v4 · TanStack Query · ECharts 6 |
| Data Sources | Tushare Pro · AKShare |

## 项目结构

```
ATMstockMarket/
├── src/
│   ├── web/               # FastAPI web application
│   │   ├── app.py                # FastAPI entry point
│   │   ├── routers/              # API route modules
│   │   │   ├── overview.py       # Homepage / dashboard
│   │   │   ├── etf.py            # ETF detail & analysis
│   │   │   ├── stocks.py         # Stock rankings & screener
│   │   │   ├── barra.py          # BARRA factor analysis
│   │   │   ├── concept.py        # Concept/sector analysis
│   │   │   ├── industry.py       # SW industry analysis
│   │   │   └── fetch.py          # Data fetching endpoints
│   │   ├── templates/            # Jinja2 HTML templates
│   │   ├── static/               # CSS, JS, React build output
│   │   └── services/             # DB, cache, middleware
│   ├── core/                     # Database manager, trading calendar
│   ├── data_fetchers/            # Tushare / AKShare data ingestion
│   └── analytics/                # Factor computations, risk models
├── frontend/                     # React + Vite + Tailwind v4 SPA source
├── config/                       # ETF definitions, thresholds, settings
├── scripts/                      # Data fetching, migration, utility scripts
├── tests/                        # Unit and integration tests
└── docs/                         # Architecture, deployment, design docs
```

## 快速开始

### 环境要求

- Python 3.11+
- PostgreSQL 14+
- Node.js 18+ (for React frontend development)

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/your-username/ATMstockMarket.git
cd ATMstockMarket

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填写 DATABASE_URL 和 TUSHARE_TOKEN

# 3. 安装依赖
pip install -r requirements.txt

# 4. 初始化数据库
cd src/web && python -c "from services.db import _ensure_db; _ensure_db()"

# 5. 拉取数据
cd ../.. && python scripts/fetch_data.py --all

# 6. 启动服务器
cd src/web && python app.py
# → http://localhost:8000
```

### Docker 部署

```bash
docker compose up -d
```

### React 前端开发

```bash
cd frontend
npm install
npm run dev      # Dev server on :5173, proxies /api to :8000
npm run build    # Production build → ../src/web/static/react/
```

## 路由 & 页面

| Route | Type | Description |
|-------|------|-------------|
| `/` | Jinja2 | 首页 — 指数ETF、板块热力图、数据管理 |
| `/etf` | Jinja2 | 指数ETF详情 — K线、份额分析、异常检测 |
| `/sector` | Jinja2 | 行业ETF对比 — 轮动矩阵、双ETF叠加 |
| `/stocks` | Jinja2 | 股票排行 — 波动率、涨幅、基本面筛选、龙虎榜 |
| `/stock/{code}` | Jinja2 | 个股详情 — K线、布林带、MACD、基本面、四象限 |
| `/barra` | Jinja2 | BARRA因子分析 — 行业/动量/规模/风格面板 |
| `/concept` | Jinja2 | 概念板块分析 — 矩形树图、热度评分 |
| `/industry` | Jinja2 | 申万行业分析 — 分布图、市值对比 |
| `/react/` | React SPA | React入口（未完成页面重定向至Jinja2版本） |

## API 端点

主要数据获取端点（位于 `/fetch/` 路由下）：
- `POST /fetch/etf` — 拉取ETF数据
- `POST /fetch/barra` — 拉取BARRA因子数据
- `POST /fetch/concept` — 拉取概念板块数据
- `POST /fetch/industry` — 拉取行业数据

## 许可证

MIT — 仅供学习和研究使用，不构成投资建议。
