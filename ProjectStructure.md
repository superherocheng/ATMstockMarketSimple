# ATMstockMarketSimple — 项目结构总览

> 生成日期：2026-06-13
> 项目版本：21.3.0

---

## 项目概述

**ATMstockMarketSimple** 是一个专注于中国 A 股 **ETF 市场**的量化监控平台，提供指数 ETF 跟踪、行业轮动可视化、份额变化分析、**多因子分析**、**投资建议**等功能。

| 维度 | 说明 |
|------|------|
| **技术栈** | Python 3.12 + FastAPI + PostgreSQL + Jinja2 + Tailwind CSS + ECharts 5 + Redis |
| **数据源** | Tushare Pro（主要）、AKShare（辅助） |
| **数据库迁移** | Alembic（8 个迁移版本） |
| **核心定位** | 基于六因子模型的 ETF 量化监控与投资决策辅助平台 |
| **许可证** | MIT |

---

## 目录树

```
ATMstockMarketSimple/
├── src/                              # 核心源代码
│   ├── analysis/                     # 量化分析模块
│   │   ├── __init__.py
│   │   ├── backtest.py               # 回测引擎
│   │   ├── barra_neutralization.py   # Barra 风格因子中性化
│   │   ├── chart_builder.py          # ECharts 图表数据构建
│   │   ├── factor_engine.py          # 多因子模型核心（向量化计算）
│   │   ├── financial_factor.py       # 基本面财务质量因子
│   │   ├── ic_analyzer.py            # IC 有效性检验
│   │   ├── intraday_efficiency.py    # 日内效率因子
│   │   ├── market_timing.py          # 大盘择时信号
│   │   ├── presets.py                # 因子权重预设计置
│   │   ├── recommendation_engine.py  # 投资建议引擎
│   │   └── rsi_factor.py             # RSI 动量因子(V6)
│   ├── core/                         # 基础设施层
│   │   ├── __init__.py
│   │   ├── db_manager_postgresql.py  # PostgreSQL 连接池管理
│   │   └── trading_calendar.py       # A 股交易日历工具
│   ├── data_fetchers/                # 数据采集层
│   │   ├── __init__.py
│   │   ├── external_loader.py        # 外部 CSV 数据加载
│   │   └── tushare_fetcher.py        # Tushare Pro 数据抓取管线
│   └── web/                          # Web 应用层
│       ├── __init__.py
│       ├── app.py                    # FastAPI 应用入口
│       ├── routers/                  # HTTP 路由
│       │   ├── __init__.py
│       │   ├── analysis.py           # 分析相关 API
│       │   ├── etf.py                # ETF 数据 API
│       │   ├── fetch.py              # 数据抓取 API
│       │   ├── overview.py           # 首页概览 API
│       │   └── telemetry.py          # 遥测端点
│       ├── services/                 # Web 服务层
│       │   ├── __init__.py
│       │   ├── cache.py              # 双缓存（内存 LRU + Redis）
│       │   └── middleware.py         # 中间件（限流、缓存头）
│       ├── static/                   # 前端静态资源
│       │   ├── css/
│       │   │   └── app.css           # Tailwind 编译样式
│       │   ├── js/
│       │   │   ├── app.js            # 前端业务逻辑
│       │   │   └── vendor.js         # 第三方依赖
│       │   └── favicon.svg           # 站点图标
│       └── templates/                # Jinja2 模板
│           ├── index.html            # 首页
│           ├── analysis.html         # 分析页面
│           ├── etf.html              # 指数 ETF 页面
│           ├── sector.html           # 行业 ETF 页面
│           ├── investment_recommendation.html  # 投资报告页
│           └── tech_notes.html       # 技术说明页
├── alembic/                          # 数据库迁移
│   ├── versions/                     # 迁移版本
│   │   ├── 001_initial_schema.py
│   │   ├── 002_analysis_tables.py
│   │   ├── 003_add_rsrs_columns.py
│   │   ├── 004_add_financial_factor_table.py
│   │   ├── 005_add_quality_to_factor_daily.py
│   │   ├── 006_add_intraday_efficiency.py
│   │   ├── 007_add_rsi_momentum.py
│   │   └── 008_convert_trade_date_to_date.py
│   ├── env.py                        # Alembic 环境配置
│   └── script.py.mako                # 迁移脚本模板
├── config/                           # 项目配置
│   ├── __init__.py
│   ├── config.py                     # 主配置（ETF 列表、参数等）
│   └── config.py.example             # 配置模板
├── scripts/                          # 独立工具脚本（26 个）
│   ├── backtest_factor.py            # 因子回测
│   ├── backtest_historical.py        # 历史回测
│   ├── backtest_q4.py                # Q4 象限回测
│   ├── compare_3f_vs_4f.py           # 三因子 vs 四因子对比
│   ├── deployment_optimizer.py       # 部署优化
│   ├── etf_screener.py               # ETF 筛选器
│   ├── factor_optimizer.py           # 因子优化
│   ├── final_attempt.py
│   ├── generalization_test.py        # 泛化性测试
│   ├── goal_cost_generalize.py
│   ├── iteration_runner.py           # 迭代运行器
│   ├── load_allsymbol.py             # 全量标的加载
│   ├── package.sh                    # 打包脚本
│   ├── priority_a_risk.py            # 优先级 A - 风险分析
│   ├── priority_c.py                 # 优先级 C
│   ├── publish.sh                    # 发布脚本
│   ├── rank_vote_deep.py             # 排名投票深度分析
│   ├── robustness_tests.py           # 稳健性测试
│   ├── rolling_validation.py         # 滚动验证
│   ├── run_v4_recompute.py           # V4 重算
│   ├── setup.sh                      # 环境设置
│   ├── validate_h15.py               # H=15 验证
│   ├── verify_a2_a3.py               # A2/A3 验证
│   ├── verify_ic_lookahead.py        # IC 前瞻验证
│   ├── verify_rsrs.py                # RSRS 验证
│   └── verify_v4.py                  # V4 验证
├── tests/                            # 单元测试
│   ├── __init__.py
│   ├── conftest.py                   # pytest 共享夹具
│   └── unit/
│       ├── test_cache.py             # 缓存测试（LRU、TTL、并发）
│       ├── test_config.py            # 配置测试
│       ├── test_db_manager.py        # 数据库管理器测试
│       ├── test_factor_engine.py     # 因子引擎测试（17 方法）
│       ├── test_financial_factor.py  # 财务因子测试（29 方法）
│       ├── test_ic_analyzer.py       # IC 分析测试
│       ├── test_rate_limiter.py      # 限流器测试
│       └── test_recommendation.py    # 投资建议测试
├── docs/                             # 项目文档
│   ├── architecture/                 # 架构决策
│   │   ├── PostgreSQL-vs-DuckDB-Decision-Guide.md
│   │   └── React+FastAPI架构迁移方案.md
│   ├── deployment/                   # 部署文档
│   │   ├── MIGRATION_COMPLETE.md
│   │   ├── POSTGRESQL_MIGRATION.md
│   │   └── VPS_DEPLOY.md
│   ├── development/                  # 开发文档
│   │   ├── DATA_UPDATE_WORKFLOW.md
│   │   ├── FILE_INDEX.md
│   │   ├── PROJECT_RESTRUCTURE_PLAN.md
│   │   ├── PROJECT_STRUCTURE.md
│   │   ├── ProjectStructure.md
│   │   └── QUICK_START_GUIDE.md
│   ├── solutions/                    # 技术方案
│   │   └── INDUSTRY_DATA_SOLUTION.md
│   ├── superpowers/                  # 功能迭代规划
│   │   ├── plans/
│   │   │   ├── 2026-05-09-mobile-simplification-plan.md
│   │   │   ├── 2026-05-10-visual-analysis-plan.md
│   │   │   └── 2026-05-19-uiux-improvement-plan.md
│   │   └── specs/
│   │       ├── 2026-05-09-mobile-simplification-design.md
│   │       ├── 2026-05-10-claude-style-redesign.md
│   │       ├── 2026-05-10-visual-analysis-design.md
│   │       └── 2026-05-19-uiux-execution-plan.md
│   ├── BUG_AUDIT_REPORT_2026-06-12.md
│   ├── FIX_REPORT_2026-06-12.md
│   ├── IMPROVEMENT_ROADMAP.md
│   ├── INVESTMENT_RECOMMENDATION_DESIGN.md
│   ├── README.md
│   ├── VPSRevision.md
│   └── changelog-ui-ux-2026-05-17.md
├── docker/                           # Docker 相关
│   └── entrypoint.sh                 # 容器启动脚本
├── .github/workflows/                # CI/CD
│   └── ci.yml                        # GitHub Actions 配置
├── .codegraph/                       # CodeGraph 索引目录
├── pyproject.toml                    # 项目元数据与构建配置
├── requirements.txt                  # Python 依赖清单
├── Dockerfile                        # Docker 构建文件
├── docker-compose.yml                # Docker Compose 编排
├── alembic.ini                       # Alembic 配置
├── AGENTS.md                         # 项目地图（供 AI 代理使用）
├── README.md                         # 项目自述文件
├── .env.example                      # 环境变量模板
├── .gitignore
├── .dockerignore
├── .pre-commit-config.yaml           # pre-commit 钩子配置
└── .mcp.json                         # MCP 配置
```

