# ATMstockMarket 项目重构方案

## 一、重构目标

将项目从当前的扁平结构重构为标准的Python项目结构，提升代码可维护性、可测试性和可扩展性。

## 二、新目录结构设计

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
│   │   ├── tushare_fetcher.py    # Tushare数据获取（原fetch_data.py）
│   │   ├── akshare_fetcher.py    # AKShare数据获取
│   │   └── external_loader.py    # 外部数据加载（原load_allsymbol.py）
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
│       │   └── js/
│       └── templates/           # Jinja2模板
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
│   ├── generate_market_value_data.py  # 市值数据生成
│   ├── performance_test.py      # 性能测试
│   ├── migrate_to_duckdb.py     # 数据库迁移
│   └── sync_external_data.py    # 外部数据同步
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
└── PROJECT_STRUCTURE.md         # 本文档
```

## 三、模块职责说明

### 1. src/core/ - 核心基础模块

**职责**：提供项目的基础设施和核心功能

**模块**：
- `db_manager.py`：DuckDB数据库连接管理、查询优化、事务处理
- `trading_calendar.py`：交易日历查询、日期计算、数据新鲜度验证
- `config.py`：配置管理、环境变量、常量定义

**特点**：
- 无业务逻辑依赖
- 可被所有其他模块依赖
- 提供稳定的基础接口

### 2. src/data_fetchers/ - 数据获取模块

**职责**：从各种数据源获取金融数据

**模块**：
- `tushare_fetcher.py`：Tushare数据获取（股票、ETF、财务数据）
- `akshare_fetcher.py`：AKShare数据获取（龙虎榜等）
- `external_loader.py`：外部CSV数据加载（股票分类、行业标签）

**特点**：
- 依赖 `core` 模块
- 独立的数据源适配器
- 易于扩展新的数据源

### 3. src/analytics/ - 分析计算模块

**职责**：实现各种金融分析算法和模型

**模块**：
- `barra.py`：BARRA多因子模型（行业因子、动量因子、规模因子、风格因子）

**特点**：
- 依赖 `core` 模块
- 纯计算逻辑，无I/O操作
- 易于测试和维护

### 4. src/web/ - Web应用模块

**职责**：提供Web界面和RESTful API

**模块**：
- `app.py`：FastAPI应用、路由定义、API接口
- `static/`：CSS、JavaScript等静态资源
- `templates/`：Jinja2 HTML模板

**特点**：
- 依赖 `core`、`analytics` 模块
- 处理HTTP请求和响应
- 提供用户界面

### 5. scripts/ - 工具脚本

**职责**：运维工具、诊断脚本、初始化脚本

**模块**：
- 数据初始化：`init_database.py`
- 数据检查：`check_industry_api.py`、`check_industry_data.py`、`check_data.py`
- 问题诊断：`diagnose_industry.py`
- 数据修复：`fix_industry_data.py`
- 测试工具：`test_fixes.py`、`test_query.py`、`performance_test.py`
- 数据迁移：`migrate_to_duckdb.py`

**特点**：
- 命令行工具
- 独立可执行
- 运维和调试用途

### 6. tests/ - 测试模块

**职责**：单元测试、集成测试、端到端测试

**模块**：
- `test_core/`：核心模块测试
- `test_analytics/`：分析模块测试
- `test_web/`：Web API测试

**特点**：
- pytest测试框架
- 测试覆盖率报告
- CI/CD集成

### 7. utils/ - 工具函数

**职责**：通用工具函数和辅助功能

**模块**：
- `validators.py`：输入验证（股票代码、日期、行业名称）
- `serializers.py`：JSON序列化、数据转换
- `helpers.py`：通用辅助函数

**特点**：
- 无状态函数
- 高复用性
- 易于测试

## 四、文件迁移映射表

### 从根目录迁移到 scripts/

| 原文件 | 目标位置 | 说明 |
|--------|---------|------|
| `check_industry_api.py` | `scripts/check_industry_api.py` | 行业数据API检查 |
| `check_industry_data.py` | `scripts/check_industry_data.py` | 行业数据数据库检查 |
| `diagnose_industry.py` | `scripts/diagnose_industry.py` | 行业数据诊断 |
| `fix_industry_data.py` | `scripts/fix_industry_data.py` | 行业数据修复 |
| `test_fixes.py` | `scripts/test_fixes.py` | 修复测试 |

### 从 tushare-py/ 迁移到 src/

| 原文件 | 目标位置 | 说明 |
|--------|---------|------|
| `tushare-py/db_manager.py` | `src/core/db_manager.py` | 核心模块 |
| `tushare-py/trading_calendar.py` | `src/core/trading_calendar.py` | 核心模块 |
| `tushare-py/config.py.example` | `config/config.py.example` | 配置模板 |
| `tushare-py/fetch_data.py` | `src/data_fetchers/tushare_fetcher.py` | 数据获取 |
| `tushare-py/akshare_fetch.py` | `src/data_fetchers/akshare_fetcher.py` | 数据获取 |
| `tushare-py/load_allsymbol.py` | `src/data_fetchers/external_loader.py` | 数据加载 |
| `tushare-py/barra.py` | `src/analytics/barra.py` | 分析模块 |
| `tushare-py/init_database.py` | `scripts/init_database.py` | 工具脚本 |
| `tushare-py/check_data.py` | `scripts/check_data.py` | 工具脚本 |
| `tushare-py/check_dates.py` | `scripts/check_dates.py` | 工具脚本 |
| `tushare-py/test_query.py` | `scripts/test_query.py` | 工具脚本 |
| `tushare-py/generate_market_value_data.py` | `scripts/generate_market_value_data.py` | 工具脚本 |
| `tushare-py/performance_test.py` | `scripts/performance_test.py` | 工具脚本 |
| `tushare-py/migrate_to_duckdb.py` | `scripts/migrate_to_duckdb.py` | 工具脚本 |
| `tushare-py/sync_external_data.py` | `scripts/sync_external_data.py` | 工具脚本 |

### 从 web/ 迁移到 src/web/

| 原文件 | 目标位置 | 说明 |
|--------|---------|------|
| `web/app.py` | `src/web/app.py` | Web应用 |
| `web/static/` | `src/web/static/` | 静态资源 |
| `web/templates/` | `src/web/templates/` | 模板文件 |

### 数据目录迁移

| 原位置 | 目标位置 | 说明 |
|--------|---------|------|
| `tushare-py/external_data/` | `data/external/` | 外部数据 |
| `tushare-py/data/` | `data/database/` | 数据库文件 |

## 五、导入路径更新规则

### 更新规则

1. **核心模块导入**：
   - 原：`from tushare_py.db_manager import ...`
   - 新：`from src.core.db_manager import ...`

2. **数据获取模块导入**：
   - 原：`from tushare_py.fetch_data import ...`
   - 新：`from src.data_fetchers.tushare_fetcher import ...`

3. **分析模块导入**：
   - 原：`from tushare_py.barra import ...`
   - 新：`from src.analytics.barra import ...`

4. **Web模块导入**：
   - 原：`from web.app import ...`
   - 新：`from src.web.app import ...`

5. **工具函数导入**：
   - 原：无
   - 新：`from utils.validators import ...`

### 需要更新的文件清单

1. `src/web/app.py` - 更新所有导入路径
2. `src/data_fetchers/tushare_fetcher.py` - 更新核心模块导入
3. `src/data_fetchers/akshare_fetcher.py` - 更新核心模块导入
4. `src/data_fetchers/external_loader.py` - 更新核心模块导入
5. `src/analytics/barra.py` - 更新核心模块导入
6. `scripts/` 目录下所有脚本 - 更新导入路径

## 六、配置文件更新

### pyproject.toml

```toml
[project]
name = "atmstockmarket"
version = "12.0.0"
description = "A股市场分析工具"

