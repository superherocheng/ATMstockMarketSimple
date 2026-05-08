# ATMstockMarket 数据更新流程控制

## 📋 概述

为了解决 DuckDB 单进程写入限制导致的并发冲突问题，我们提供了两个数据更新脚本：

1. **完整版脚本** (`safe_data_update.sh`) - 推荐用于生产环境
2. **快速版脚本** (`quick_update.sh`) - 适合快速手动更新

## 🚀 快速开始

### 方式 1: 使用完整版脚本（推荐）

```bash
cd /Users/atmbrandnew/Desktop/SOLOProject/ATMstockMarket
./scripts/safe_data_update.sh
```

**特点**：
- ✅ 完整的错误处理
- ✅ 详细的日志记录
- ✅ 每一步都验证成功
- ✅ 失败时自动清理
- ✅ 数据库完整性检查

### 方式 2: 使用快速版脚本

```bash
cd /Users/atmbrandnew/Desktop/SOLOProject/ATMstockMarket
./scripts/quick_update.sh
```

**特点**：
- ✅ 简洁快速
- ✅ 适合手动执行
- ✅ 基本的错误处理

## 📝 流程说明

### 完整流程（6个步骤）

```
┌─────────────────────────────────────────────────────────┐
│  步骤 1: 停止 Web 服务器                                 │
│  ├─ 检测运行中的 uvicorn 进程                           │
│  ├─ 发送停止信号                                        │
│  └─ 验证进程已停止                                      │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  步骤 2: 清理数据库锁文件                                │
│  └─ 删除 analysis.duckdb.wal 文件                      │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  步骤 3: 获取 Tushare 数据                               │
│  ├─ 运行 tushare_fetcher.py                            │
│  ├─ 监控执行状态                                        │
│  └─ 验证退出码 = 0                                      │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  步骤 4: 获取 AKShare 数据                               │
│  ├─ 运行 akshare_fetcher.py                            │
│  ├─ 监控执行状态                                        │
│  └─ 验证退出码 = 0                                      │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  步骤 5: 验证数据库完整性                                │
│  ├─ 检查数据库文件存在                                  │
│  ├─ 显示数据库大小                                      │
│  └─ 检查 WAL 文件残留                                   │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  步骤 6: 重启 Web 服务器                                 │
│  ├─ 启动 uvicorn 服务                                   │
│  ├─ 等待服务就绪                                        │
│  └─ 验证服务可访问                                      │
└─────────────────────────────────────────────────────────┘
                          ↓
                    ✅ 全部完成
```

## 🔍 日志查看

### 实时查看日志

```bash
# 查看最新的更新日志
tail -f logs/data_update_*.log

# 查看最近的日志文件
ls -lt logs/data_update_*.log | head -1 | awk '{print $NF}' | xargs tail -f
```

### 日志文件位置

```
logs/
├── data_update_20260504_134530.log
├── data_update_20260504_160000.log
└── data_update_20260505_160000.log
```

## ⚙️ 定时任务设置

### 使用 crontab 设置自动更新

```bash
# 编辑 crontab
crontab -e

# 添加以下行（每个交易日收盘后 16:00 更新）
0 16 * * 1-5 /Users/atmbrandnew/Desktop/SOLOProject/ATMstockMarket/scripts/safe_data_update.sh >> /Users/atmbrandnew/Desktop/SOLOProject/ATMstockMarket/logs/cron.log 2>&1
```

**说明**：
- `0 16 * * 1-5` - 每周一到周五 16:00 执行
- `1-5` 表示周一到周五（交易日）
- 日志输出到 `logs/cron.log`

### 查看定时任务

```bash
# 查看当前的 crontab
crontab -l

# 查看定时任务日志
tail -f logs/cron.log
```

## 🛠️ 故障排查

### 问题 1: Web 服务器无法停止

```bash
# 手动停止
pkill -9 -f uvicorn

# 检查是否有残留进程
ps aux | grep uvicorn
```

### 问题 2: 数据获取失败

```bash
# 查看详细日志
tail -100 logs/data_update_*.log

# 手动运行数据获取脚本测试
PYTHONPATH=$(pwd) python3 src/data_fetchers/tushare_fetcher.py --verify
PYTHONPATH=$(pwd) python3 src/data_fetchers/akshare_fetcher.py --verify
```

### 问题 3: Web 服务器启动失败

```bash
# 检查端口是否被占用
lsof -i :8000

# 手动启动测试
PYTHONPATH=$(pwd) python3 -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000
```

### 问题 4: 数据库锁定

```bash
# 清理 WAL 文件
rm -f data/database/analysis.duckdb.wal

# 检查数据库文件
ls -lh data/database/
```

## 📊 执行时间估算

| 步骤 | 预计时间 | 说明 |
|------|---------|------|
| 停止 Web 服务器 | 3秒 | 等待进程优雅退出 |
| 清理锁文件 | < 1秒 | 删除 WAL 文件 |
| Tushare 数据获取 | 2-10分钟 | 取决于数据量和网络 |
| AKShare 数据获取 | 10-30秒 | 龙虎榜数据 |
| 数据库验证 | < 1秒 | 文件检查 |
| 重启 Web 服务器 | 3秒 | 等待服务就绪 |
| **总计** | **3-11分钟** | Web 服务中断 < 10秒 |

## 🎯 最佳实践

### 1. 交易日收盘后更新

```bash
# 推荐：每个交易日 16:00 自动更新
0 16 * * 1-5 /path/to/safe_data_update.sh
```

### 2. 手动更新前检查

```bash
# 检查 Web 服务器状态
pgrep -f uvicorn

# 检查数据库状态
PYTHONPATH=$(pwd) python3 src/data_fetchers/tushare_fetcher.py --verify
```

### 3. 监控更新结果

```bash
# 设置日志监控
tail -f logs/data_update_*.log | grep -E "✓|✗|错误|成功"
```

### 4. 定期清理日志

```bash
# 保留最近 30 天的日志
find logs/ -name "data_update_*.log" -mtime +30 -delete
```

## 📞 技术支持

如果遇到问题，请提供以下信息：

1. 错误日志（`logs/data_update_*.log`）
2. 数据库状态（`--verify` 输出）
3. 系统环境（Python 版本、操作系统）

---

**最后更新**: 2026-05-04  
**维护者**: ATMstockMarket Team