---

## 架构分层

项目采用经典的四层架构，依赖关系严格单向：

```
路由层 (routers/)  →  服务层 (services/)  →  基础设施层 (core/)
    ↓                      ↓
分析层 (analysis/)   数据采集 (data_fetchers/)
    ↓                      ↓
基础设施层 (core/)    基础设施层 (core/)
```

### 依赖方向

- `routers/` → `services/cache` → `db_manager_postgresql`
- `routers/` → `analysis/*` → `db_manager_postgresql`
- `data_fetchers/` → `db_manager_postgresql`、`trading_calendar`

---

## 模块详解

### 1. `src/analysis/` — 量化分析（核心业务逻辑）

| 文件 | 职责 | 关键特性 |
|------|------|----------|
| `factor_engine.py` | **多因子模型引擎** | 向量化批量计算 RSRS/Flow/Mom 因子；4 组预设并行计算；单次 DB 全表扫描 |
| `financial_factor.py` | **基本面财务质量因子** | 从成分股 ROE/PB/净利增速聚合到 ETF；Quality 子评分 |
| `ic_analyzer.py` | **IC 有效性检验** | Spearman Rank IC；ICIR；滚动 ICIR 衰减检测 |
| `recommendation_engine.py` | **投资建议引擎** | 六因子评分 + RSRS 象限覆盖 + 两阶段相关性惩罚 + 大盘择时 + 仓位配置 |
| `presets.py` | **因子权重预设** | short/medium/long 三组权重配置 |
| `chart_builder.py` | **图表数据构建** | 雷达图/柱状图/IC 时序/象限散点/滚动 ICIR |
| `barra_neutralization.py` | **Barra 风险中性化** | OLS/Ridge 残差中性化 |
| `intraday_efficiency.py` | **日内效率因子(V5)** | OHLC 排列熵代理 |
| `rsi_factor.py` | **RSI 动量因子(V6)** | RSI(5)-RSI(20) 序列 |
| `market_timing.py` | **大盘择时** | RSI+动量+份额变化综合判断 |
| `backtest.py` | **回测引擎** | 支持多预设回测 |

