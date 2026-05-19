# ATMstockMarket 根目录文件索引

**更新日期:** 2026-05-04  
**版本:** v12.0.0

---

## 📄 根目录文件

| 文件 | 用途说明 |
|------|----------|
| `README.md` | 项目说明文档，包含功能介绍、技术栈、安装指南 |
| `pyproject.toml` | Python 项目配置文件，定义依赖、版本、构建信息 |
| `requirements.txt` | Python 依赖列表，用于 pip 安装 |
| `setup.py` | 项目安装脚本，支持 pip install 方式安装 |
| `scripts/setup.sh` | 项目初始化 Shell 脚本，一键配置开发环境 |
| `.gitignore` | Git 忽略规则，排除不需要版本控制的文件 |
| `.dockerignore` | Docker 构建忽略规则，排除不需要打包的文件 |
| `.env.example` | 环境变量配置模板，复制为 `.env` 使用 |
| `.pre-commit-config.yaml` | Git pre-commit 钩子配置，代码提交前自动检查 |
| `Dockerfile` | Docker 镜像构建文件，多阶段构建优化体积 |
| `docker-compose.yml` | Docker Compose 编排配置，简化容器部署 |
| `scripts/package.sh` | 项目打包脚本，生成发布包 |
| `scripts/publish.sh` | 项目发布脚本，自动化发布流程 |

---

## 📁 根目录文件夹

| 文件夹 | 用途说明 |
|--------|----------|
| `src/` | **源代码主目录**，包含核心业务逻辑、数据获取、Web 应用等模块 |
| `scripts/` | **工具脚本目录**，包含数据库初始化、数据检查、诊断修复等脚本 |
| `tests/` | **测试代码目录**，包含单元测试、测试配置等 |
| `utils/` | **通用工具目录**，包含辅助函数、验证器、序列化器等 |
| `config/` | **配置文件目录**，包含配置模板文件 |
| `data/` | **数据存储目录**，存放数据库文件、外部数据等 |
| `docs/` | **文档目录**，包含架构设计、开发文档、解决方案等 |
| `.github/` | **GitHub 配置目录**，包含 CI/CD 工作流等 |
| `.trae/` | **Trae IDE 配置目录**，包含项目相关的计划和文档 |

---

## 📊 文件统计

| 类型 | 数量 |
|------|------|
| 配置文件 | 7 个 |
| 脚本文件 | 2 个 |
| 文档文件 | 1 个 |
| 文件夹 | 9 个 |
| **根目录文件总数** | **13 个** |

---

## 🔗 相关文档

- 详细项目结构: [docs/development/PROJECT_STRUCTURE.md](docs/development/PROJECT_STRUCTURE.md)
- 项目说明: [README.md](README.md)