[project.optional-dependencies]
dev = ["pytest", "pytest-cov", "black", "flake8"]

[tool.setuptools.packages.find]
where = ["."]
include = ["src*", "utils*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

### setup.py

```python
from setuptools import setup, find_packages

setup(
    name="atmstockmarket",
    version="12.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "fastapi>=0.100.0",
        "uvicorn>=0.22.0",
        "duckdb>=0.8.0",
        "pandas>=2.0.0",
        "tushare>=1.3.0",
        "akshare>=1.10.0",
        "jinja2>=3.1.0",
        "requests>=2.31.0",
    ],
)
```

## 七、重构步骤

### 阶段一：创建目录结构
1. 创建 `src/` 及其子目录
2. 创建 `scripts/` 目录
3. 创建 `tests/` 目录
4. 创建 `utils/` 目录
5. 创建 `data/` 目录
6. 创建 `config/` 目录

### 阶段二：迁移文件
1. 迁移核心模块到 `src/core/`
2. 迁移数据获取模块到 `src/data_fetchers/`
3. 迁移分析模块到 `src/analytics/`
4. 迁移Web应用到 `src/web/`
5. 迁移工具脚本到 `scripts/`
6. 迁移数据目录到 `data/`

### 阶段三：更新导入路径
1. 更新 `src/web/app.py` 的所有导入
2. 更新 `src/data_fetchers/` 模块的导入
3. 更新 `src/analytics/` 模块的导入
4. 更新 `scripts/` 目录下所有脚本的导入

### 阶段四：创建模块初始化文件
1. 创建所有 `__init__.py` 文件
2. 定义模块公共API
3. 设置模块级常量

### 阶段五：更新配置文件
1. 更新 `pyproject.toml`
2. 创建 `setup.py`
3. 更新 `.gitignore`

### 阶段六：验证和测试
1. 运行所有脚本验证功能
2. 启动Web服务验证API
3. 运行测试套件（如有）
4. 检查导入路径是否正确

## 八、命名规范

### 文件命名
- 模块文件：小写字母 + 下划线（如 `db_manager.py`）
- 测试文件：`test_` 前缀（如 `test_db_manager.py`）
- 脚本文件：小写字母 + 下划线（如 `init_database.py`）

### 目录命名
- 模块目录：小写字母 + 下划线（如 `data_fetchers`）
- 测试目录：`test_` 前缀（如 `test_core`）

### Python包命名
- 包名：小写字母 + 下划线
- 避免使用连字符

## 九、优势与收益

### 1. 可维护性提升
- 清晰的模块边界
- 单一职责原则
- 易于定位代码

### 2. 可测试性提升
- 模块独立测试
- Mock依赖更容易
- 测试覆盖率提升

### 3. 可扩展性提升
- 易于添加新模块
- 数据源扩展简单
- 分析模型扩展方便

### 4. 协作效率提升
- 清晰的项目结构
- 标准的Python布局
- 降低学习成本

### 5. 部署便利性提升
- 标准的包管理
- 依赖管理清晰
- 环境配置简单

## 十、风险与注意事项

### 风险
1. **导入路径变更**：可能影响现有代码
2. **配置文件路径**：需要更新配置文件路径
3. **数据文件路径**：数据库和外部数据路径变更

### 缓解措施
1. **渐进式重构**：分阶段进行，每阶段验证
2. **保留兼容性**：创建兼容性导入（可选）
3. **充分测试**：每个阶段进行功能验证
4. **文档更新**：及时更新所有文档

## 十一、后续优化建议

### 短期（1-2周）
1. 添加单元测试
2. 完善API文档
3. 添加类型注解

### 中期（1-2月）
1. 实现CI/CD流程
2. 添加代码质量检查
3. 性能优化

### 长期（3-6月）
1. 微服务化改造
2. 容器化部署
3. 监控告警系统

---

**文档版本**：v1.0  
**创建时间**：2026-05-04  
**适用版本**：ATMstockMarket v12.0
