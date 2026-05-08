# ATMstockMarket 文档目录

本目录包含项目的所有文档，按照类型进行分类组织。

## 📁 目录结构

```
docs/
├── architecture/        # 架构设计文档
│   ├── PostgreSQL-vs-DuckDB-Decision-Guide.md
│   └── React+FastAPI架构迁移方案.md
│
├── deployment/          # 部署相关文档
│   ├── POSTGRESQL_MIGRATION.md        # PostgreSQL迁移指南
│   └── MIGRATION_COMPLETE.md          # PostgreSQL迁移完成记录
│
├── development/         # 开发相关文档
│   ├── PROJECT_STRUCTURE.md           # 项目结构说明文档
│   ├── PROJECT_RESTRUCTURE_PLAN.md    # 项目重构方案
│   ├── ProjectStructure.md            # 项目结构详细分析
│   ├── DATA_UPDATE_WORKFLOW.md        # 数据更新工作流程
│   ├── FILE_INDEX.md                  # 根目录文件索引
│   └── QUICK_START_GUIDE.md           # 快速启动指南
│
└── solutions/           # 解决方案文档
    └── INDUSTRY_DATA_SOLUTION.md      # 行业数据解决方案
```

## 📖 文档说明

### architecture/ - 架构设计文档
包含系统架构设计、技术选型、架构迁移方案等文档。

- **PostgreSQL-vs-DuckDB-Decision-Guide.md** - PostgreSQL 与 DuckDB 技术选型决策指南
- **React+FastAPI架构迁移方案.md** - 前后端分离架构迁移方案

### deployment/ - 部署相关文档
包含部署指南、迁移文档、环境配置等文档。

- **POSTGRESQL_MIGRATION.md** - 从DuckDB迁移到PostgreSQL的详细步骤
- **MIGRATION_COMPLETE.md** - PostgreSQL迁移完成记录和改进说明

### development/ - 开发相关文档
包含项目结构说明、开发指南、重构方案等文档。

- **PROJECT_STRUCTURE.md** - 项目结构详细说明（推荐阅读）
- **PROJECT_RESTRUCTURE_PLAN.md** - v12.0 重构方案文档
- **ProjectStructure.md** - 项目结构详细分析，包含核心模块分析和架构图
- **DATA_UPDATE_WORKFLOW.md** - 数据更新工作流程文档
- **FILE_INDEX.md** - 根目录文件和文件夹索引说明
- **QUICK_START_GUIDE.md** - 快速启动指南

### solutions/ - 解决方案文档
包含特定问题的解决方案、技术方案等文档。

- **INDUSTRY_DATA_SOLUTION.md** - 行业数据问题解决方案

## 🔍 快速导航

### 新手入门
1. 阅读 [项目根目录的 README.md](../README.md) 了解项目概况
2. 阅读 [PROJECT_STRUCTURE.md](development/PROJECT_STRUCTURE.md) 了解项目结构
3. 查看 [QUICK_START_GUIDE.md](development/QUICK_START_GUIDE.md) 快速启动项目
4. 查看 [FILE_INDEX.md](development/FILE_INDEX.md) 了解根目录文件说明

### 架构设计
- 查看 [React+FastAPI架构迁移方案.md](architecture/React+FastAPI架构迁移方案.md) 了解架构演进
- 查看 [PostgreSQL-vs-DuckDB-Decision-Guide.md](architecture/PostgreSQL-vs-DuckDB-Decision-Guide.md) 了解数据库选型

### 部署运维
- 查看 [POSTGRESQL_MIGRATION.md](deployment/POSTGRESQL_MIGRATION.md) 了解数据库迁移
- 查看 [MIGRATION_COMPLETE.md](deployment/MIGRATION_COMPLETE.md) 查看迁移完成记录

### 问题解决
- 查看 [INDUSTRY_DATA_SOLUTION.md](solutions/INDUSTRY_DATA_SOLUTION.md) 了解行业数据问题

## 📝 文档维护

### 添加新文档
- 架构设计文档 → `architecture/`
- 部署运维文档 → `deployment/`
- 开发指南文档 → `development/`
- 解决方案文档 → `solutions/`

### 文档命名规范
- 使用大写字母和下划线：`PROJECT_STRUCTURE.md`
- 或使用中文命名：`React+FastAPI架构迁移方案.md`
- 文件名应清晰表达文档内容

### 文档更新
- 更新文档后，请同步更新本 README 文件
- 保持文档目录结构的清晰和一致

---

**最后更新**: 2026-05-05  
**维护者**: ATMstockMarket Team
