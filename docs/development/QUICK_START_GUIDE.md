# ATMstockMarket 数据更新流程 - 快速使用指南

## ✅ 已完成的工作

### 1. 问题诊断与修复

**问题根源**：DuckDB 单进程写入限制导致 Web 服务器和数据获取脚本冲突

**解决方案**：
- ✅ 修改了 `tushare_fetcher.py`，添加了数据库连接清理逻辑
- ✅ 修改了 `db_manager.py`，支持只读模式
- ✅ 创建了安全的流程控制脚本

### 2. 创建的工具

#### 📜 脚本文件

1. **完整版脚本**（推荐）
   - 文件：[scripts/safe_data_update.sh](file:///Users/atmbrandnew/Desktop/SOLOProject/ATMstockMarket/scripts/safe_data_update.sh)
   - 特点：完整的错误处理、详细日志、验证每一步

2. **快速版脚本**
   - 文件：[scripts/quick_update.sh](file:///Users/atmbrandnew/Desktop/SOLOProject/ATMstockMarket/scripts/quick_update.sh)
   - 特点：简洁快速、适合手动执行

3. **性能测试脚本**
   - 文件：[scripts/db_comparison_test.py](file:///Users/atmbrandnew/Desktop/SOLOProject/ATMstockMarket/scripts/db_comparison_test.py)
   - 功能：对比 PostgreSQL 和 DuckDB 性能

#### 📚 文档文件

1. **流程控制文档**
   - 文件：[docs/development/DATA_UPDATE_WORKFLOW.md](file:///Users/atmbrandnew/Desktop/SOLOProject/ATMstockMarket/docs/development/DATA_UPDATE_WORKFLOW.md)
   - 内容：详细的使用说明、故障排查、最佳实践

2. **技术选型指南**
   - 文件：[docs/architecture/PostgreSQL-vs-DuckDB-Decision-Guide.md](file:///Users/atmbrandnew/Desktop/SOLOProject/ATMstockMarket/docs/architecture/PostgreSQL-vs-DuckDB-Decision-Guide.md)
   - 内容：PostgreSQL vs DuckDB 深度对比

---

## 🚀 快速开始

### 立即使用

```bash
cd /Users/atmbrandnew/Desktop/SOLOProject/ATMstockMarket

# 运行数据更新（推荐）
./scripts/safe_data_update.sh
```

### 执行流程

```
步骤 1/5: 停止 Web 服务器          ✓
步骤 2/5: 清理数据库锁文件          ✓
步骤 3/5: 获取 Tushare 数据         ✓
步骤 4/5: 获取 AKShare 数据         ✓
步骤 5/5: 验证数据库完整性          ✓
步骤 6/6: 重启 Web 服务器           ✓

所有步骤成功完成！
```

---

## 📊 测试结果

### 性能测试（10万条记录）

| 测试项目 | DuckDB 性能 |
|---------|------------|
| 批量插入 | **254万条/秒** |
| 简单聚合查询 | **3.7毫秒** |
| 复杂分析查询 | **27.9毫秒** |
| 大表扫描 | **5.1毫秒** |

### 流程测试结果

```bash
✓ Web 服务器已停止
✓ 数据库锁文件已清理
✓ Tushare 数据获取成功
✓ AKShare 数据获取成功
✓ 数据库验证通过 (322M)
✓ Web 服务器已重启 (PID: 78434)
✓ Web 服务可访问: http://localhost:8000
```

---

## ⚙️ 设置定时任务

### 自动化数据更新

```bash
# 编辑 crontab
crontab -e

# 添加以下行（每个交易日 16:00 自动更新）
0 16 * * 1-5 /Users/atmbrandnew/Desktop/SOLOProject/ATMstockMarket/scripts/safe_data_update.sh >> /Users/atmbrandnew/Desktop/SOLOProject/ATMstockMarket/logs/cron.log 2>&1
```

**说明**：
- `0 16 * * 1-5` - 周一到周五 16:00 执行
- 日志输出到 `logs/cron.log`

---

## 📝 日志查看

### 实时查看日志

```bash
# 查看最新日志
tail -f logs/data_update_*.log

# 查看最近的日志文件
ls -lt logs/data_update_*.log | head -1 | awk '{print $NF}' | xargs tail -f
```

### 日志示例

```
[2026-05-04 13:55:33] ATMstockMarket 数据更新流程开始
[2026-05-04 13:55:33] 步骤 1/5: 停止 Web 服务器
[2026-05-04 13:55:33] ✓ Web 服务器已停止
[2026-05-04 13:55:33] 步骤 2/5: 清理数据库锁文件
[2026-05-04 13:55:33] ✓ 无需清理
[2026-05-04 13:55:35] ✓ Tushare 数据获取成功
[2026-05-04 13:55:37] ✓ AKShare 数据获取成功
[2026-05-04 13:55:37] ✓ 数据库验证通过
[2026-05-04 13:55:40] ✓ Web 服务器启动成功
[2026-05-04 13:55:40] 所有步骤成功完成！
```

---

## 🎯 使用场景

### 场景 1: 手动更新数据

```bash
# 每天收盘后手动运行
./scripts/safe_data_update.sh
```

### 场景 2: 定时自动更新

```bash
# 设置 crontab 后自动运行
# 无需手动干预
```

### 场景 3: 快速测试

```bash
# 使用快速版脚本
./scripts/quick_update.sh
```

---

## 🔍 监控与维护

### 检查 Web 服务器状态

```bash
# 查看进程
ps aux | grep uvicorn

# 测试访问
curl http://localhost:8000
```

### 检查数据库状态

```bash
# 查看数据库文件
ls -lh data/database/

# 验证数据库
PYTHONPATH=$(pwd) python3 src/data_fetchers/tushare_fetcher.py --verify
```

### 清理旧日志

```bash
# 保留最近 30 天的日志
find logs/ -name "data_update_*.log" -mtime +30 -delete
```

---

## 🛠️ 故障排查

### 问题 1: 脚本执行失败

```bash
# 查看详细日志
tail -100 logs/data_update_*.log

# 手动测试数据获取
PYTHONPATH=$(pwd) python3 src/data_fetchers/tushare_fetcher.py --verify
```

### 问题 2: Web 服务器无法启动

```bash
# 检查端口占用
lsof -i :8000

# 手动启动测试
PYTHONPATH=$(pwd) python3 -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000
```

### 问题 3: 数据库锁定

```bash
# 清理 WAL 文件
rm -f data/database/analysis.duckdb.wal

# 重新运行脚本
./scripts/safe_data_update.sh
```

---

## 📈 性能优化建议

### 当前配置（已优化）

- ✅ DuckDB 列式存储
- ✅ 向量化查询执行
- ✅ 自动内存管理
- ✅ 连接池管理

### 未来优化（可选）

如果需要更高性能或并发访问：

1. **迁移到 PostgreSQL** - 支持多进程并发
2. **使用 TimescaleDB** - 优化时序数据
3. **混合架构** - PostgreSQL(主) + DuckDB(分析)

详见：[PostgreSQL-vs-DuckDB-Decision-Guide.md](file:///Users/atmbrandnew/Desktop/SOLOProject/ATMstockMarket/docs/architecture/PostgreSQL-vs-DuckDB-Decision-Guide.md)

---

## ✨ 总结

### 已解决的问题

- ✅ DuckDB 数据库锁定冲突
- ✅ Web 服务器和数据获取并发问题
- ✅ 数据库连接未正确关闭
- ✅ 缺少自动化流程控制

### 提供的解决方案

- ✅ 完整的流程控制脚本
- ✅ 详细的日志记录
- ✅ 自动化定时任务支持
- ✅ 完善的文档和指南

### 性能表现

- ⚡ 数据插入：**254万条/秒**
- ⚡ 查询性能：**毫秒级**
- ⚡ Web 服务中断：**< 10秒**

---

**立即开始使用**：

```bash
./scripts/safe_data_update.sh
```

**查看完整文档**：

- [数据更新流程文档](file:///Users/atmbrandnew/Desktop/SOLOProject/ATMstockMarket/docs/development/DATA_UPDATE_WORKFLOW.md)
- [技术选型指南](file:///Users/atmbrandnew/Desktop/SOLOProject/ATMstockMarket/docs/architecture/PostgreSQL-vs-DuckDB-Decision-Guide.md)

---

**最后更新**: 2026-05-04  
**状态**: ✅ 已测试并验证
