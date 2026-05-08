# ATMstockMarket 项目结构说明文档

## 项目版本
**v12.0** - 2026-05-04 重构版本

## 项目概述

ATMstockMarket 是一个A股市场分析工具，基于 Tushare + AKShare 数据源，使用 FastAPI + ECharts 构建的全栈股票分析 Web 应用。

### 核心功能
- 指数ETF和行业ETF分析
- 个股查询与排行
- BARRA多因子分析
- 行业与概念板块分析
- 龙虎榜数据展示

### 技术栈
- **后端**: Python 3.9+, FastAPI, DuckDB
- **前端**: Jinja2, Tailwind CSS, ECharts 5
- **数据源**: Tushare Pro, AKShare

---

## 目录结构

```
ATMstockMarket/
├── src/                           # 源代码主目录
│   ├── __init__.py
│   │
│   ├── core/                      # 核心基础模块
│   │   ├── __init__.py
│   │   ├── db_manager.py         # 数据库连接管理器
│   │   ├── trading_calendar.py   # 交易日历工具
│   │   └── config.py             # 配置管理
│   │
│   ├── data_fetchers/            # 数据获取模块
│   │   ├── __init__.py
│   │   ├── tushare_fetcher.py    # Tushare数据获取
│   │   ├── akshare_fetcher.py    # AKShare数据获取
│   │   └── external_loader.py    # 外部数据加载
│   │
│   ├── analytics/                # 分析计算模块
│   │   ├── __init__.py
│   │   └── barra.py             # BARRA多因子分析
│   │
│   └── web/                      # Web应用模块
│       ├── __init__.py
│       ├── app.py               # FastAPI主应用
│       ├── static/              # 静态资源
│       │   ├── css/
│       │   │   ├── tokens.css
│       │   │   ├── style.css
│       │   │   └── components.css
│       │   └── js/
│       │       ├── chart-loader.js
│       │       ├── nav.js
│       │       ├── cache.js
│       │       ├── theme.js
│       │       ├── utils.js
│       │       ├── perf.js
│       │       └── tailwind-config.js
│       └── templates/           # Jinja2模板
│           ├── index.html
│           ├── etf.html
│           ├── sector.html
│           ├── stocks.html
│           ├── stock_detail.html
│           ├── barra.html
│           ├── concept.html
│           └── industry.html
│
├── scripts/                      # 工具脚本目录
│   ├── __init__.py
│   ├── init_database.py         # 数据库初始化脚本
│   ├── check_industry_api.py    # 行业数据API检查
│   ├── check_industry_data.py   # 行业数据数据库检查
│   ├── diagnose_industry.py     # 行业数据诊断
│   ├── fix_industry_data.py     # 行业数据修复
│   ├── test_fixes.py            # 修复测试
│   ├── check_data.py            # 数据检查工具
│   ├── check_dates.py           # 日期检查工具
│   ├── test_query.py            # 查询测试工具
│   ├── generate_market_value_data.py
│   ├── performance_test.py
│   ├── migrate_to_duckdb.py
│   └── sync_external_data.py
│
├── tests/                        # 测试模块
│   ├── __init__.py
│   ├── test_core/               # 核心模块测试
│   │   ├── __init__.py
│   │   ├── test_db_manager.py
│   │   └── test_trading_calendar.py
│   ├── test_analytics/          # 分析模块测试
│   │   ├── __init__.py
│   │   └── test_barra.py
│   └── test_web/                # Web模块测试
│       ├── __init__.py
│       └── test_api.py
│
├── utils/                        # 工具函数模块
│   ├── __init__.py
│   ├── validators.py            # 输入验证工具
│   ├── serializers.py           # 序列化工具
│   └── helpers.py               # 通用辅助函数
│
├── data/                         # 数据目录
│   ├── external/                # 外部数据
│   │   ├── ALLSYMBOL.meta.json
│   │   └── README.md
│   └── database/                # 数据库文件
│       └── analysis.duckdb
│
├── docs/                         # 文档目录
│   ├── api/                     # API文档
│   ├── development/             # 开发文档
│   └── deployment/              # 部署文档
│
├── config/                       # 配置文件目录
│   ├── config.py.example        # 配置模板
│   └── logging.conf             # 日志配置
│
├── .gitignore
├── README.md
├── requirements.txt
├── pyproject.toml
├── setup.py                     # 安装配置
├── PROJECT_STRUCTURE.md         # 本文档
└── PROJECT_RESTRUCTURE_PLAN.md  # 重构方案文档
```

