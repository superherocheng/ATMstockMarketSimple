# 申万行业市值/PE/PB 不显示问题 - 解决方案

## 问题诊断

经过代码审查和测试，发现问题的根本原因是：**stock_daily_basic 表没有数据或数据不完整**。

### 症状
- 行业分析页面显示所有行业的市值、PE、PB 都是 `--`
- API 返回的数据中 `avg_mv`、`avg_pe`、`avg_pb` 都是 `null`

### 根本原因
`stock_daily_basic` 表存储了每只股票的每日估值数据（市值、PE、PB、换手率等）。如果这个表为空或数据不完整，行业分析就无法计算平均市值、PE、PB。

---

## 解决方法

### 方法 1：更新估值数据（推荐）

运行以下命令获取最新的估值数据：

```bash
cd /Users/atmbrandnew/Desktop/SOLOProject/ATMstockMarket/tushare-py
python fetch_data.py --funda
```

这将：
1. 从 Tushare API 获取所有股票的每日估值数据
2. 包括：市值、PE（市盈率）、PB（市净率）、换手率等
3. 数据将存储在 `stock_daily_basic` 表中

**注意**：这个过程可能需要较长时间，取决于你的 Tushare 积分等级。

---

### 方法 2：完整更新所有数据

如果方法 1 不够，可以完整更新所有数据：

```bash
cd /Users/atmbrandnew/Desktop/SOLOProject/ATMstockMarket/tushare-py

# 1. 更新基础信息（股票列表、行业分类）
python fetch_data.py --basic

# 2. 更新日线数据（股价、成交量）
python fetch_data.py --daily

# 3. 更新估值数据（市值、PE、PB）
python fetch_data.py --funda
```

---

### 方法 3：检查数据完整性

运行诊断脚本检查数据状态：

```bash
cd /Users/atmbrandnew/Desktop/SOLOProject/ATMstockMarket

# 注意：需要先停止 Web 服务器
python diagnose_industry.py
```

---

## 已实施的代码改进

为了更好地处理数据缺失的情况，我已经对代码进行了以下改进：

### 1. 后端改进 ([web/app.py](file:///Users/atmbrandnew/Desktop/SOLOProject/ATMstockMarket/web/app.py))

- ✅ 添加数据完整性检查
- ✅ 保留 `null` 值而不是转换为 0，让前端能区分"无数据"和"数据为0"
- ✅ 添加详细的日志记录
- ✅ 返回友好的错误和警告消息

### 2. 前端改进 ([web/templates/industry.html](file:///Users/atmbrandnew/Desktop/SOLOProject/ATMstockMarket/web/templates/industry.html))

- ✅ 正确处理 `null` 值，显示 `--` 表示无数据
- ✅ 显示友好的警告消息，指导用户如何解决
- ✅ 图表自动降级：无市值数据时显示股票数量对比

---

## 验证修复

更新数据后，按以下步骤验证：

1. **重启 Web 服务器**
   ```bash
   # 停止当前服务器（Ctrl+C）
   # 重新启动
   cd /Users/atmbrandnew/Desktop/SOLOProject/ATMstockMarket/web
   uvicorn app:app --reload --port 8000
   ```

2. **清除浏览器缓存**
   - Chrome: Cmd+Shift+Delete
   - 或使用隐私模式打开

3. **访问行业分析页面**
   - 打开 http://localhost:8000/industry
   - 检查市值、PE、PB 是否正常显示

4. **运行 API 测试**
   ```bash
   cd /Users/atmbrandnew/Desktop/SOLOProject/ATMstockMarket
   python check_industry_api.py
   ```

---

## 数据要求

为了正常显示行业分析数据，需要满足以下条件：

| 数据表 | 必需字段 | 说明 |
|--------|---------|------|
| `stock_info` | `ts_code`, `name`, `sw_level1` | 股票基础信息和申万行业分类 |
| `stock_daily` | `ts_code`, `trade_date`, `close`, `pct_chg` | 日线行情数据 |
| `stock_daily_basic` | `ts_code`, `trade_date`, `total_mv`, `pe_ttm`, `pb` | 每日估值数据 |

**关键点**：
- 三个表的 `ts_code` 必须能关联
- `trade_date` 最好一致（都是最新交易日）
- `sw_level1` 不能为空（来自 ALLSYMBOL.csv）

---

## 常见问题

### Q1: 运行 `python fetch_data.py --funda` 报错

**A**: 检查以下几点：
1. Tushare Token 是否配置正确（`config.py`）
2. 网络连接是否正常
3. Tushare 积分是否足够（估值数据需要较高积分）

### Q2: 数据更新后仍然不显示

**A**: 尝试以下步骤：
1. 清除预计算缓存：删除 `tushare-py/data/cache/` 目录
2. 重启 Web 服务器
3. 清除浏览器缓存
4. 检查服务器日志是否有错误

### Q3: 部分行业有数据，部分没有

**A**: 这是正常的，可能原因：
1. 某些行业的股票没有估值数据（如新股）
2. 数据日期不匹配
3. 股票代码格式不一致

---

## 技术细节

### 数据流程

```
ALLSYMBOL.csv
    ↓
stock_info (股票基础信息 + 申万行业分类)
    ↓
stock_daily (日线行情)
    ↓
stock_daily_basic (估值数据: 市值/PE/PB)
    ↓
行业分析 API (计算平均值)
    ↓
前端展示
```

### SQL 查询逻辑

```sql
SELECT 
    si.sw_level1 as industry,
    AVG(sb.total_mv) as avg_mv,
    AVG(sb.pe_ttm) as avg_pe,
    AVG(sb.pb) as avg_pb
FROM stock_info si
LEFT JOIN stock_daily_basic sb 
    ON si.ts_code = sb.ts_code
    AND sb.trade_date = (SELECT MAX(trade_date) FROM stock_daily_basic)
WHERE si.sw_level1 IS NOT NULL
GROUP BY si.sw_level1
```

如果 `stock_daily_basic` 为空，`LEFT JOIN` 会返回 `NULL`，导致 `AVG()` 也是 `NULL`。

---

## 联系支持

如果按照以上步骤仍然无法解决问题，请提供以下信息：

1. 运行 `diagnose_industry.py` 的输出
2. Web 服务器的错误日志
3. `fetch_data.py --funda` 的执行结果

---

*最后更新: 2026-05-04*