### 2. `src/core/` — 基础设施

| 文件 | 职责 |
|------|------|
| `db_manager_postgresql.py` | PostgreSQL 连接池（单例模式）；`execute()` 被调用 105+ 次，是最高频函数 |
| `trading_calendar.py` | A 股交易日历；数据新鲜度检查；日期范围缺口检测 |

### 3. `src/data_fetchers/` — 数据采集

| 文件 | 职责 | 关键能力 |
|------|------|----------|
| `tushare_fetcher.py` | **Tushare Pro 数据管线**（26 函数） | 指数/行业 ETF 日线、份额、复权因子；个股日线、估值、财务指标；带限速的 API 调用封装 |
| `external_loader.py` | 外部 CSV 数据加载 | 列名标准化；元数据更新 |

### 4. `src/web/` — Web 层

#### 路由（5 个文件）

| 路由文件 | 主要端点 |
|----------|----------|
| `overview.py` | `GET /`（首页）、`GET /api/overview`、`GET /api/heatmap`、`GET /api/validate-analysis`、`GET /health`、`GET /api/data-range` |
| `analysis.py` | `GET /analysis`、`GET /analysis/tech-notes`、`GET /analysis/investment-recommendation`；API：presets、factor-distribution、ic-series、quadrant-heatmap、group-returns、rolling-icir、ic-summary-all、market-timing、financial-factors、recompute |
| `etf.py` | `GET /etf`、`GET /sector`；API：指数/行业 ETF 详情、份额标准差 |
| `fetch.py` | `GET /fetch`、`POST /api/fetch`、`GET /api/fetch-status`、`POST /api/etf-share-update`、`POST /api/cache-invalidate` |
| `telemetry.py` | 遥测端点 |

