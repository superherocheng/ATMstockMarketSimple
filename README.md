# ATMstockMarketSimple 📈

<div align="center">

![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14%2B-336791?logo=postgresql&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

**A股量化分析平台 | Chinese A-Share Quantitative Analysis Platform**

[功能特性](#功能特性) • [快速开始](#快速开始) • [API文档](#api-端点) • [部署](#docker-部署)

</div>

---

## 📖 项目简介

ATMstockMarketSimple 是一个专注于中国A股市场的量化分析平台，提供ETF指数跟踪、行业轮动可视化、异常检测等功能。采用 **FastAPI + PostgreSQL + Redis** 架构，前端使用 **Jinja2 + Tailwind CSS + ECharts 5**，实现高性能数据展示。

> **简化版特性**：移除了React SPA、BARRA分析、AKShare数据源等冗余模块，保留核心功能，代码更简洁、部署更轻松。

## ✨ 功能特性

- 🎯 **指数ETF监控** - 实时追踪沪深300、中证500、上证50、中证1000、科创50等核心指数
- 📊 **行业轮动分析** - 可视化行业ETF资金流向，发现板块轮动机会
- 📈 **K线图表展示** - 基于ECharts 5的专业K线图，支持多维度数据分析
- 🔍 **异常检测** - 自动识别ETF份额异常变动，捕捉市场信号
- 🚀 **高性能缓存** - Redis + 内存LRU两级缓存，响应速度提升10倍
- 🐳 **容器化部署** - 完整的Docker支持，一键部署到生产环境

## 🛠️ 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **后端** | Python 3.9+ · FastAPI · Uvicorn | 高性能异步Web框架 |
| **数据库** | PostgreSQL · SQLAlchemy | 关系型数据库 + ORM |
| **缓存** | Redis (主) + 内存LRU (回退) | 两级缓存策略 |
| **前端** | Jinja2 · Tailwind CSS · vanilla JS | 服务端渲染 + 现代CSS |
| **可视化** | ECharts 5 (bundled) | 无需CDN，离线可用 |
| **数据源** | Tushare Pro | 专业金融数据接口 |

## 📁 项目结构

```
ATMstockMarketSimple/
├── src/
│   ├── web/                    # FastAPI Web应用
│   │   ├── app.py                      # 应用入口 (端口 8500)
│   │   ├── routers/                    # API路由模块
│   │   │   ├── overview.py             # 首页/仪表盘
│   │   │   ├── etf.py                  # ETF详情、行业ETF
│   │   │   └── fetch.py                # 数据获取端点
│   │   ├── templates/                  # Jinja2 HTML模板
│   │   │   ├── index.html              # 首页
│   │   │   ├── etf.html                # 指数ETF K线/异常
│   │   │   └── sector.html             # 行业ETF轮动
│   │   ├── static/                     # 静态资源
│   │   │   ├── css/app.css             # 样式文件
│   │   │   ├── js/app.js               # 应用JS
│   │   │   ├── js/vendor.js            # ECharts 5 (bundled)
│   │   │   └── favicon.svg
│   │   └── services/
│   │       └── cache.py                # Redis + 内存LRU缓存
│   ├── core/                           # 数据库管理、交易日历
│   ├── data_fetchers/                  # Tushare数据获取
│   └── __init__.py
├── config/                             # ETF定义、阈值配置
├── tests/                              # 单元测试
├── docs/                               # 架构与部署文档
├── data/                               # 本地数据缓存
├── alembic/                            # 数据库迁移
├── pyproject.toml                      # 项目配置
├── requirements.txt                    # 依赖列表
├── Dockerfile                          # Docker镜像
├── docker-compose.yml                  # Docker编排
└── .env.example                        # 环境变量示例
```

## 🚀 快速开始

### 环境要求

- Python 3.9+
- PostgreSQL 14+
- Redis (可选，自动回退到内存缓存)
- Tushare Pro Token ([获取地址](https://tushare.pro/))

### 本地安装

```bash
# 1. 克隆仓库
git clone https://github.com/yourusername/ATMstockMarketSimple.git
cd ATMstockMarketSimple

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填写以下配置：
# - DATABASE_URL=postgresql://user:password@localhost:5432/atmstock
# - TUSHARE_TOKEN=your_tushare_token
# - REDIS_HOST=localhost (可选)
# - REDIS_PORT=6379 (可选)

# 5. 初始化数据库
python -c "from src.core.db_manager_postgresql import _ensure_db; _ensure_db()"

# 6. 运行数据库迁移
alembic upgrade head

# 7. 启动应用
cd src/web && python app.py
# 访问 http://localhost:8500
```

### Docker 部署

```bash
# 使用 Docker Compose 一键启动
docker compose up -d

# 查看日志
docker compose logs -f

# 停止服务
docker compose down
```

## 📊 路由 & 页面

| 路由 | 页面 | 功能描述 |
|------|------|----------|
| `/` | index.html | 首页 — 指数ETF行情、行业热力图、数据管理 |
| `/etf` | etf.html | 指数ETF详情 — K线走势、份额分析、异常检测 |
| `/sector` | sector.html | 行业ETF轮动 — 横向对比、份额趋势、资金流向矩阵 |

## 🎯 监控ETF列表

| ETF代码 | 名称 | 类型 | 说明 |
|---------|------|------|------|
| 510300.SH | 沪深300ETF | 大盘蓝筹 | A股核心资产代表 |
| 510500.SH | 中证500ETF | 中盘成长 | 中盘股风向标 |
| 510050.SH | 上证50ETF | 超大盘 | 蓝筹中的蓝筹 |
| 512100.SH | 中证1000ETF | 小盘成长 | 小盘股代表 |
| 588000.SH | 科创50ETF | 科创板 | 科技创新龙头 |

## 🔌 API 端点

### 数据查询

| 方法 | 路由 | 描述 | 缓存 |
|------|------|------|------|
| GET | `/api/overview` | 首页概览（指数ETF + 行业摘要） | 5分钟 |
| GET | `/api/heatmap` | 行业板块热力图 | - |
| GET | `/api/data-range` | 各数据表状态与日期范围 | 5分钟 |
| GET | `/api/index-etf/{code}` | 单只指数ETF完整数据（K线+份额+异常） | - |
| GET | `/api/sector-etf` | 全部行业ETF数据 | - |
| GET | `/api/sector-etf/{code}` | 单只行业ETF数据 | - |
| GET | `/api/sector-cards` | 行业ETF卡片摘要 | - |

### 数据管理

| 方法 | 路由 | 描述 |
|------|------|------|
| POST | `/api/fetch/all` | 全量数据获取 |
| POST | `/api/fetch/tushare` | Tushare数据获取 |
| GET | `/api/fetch/status` | 数据获取任务状态轮询 |
| GET | `/api/analysis/validate` | 数据完整性校验 |
| GET | `/health` | 健康检查 |

## ⚡ 缓存策略

平台采用 **Redis + 内存LRU** 两级缓存架构：

```
┌─────────────┐
│   Request   │
└──────┬──────┘
       │
       ▼
┌─────────────┐     Hit     ┌──────────┐
│    Redis    │────────────▶│ Response │
└──────┬──────┘              └──────────┘
       │ Miss
       ▼
┌─────────────┐     Hit     ┌──────────┐
│  Memory LRU │────────────▶│ Response │
└──────┬──────┘              └──────────┘
       │ Miss
       ▼
┌─────────────┐
│  Database   │
└─────────────┘
```

- **Redis**: 主缓存层，支持应用重启后缓存预热
- **内存LRU**: 当Redis不可用时自动回退，避免单点故障
- **缓存分类**: `overview`（首页）、`etf`（ETF详情）、`sector`（行业）
- **缓存时长**: 数据范围接口缓存5分钟，避免频繁查询数据库

## 🧪 测试

```bash
# 运行所有测试
pytest

# 运行测试并生成覆盖率报告
pytest --cov=src --cov-report=html

# 运行特定测试文件
pytest tests/unit/test_cache.py -v
```

## 📝 开发指南

### 代码规范

项目使用以下工具保证代码质量：

- **Black**: 代码格式化
- **isort**: import排序
- **flake8**: 代码风格检查
- **mypy**: 类型检查
- **pre-commit**: Git提交前自动检查

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 安装pre-commit钩子
pre-commit install

# 手动运行所有检查
pre-commit run --all-files
```

### 数据库迁移

```bash
# 创建新迁移
alembic revision --autogenerate -m "description"

# 应用迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1
```

## 📚 文档

- [项目结构文档](docs/development/PROJECT_STRUCTURE.md)
- [快速开始指南](docs/development/QUICK_START_GUIDE.md)
- [VPS部署指南](docs/deployment/VPS_DEPLOY.md)
- [PostgreSQL迁移文档](docs/deployment/POSTGRESQL_MIGRATION.md)
- [数据更新工作流](docs/development/DATA_UPDATE_WORKFLOW.md)

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

**免责声明**: 本项目仅供学习和研究使用，不构成任何投资建议。投资有风险，入市需谨慎。

## 📧 联系方式

- 项目主页: [https://github.com/yourusername/ATMstockMarketSimple](https://github.com/yourusername/ATMstockMarketSimple)
- 问题反馈: [Issues](https://github.com/yourusername/ATMstockMarketSimple/issues)

---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给一个 Star ⭐**

Made with ❤️ by ATMstockMarket Team

</div>