---

## 模块说明

### 1. src/core/ - 核心基础模块

**职责**: 提供项目的基础设施和核心功能

#### db_manager.py
- **功能**: DuckDB数据库连接管理、查询优化、事务处理
- **核心类**: `DuckDBConnectionManager`
- **核心函数**:
  - `init_db_manager(db_path)` - 初始化管理器
  - `get_db_manager()` - 获取管理器实例
  - `get_conn()` - 获取连接（兼容旧代码）
  - `query(sql, params)` - 执行查询

#### trading_calendar.py
- **功能**: 交易日历查询、日期计算、数据新鲜度验证
- **核心函数**:
  - `now_beijing()` - 获取北京时间
  - `get_latest_trading_date()` - 获取最新交易日
  - `get_open_trade_dates()` - 获取交易日列表
  - `is_fresh(table)` - 检查数据是否最新
  - `get_dates_to_fetch(table)` - 获取需补拉的日期

#### config.py
- **功能**: 配置管理、环境变量、常量定义
- **配置项**:
  - `TUSHARE_TOKEN` - Tushare API Token
  - `DB_PATH` - 数据库路径
  - `INDEX_ETF` - 指数ETF代码
  - `SECTOR_ETF` - 行业ETF代码
  - `LOOKBACK_DAYS` - 回溯天数
  - `ANOMALY_STD_THRESHOLD` - 异常检测阈值

**特点**:
- 无业务逻辑依赖
- 可被所有其他模块依赖
- 提供稳定的基础接口

---

### 2. src/data_fetchers/ - 数据获取模块

**职责**: 从各种数据源获取金融数据

#### tushare_fetcher.py
- **功能**: Tushare数据获取（股票、ETF、财务数据）
- **核心函数**:
  - `init_db()` - 初始化数据库表结构
  - `fetch_index_etf()` - 获取指数ETF数据
  - `fetch_sector_etf()` - 获取行业ETF数据
  - `fetch_stock_list()` - 获取股票列表
  - `fetch_stock_daily()` - 获取个股日线
  - `fetch_daily_basic()` - 获取每日估值
  - `fetch_fina_indicator()` - 获取财务指标

#### akshare_fetcher.py
- **功能**: AKShare数据获取（龙虎榜等）
- **核心函数**:
  - `fetch_lhb()` - 获取龙虎榜数据

#### external_loader.py
- **功能**: 外部CSV数据加载（股票分类、行业标签）
- **核心函数**:
  - `load_csv_data()` - 加载CSV数据
  - `extract_and_load_data()` - 提取并加载数据

**特点**:
- 依赖 `core` 模块
- 独立的数据源适配器
- 易于扩展新的数据源

---

### 3. src/analytics/ - 分析计算模块

**职责**: 实现各种金融分析算法和模型

#### barra.py
- **功能**: BARRA多因子模型
- **核心函数**:
  - `calc_industry_factors()` - 计算行业因子
  - `calc_momentum_factors()` - 计算动量因子
  - `calc_size_factors()` - 计算规模因子
  - `calc_style_factors()` - 计算风格因子
  - `calc_barra_summary()` - 计算汇总结果

**特点**:
- 依赖 `core` 模块
- 纯计算逻辑，无I/O操作
- 易于测试和维护

---

### 4. src/web/ - Web应用模块

**职责**: 提供Web界面和RESTful API

#### app.py
- **功能**: FastAPI应用、路由定义、API接口
- **页面路由**:
  - `/` - 首页概览
  - `/etf` - 指数ETF分析
  - `/sector` - 行业ETF分析
  - `/stocks` - 个股排行
  - `/stock/{ts_code}` - 个股详情
  - `/barra` - BARRA因子分析
  - `/concept` - 概念分析
  - `/industry` - 行业分析