#### 服务

| 文件 | 职责 |
|------|------|
| `cache.py` | 双缓存策略：内存 LRU（始终开启，maxsize=1000，TTL 感知）+ Redis（可选） |
| `middleware.py` | 令牌桶限流（60 req/min per client）；Cache-Control 头 |

#### 前端

- **模板**：6 个 Jinja2 页面（首页、分析、ETF、行业 ETF、投资报告、技术说明）
- **静态资源**：Tailwind 编译 CSS + 业务 JS + 第三方 vendor JS
- **UI 技术**：Tailwind CSS + ECharts 5 图表 + 响应式布局 + 暗色模式

---

## 六因子模型

```
综合因子 = w_rsrs × z_rsrs + w_flow × z_flow + w_mom × z_mom
         + w_quality × z_quality + w_efficiency × z_efficiency
         + w_rsi × z_rsi_momentum
```

| 因子 | 计算方式 | 说明 |
|------|----------|------|
| **RSRS** | 高低点滚动 OLS 回归(β×R²)，N=18 | 支撑/阻力结构强度 |
| **Flow** | EWMA 加权斜率(半衰期 3 天) → Rank 标准化 | 资金流向趋势 |
| **Mom** | 累计收益率 / 60 日波动率 | 风险调整后动量 |
| **Quality** | ROE/毛利率/负债率/现金流综合评分 | 基本面防御力(V4) |
| **Efficiency** | OHLC 排列熵代理 | 交易结构稳定性(V5) |
| **RSI_Mom** | RSI(5)-RSI(20)，规模中性化 | 短期均值回归(V6) |

### 权重预设

| 预设 | RSRS | Flow | Mom | Qual | Eff | RSI_Mom | 持有期 |
|------|:----:|:----:|:---:|:----:|:---:|:-------:|:------:|
| short | 0.258 | 0.129 | 0.258 | 0.184 | 0.092 | 0.08 | H=10 |
| medium | 0.193 | 0.193 | 0.258 | 0.184 | 0.092 | 0.08 | H=20 |
| long | 0.161 | 0.161 | 0.322 | 0.184 | 0.092 | 0.08 | H=40 |

---

## 数据库模式（8 个迁移版本）