- **API接口**:
  - `GET /api/overview` - 获取首页概览数据
  - `GET /api/index-etf/{ts_code}` - 获取指数ETF详情
  - `GET /api/sector-etf` - 获取所有行业ETF
  - `GET /api/stocks/volatility` - 波动率排行
  - `GET /api/stocks/gainers` - 涨跌幅排行
  - `GET /api/stocks/fundamental` - 基本面选股
  - `GET /api/stock/{ts_code}` - 个股详情
  - `GET /api/barra/summary` - BARRA汇总
  - `GET /api/concept/analysis` - 概念分析
  - `GET /api/industry/analysis` - 行业分析

**特点**:
- 依赖 `core`、`analytics` 模块
- 处理HTTP请求和响应
- 提供用户界面

---

### 5. scripts/ - 工具脚本

**职责**: 运维工具、诊断脚本、初始化脚本

#### init_database.py
- **功能**: 数据库一键初始化脚本
- **用途**: 首次部署或数据库重置

#### check_industry_api.py
- **功能**: 通过HTTP API检查行业分析数据的完整性
- **用途**: Web服务运行时验证数据

#### check_industry_data.py
- **功能**: 直接检查DuckDB数据库中行业分析相关数据的完整性
- **用途**: 数据库维护和问题诊断

#### diagnose_industry.py
- **功能**: 诊断行业数据问题，提供详细的诊断步骤和解决方案
- **用途**: 深度诊断行业数据问题

#### fix_industry_data.py
- **功能**: 快速修复行业数据问题的自动化脚本
- **用途**: 一键修复行业数据问题

#### test_fixes.py
- **功能**: 测试输入验证、线程安全缓存、JSON序列化等修复效果
- **用途**: 系统修复后的验证测试

**特点**:
- 命令行工具
- 独立可执行
- 运维和调试用途

---

### 6. tests/ - 测试模块

**职责**: 单元测试、集成测试、端到端测试

#### test_core/
- `test_db_manager.py` - 数据库管理器测试
- `test_trading_calendar.py` - 交易日历测试

#### test_analytics/
- `test_barra.py` - BARRA因子分析测试

#### test_web/
- `test_api.py` - Web API测试

**特点**:
- pytest测试框架
- 测试覆盖率报告
- CI/CD集成

---

### 7. utils/ - 工具函数

**职责**: 通用工具函数和辅助功能

#### validators.py
- **功能**: 输入验证（股票代码、日期、行业名称）
- **核心函数**:
  - `validate_ts_code()` - 验证股票代码格式
  - `validate_date()` - 验证日期格式
  - `validate_industry_name()` - 验证行业名称（防SQL注入）

#### serializers.py
- **功能**: JSON序列化、数据转换
- **核心函数**:
  - `safe_json()` - 安全的JSON序列化，处理 NaN、inf 等特殊值
  - `safe_json_dumps()` - 安全的JSON序列化为字符串

#### helpers.py
- **功能**: 通用辅助函数
- **核心函数**:
  - `get_project_root()` - 获取项目根目录
  - `ensure_dir()` - 确保目录存在
  - `format_number()` - 格式化数字（添加千分位、单位）
  - `format_percent()` - 格式化百分比

**特点**:
- 无状态函数
- 高复用性
- 易于测试

---

## 数据流架构

```
┌──────────────┐
│  外部数据源   │
│ - Tushare    │
│ - AKShare    │
│ - CSV文件    │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ data_fetchers│
│  数据获取模块 │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│    core      │
│  数据库管理   │
│  DuckDB      │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  analytics   │
│  分析计算模块 │
│ - BARRA      │
│ - 个股分析   │
│ - ETF分析    │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│     web      │
│  Web应用模块  │
│ - FastAPI    │
│ - REST API   │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   前端展示    │
│ - ECharts    │
│ - Tailwind   │
└──────────────┘
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -e .
```

### 2. 配置 Tushare Token

```bash
export TUSHARE_TOKEN="你的Token"
```

或编辑 `src/core/config.py` 直接配置。

### 3. 初始化数据库

```bash
python scripts/init_database.py
```

### 4. 启动Web服务

```bash
cd src/web
uvicorn app:app --reload --port 8000
```

或使用命令：

```bash
atm-web
```

### 5. 访问应用

浏览器打开 http://localhost:8000

---

## 开发指南

### 添加新的数据源

1. 在 `src/data_fetchers/` 创建新的获取器模块
2. 继承或参考现有的获取器实现
3. 在 `src/data_fetchers/__init__.py` 中导出

### 添加新的分析模块

1. 在 `src/analytics/` 创建新的分析模块
2. 实现分析逻辑
3. 在 `src/analytics/__init__.py` 中导出
4. 在 `src/web/app.py` 中添加API接口

### 添加新的API接口

1. 在 `src/web/app.py` 中添加路由函数
2. 使用 `@app.get()` 或 `@app.post()` 装饰器
3. 实现数据查询和处理逻辑
4. 使用 `safe_json()` 返回JSON响应

### 运行测试

```bash
pytest tests/
```

### 代码风格

```bash
black src/ tests/ utils/ scripts/
flake8 src/ tests/ utils/ scripts/
```

---

## 部署架构

```
┌─────────────────────────────────────────┐
│            生产环境部署                  │
├─────────────────────────────────────────┤
│                                          │
│  ┌──────────────┐    ┌──────────────┐  │
│  │   Nginx      │    │   SSL证书    │  │
│  │  反向代理    │◄───┤   HTTPS      │  │
│  └──────┬───────┘    └──────────────┘  │
│         │                                │
│         ▼                                │
│  ┌──────────────┐                        │
│  │   Uvicorn    │                        │
│  │  ASGI服务器  │                        │
│  │  (多进程)    │                        │
│  └──────┬───────┘                        │
│         │                                │
│         ▼                                │
│  ┌──────────────┐                        │
│  │  FastAPI     │                        │
│  │  Web应用     │                        │
│  └──────┬───────┘                        │
│         │                                │
│         ▼                                │
│  ┌──────────────┐                        │
│  │   DuckDB     │                        │
│  │  数据库文件  │                        │
│  └──────────────┘                        │
│                                          │
└─────────────────────────────────────────┘
```

---

## 性能优化

### 数据库优化
- DuckDB列式存储，适合分析查询
- 向量化执行，提升查询性能
- 线程本地连接，避免锁竞争
- UPSERT语义，简化数据更新

### 缓存策略
- 内存缓存：`ThreadSafeCache`（线程安全）
- 数据库缓存：`precomputed_cache` 表
- HTTP缓存：`Cache-Control` 头

### 索引策略
- 主键索引：`(ts_code, trade_date)`
- 单列索引：`ts_code`, `trade_date`, `industry`
- 复合索引：`(trade_date, ts_code)`

---

## 常见问题

### Q: 如何更新数据？
A: 运行 `python scripts/init_database.py` 或访问 Web 界面的数据管理页面。

### Q: 如何添加新的ETF？
A: 编辑 `src/core/config.py`，在 `INDEX_ETF` 或 `SECTOR_ETF` 字典中添加。

### Q: 如何修改数据库路径？
A: 编辑 `src/core/config.py` 中的 `DB_PATH` 变量。

### Q: 如何运行测试？
A: 运行 `pytest tests/` 命令。

### Q: 如何贡献代码？
A: 
1. Fork 项目
2. 创建特性分支
3. 提交代码
4. 创建 Pull Request

---

## 更新日志

### v12.0 (2026-05-04)
- 🎉 完成项目结构重构
- 📁 采用标准Python项目布局
- 🔧 更新所有导入路径
- 📦 创建模块化的包结构
- 🛠️ 添加工具函数模块
- 📝 完善项目文档

### v11.1
- 优化数据库性能
- 添加BARRA因子分析
- 改进缓存策略

---

## 许可证

MIT License

---

## 联系方式

- 项目主页: https://github.com/yourusername/ATMstockMarket
- 问题反馈: https://github.com/yourusername/ATMstockMarket/issues

---

**文档版本**: v1.0  
**最后更新**: 2026-05-04  
**维护者**: ATMstockMarket Team