| 迁移 | 内容 |
|------|------|
| 001_initial_schema | `etf_daily`、`etf_share`、`trade_dates`、`stock_daily`、`stock_list`、`daily_basic`、`fina_indicator` |
| 002_analysis_tables | `factor_daily`、`ic_analysis`、`factor_preset_weights` |
| 003_add_rsrs_columns | factor_daily 表增加 RSRS 列 |
| 004_add_financial_factor_table | `financial_factors` 表 |
| 005_add_quality_to_factor_daily | factor_daily 增加 Quality 列 |
| 006_add_intraday_efficiency | 日内效率列 |
| 007_add_rsi_momentum | RSI 动量列 |
| 008_convert_trade_date_to_date | trade_date 类型转换（date 类型） |

---

## ETF 覆盖范围

- **指数 ETF（5 只）**：沪深300、中证500、上证50、中证1000、科创50
- **行业 ETF（32 只）**：半导体、新能源车、医药、银行、证券、消费、通信、军工、光伏、黄金、农业、旅游、软件、金融科技、医疗、游戏、电池、稀土、高端装备、能源、科技、电网设备等
- **商品 ETF**：黄金ETF、石油ETF（仅有技术面因子，无基本面因子）

---

## 测试覆盖

| 测试文件 | 方法数 | 覆盖模块 |
|----------|:------:|----------|
| test_factor_engine.py | 17 | 因子计算（RSRS/Flow/Mom/zscore/象限） |
| test_financial_factor.py | 29 | 代码转换、聚合、Quality 评分 |
| test_cache.py | 13 | LRU、TTL、并发安全 |
| test_config.py | 12 | 配置加载、ETF 列表、缓存配置 |
| test_rate_limiter.py | 7 | 令牌桶、TTL、并发 |
| test_db_manager.py | 5 | 位置参数适配、upsert |
| test_ic_analyzer.py | 5 | IC 计算、摘要统计 |
| test_recommendation.py | — | 投资建议流程 |

---

## 工具脚本

`scripts/` 目录包含 26 个独立脚本（含 Shell 脚本），用途包括：

- **回测验证**：`backtest_factor.py`、`backtest_historical.py`、`backtest_q4.py`、`rolling_validation.py`
- **因子研究**：`factor_optimizer.py`、`compare_3f_vs_4f.py`、`rank_vote_deep.py`
- **稳健性测试**：`robustness_tests.py`、`generalization_test.py`、`validate_h15.py`
- **验证工具**：`verify_v4.py`、`verify_rsrs.py`、`verify_ic_lookahead.py`、`verify_a2_a3.py`
- **部署运维**：`package.sh`、`publish.sh`、`setup.sh`、`deployment_optimizer.py`

---

## 项目关键指标

| 指标 | 值 |
|------|:---:|
| Python 源文件数 | ~45+ |
| 总函数数 | 150+ |
| DB 迁移版本 | 8 |
| 单元测试方法 | ~90+ |
| ETF 覆盖 | 37 只（5 指数 + 32 行业） |
| 因子维度 | 6 |
| 最高频函数 | `execute()`（105+ 次调用） |
| 缓存机制 | 内存 LRU（强制）+ Redis（可选） |

---

## 部署架构

```
                         ┌─────────────┐
                         │   Nginx     │
                         │  (反代/SSL)  │
                         └──────┬──────┘
                                │
                         ┌──────▼──────┐
                         │   Uvicorn   │
                         │  FastAPI 应用 │
                         └──────┬──────┘
                                │
               ┌────────────────┼────────────────┐
               │                │                │
        ┌──────▼─────┐  ┌──────▼──────┐  ┌─────▼─────┐
        │ PostgreSQL  │  │   Redis     │  │  文件系统   │
        │   (主要存储)  │  │  (可选缓存)   │  │ (静态资源)  │
        └────────────┘  └─────────────┘  └───────────┘
```

---

## 开发与部署快速参考

```bash
# 安装依赖
pip install -r requirements.txt

# 数据库迁移
alembic upgrade head

# 启动开发服务器
uvicorn src.web.app:app --reload

# 运行测试
pytest tests/

# Docker 部署
docker-compose up -d
```

---

> 本文档基于项目源码结构分析生成，反映了截至 2026-06-13 的项目状态。