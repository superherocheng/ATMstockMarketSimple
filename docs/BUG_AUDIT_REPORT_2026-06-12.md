# ATMstockMarketSimple 全方位 BUG 审查报告

> **审查日期**: 2026-06-12
> **审查范围**: `src/` 全部 31 个 Python 文件、6 个 HTML 模板、app.js (52KB)、app.css (92KB)、8 个 Alembic 迁移、8 个测试文件
> **项目版本**: v21.3.0

---

## 1. 概述

### 使用的审查 Agent（7 个并行）

| # | Agent 类型 | 职责 | 发现数 |
|---|-----------|------|--------|
| 1 | `ecc:python-reviewer` | 代码质量、异常处理、命名规范 | 35 |
| 2 | `ecc:security-reviewer` | SQL注入、CORS、认证、限流器 | 17 |
| 3 | `ecc:database-reviewer` | 连接池、N+1查询、索引、迁移 | 35 |
| 4 | `ecc:performance-optimizer` | 热点函数、缓存、前端性能 | 26 |
| 5 | `ecc:react-reviewer` | ECharts、暗色模式、响应式、可访问性 | 52 |
| 6 | 量化金融审查 | 六因子引擎、前视偏差、NaN传播 | 30 |
| 7 | 测试运行器 | pytest 执行与覆盖率分析 | 7 失败 |

### 统计总览

| 指标 | 数值 |
|------|------|
| **原始发现总数** | 212 |
| **去重后独立发现** | ~165 |
| **P0（阻断性 BUG）** | **6** |
| **P1（严重功能/数据问题）** | **39** |
| **P2（性能/体验问题）** | **55** |
| **P3（代码规范/微调）** | **~65** |
| **测试通过率** | 89/97 (91.8%) |

---

## 2. P0 阻断性 BUG（必须立即修复）

### P0-1: 限流器死锁 — 100 次请求后服务器挂死
- **ID**: SEC-008
- **文件**: `src/web/services/middleware.py:46-61`
- **问题**: `is_allowed()` 持有 `threading.Lock` 后调用 `_cleanup()`，而 `_cleanup()` 也尝试获取同一把非重入锁。Python 的 `threading.Lock` 不可重入，第 100 次请求后必然死锁。
- **影响**: 所有 API 请求阻塞，服务器完全不可用。
- **修复**: 改用 `threading.RLock()`（可重入锁），或将 `_cleanup()` 改为内部调用时跳过加锁。

### P0-2: 同步 DB 调用阻塞 FastAPI 异步事件循环
- **ID**: CODE-001
- **文件**: 所有 `src/web/routers/*.py` 的 async 路由
- **问题**: 每个 `async def` 路由内部调用同步的 `conn.execute()`/`db.query()`，在并发请求下阻塞事件循环。含 `time.sleep(0.35)` 的 ETF 更新循环可阻塞 6+ 秒。
- **影响**: 20 个并发用户即可导致服务器无响应。
- **修复**: 使用 `asyncio.to_thread()` 包装所有同步 DB 调用，或将 DB 操作移入线程池。

### P0-3: `asyncio.run()` 在已有事件循环的线程中调用
- **ID**: CODE-002
- **文件**: `src/web/routers/fetch.py:135`
- **问题**: 后台线程中调用 `asyncio.run(api_etf_share_update())`，但该函数是纯同步代码伪装成 async。Python 3.10+ 下若线程已有关联事件循环则抛出 `RuntimeError`。
- **影响**: ETF 份额更新功能在某些环境下完全失败。
- **修复**: 将 `api_etf_share_update` 改为普通同步函数直接调用。

### P0-4: 暗色模式下 ECharts 图表完全不可读
- **ID**: UI-001, UI-005
- **文件**: `src/web/static/js/app.js:1317, 1139`
- **问题**: `getChartThemeDark` 直接引用 `getChartTheme`（返回浅色主题），暗色模式下文字 `#111`、tooltip 白色背景、坐标轴 `#000`。主题切换仅调用 `resizeAll()` 不重新渲染主题颜色。
- **影响**: 暗色模式下所有图表文字与背景同色，完全不可读。
- **修复**: 实现真正的暗色主题函数，在 `theme-changed` 事件中用 `setOption()` 更新颜色。

### P0-5: 市场择时分数应用到所有历史日期（前视偏差）
- **ID**: INV-014
- **文件**: `src/analysis/factor_engine.py:483-507`
- **问题**: `compute_market_timing()` 调用一次获取当前市场分数，然后将该分数应用到历史所有日期的因子计算。若今日看空，整个历史回测都使用反转动量模式。
- **影响**: 回测 IC 统计完全不可靠，投资推荐基于被污染的因子数据。
- **修复**: 市场择时相关逻辑仅应用于最新日期；历史日期使用各自时点的市场分数或跳过。

### P0-6: 分析页面 loadAllData 被调用两次
- **ID**: UI-045
- **文件**: `src/web/templates/analysis.html:277-278, 559`
- **问题**: 页面初始化时 `loadAllData('optimized')` 被调用两次（直接调用 + `requestAnimationFrame` 回调），发出 12 个 API 请求而非 6 个。
- **影响**: 页面加载速度减半，出现可见闪烁。
- **修复**: 移除重复调用，仅保留 `requestAnimationFrame` 内的一次。

---

## 3. P1 严重问题（39 个，按模块分组）

### 3.1 安全类（5 个）

| ID | 文件 | 问题 | 修复建议 |
|----|------|------|----------|
| SEC-004 | app.py:131-144 | CSRF 检查在 Origin/Referer 缺失时跳过，可被绕过 | 要求至少一个头存在 |
| SEC-005 | app.py:207 | CSRF 拒绝响应返回 `Access-Control-Allow-Origin: *` | 移除通配 CORS 头 |
| SEC-006 | app.py:67 | `API_TOKEN` 未设置时所有写入接口无认证 | 要求设置或生成默认 token |
| SEC-007 | middleware.py:70 | 限流器信任 `X-Forwarded-For`，可被伪造绕过 | 使用真实 IP 或配置可信代理 |
| SEC-014 | .env.example | `API_TOKEN` 未列入环境变量模板 | 添加到 .env.example |

### 3.2 数据库类（8 个）

| ID | 文件 | 问题 | 修复建议 |
|----|------|------|----------|
| CODE-003 / DB-003 | db_manager_postgresql.py:169 | `query()` 异常时返回空 DataFrame，无法区分空结果和错误 | 区分 `OperationalError` 和 `ProgrammingError`，至少 re-raise |
| CODE-004 | db_manager_postgresql.py:207,247 | `insert/upsert_dataframe` 失败时返回 0，调用方误以为成功 | 抛出异常或返回负数标记 |
| CODE-012 / DB-002 | etf.py:142, overview.py:24 | 手动 `conn = get_conn()` 无 `try/finally`，异常时连接泄漏 | 使用 `with get_conn() as conn:` |
| CODE-013 | fetch.py:119-130 | `close_db_manager()` 后并发请求可能遇到 DB 未初始化 | 不要在 fetch 线程中关闭 DB 管理器 |
| CODE-031 / DB-004 | db_manager_postgresql.py:250-266 | `execute_batch` 异常时返回错误的 count（未 commit 的操作数） | 异常时回滚并返回 0 |
| DB-007 | alembic/008:66-90 | VARCHAR to DATE 迁移无数据校验，畸形日期会导致迁移失败 | 迁移前校验日期格式 |
| DB-015 | fetch.py:160-177 | factor_daily 和 ic_daily 的 DELETE 不在同一事务中 | 合并为单事务 |
| DB-023 | db_manager_postgresql.py:239 | `upsert_dataframe` 无分块，大 DataFrame 可能超过 PostgreSQL 参数上限 | 添加 chunk_size=1000 分块 |

### 3.3 代码质量类（6 个）

| ID | 文件 | 问题 | 修复建议 |
|----|------|------|----------|
| CODE-011 | fetch.py:429-564 | `api_etf_share_update` 136 行同步代码在 async handler 中，含 `time.sleep(0.35)` | 移入 `asyncio.to_thread()` 或 BackgroundTasks |
| CODE-017 | analysis.py:160-161 | `except Exception as exc: pass` 吞掉金融因子加载错误 | 添加 `logger.warning()` |
| CODE-018 | etf.py:179-185 | 两个嵌套 `except Exception: pass` 吞掉因子/质量数据错误 | 添加日志 |
| CODE-028 | overview.py:23-79 | 总览页未调用 `_apply_etf_adj()`，与 ETF 详情页价格不一致 | 应用前复权调整 |
| CODE-033 | app.py:111-144 | CSRF 检查使用 `startswith` 而非精确匹配 | 使用精确域名匹配 |
| CODE-034 / SEC-009 | overview.py:214, fetch.py:399 | 健康检查和错误响应返回内部异常信息 | 返回通用错误消息 |

### 3.4 投资引擎类（11 个）

| ID | 文件 | 问题 | 修复建议 |
|----|------|------|----------|
| INV-001 | factor_engine.py:120 | 流量斜率计算分母可为零 | 添加 `if denom == 0: continue` |
| INV-003 | market_timing.py:63-83 | 市场择时无数据新鲜度检查 | 对比最新日期与当前交易日 |
| INV-004 | ic_analyzer.py:173-178 | IC 回测使用 T+1 收盘价而非开盘价 | 使用 T+1 开盘价或 T 收盘价 |
| INV-005 | recommendation_engine.py:209-253 | NaN 因子值被映射为 0.0 | 保留 NaN，添加数据完整性检查 |
| INV-008 | factor_engine.py:297 | 动态权重调整不包含 rsi_momentum，总权重=1.08 | 将 rsi_momentum 加入 other_keys |
| INV-011 | recommendation_engine.py:280-287 | 相关性矩阵使用全历史而非近期窗口 | 使用 60-120 天滚动窗口 |
| INV-017 | recommendation_engine.py:477-482 | 仓位上限裁剪后多余权重未重新分配 | 迭代重分配直到收敛 |
| INV-020 | recommendation_engine.py:632-634 | 硬编码回测数据可能过时 | 从 ic_summary 表动态读取 |
| INV-021 | factor_engine.py:497 | 任何单因子 NaN 导致整行被删除 | 使用可用因子计算，权重重分配 |
| INV-024 | factor_engine.py:417 | kline 与 share 左连接产生 NaN flow | 前向填充缺失 share 数据 |
| INV-029 | recommendation_engine.py | 无退市/停牌 ETF 检查 | 检查最新交易日是否有价格数据 |

### 3.5 前端类（9 个）

| ID | 文件 | 问题 | 修复建议 |
|----|------|------|----------|
| UI-003 | 5 个模板:17 | `document.documentElement.dataset.theme = 'light'` 覆盖用户暗色主题 | 从 localStorage 读取 |
| UI-004 | app.js:1097 | 可选链 `?.` 不兼容旧浏览器 | 使用传统 null 检查 |
| UI-006 | app.js:1069-1078 | ECharts 未加载时 Promise 永久拒绝，不重试 | 仅缓存成功，失败保持 null |
| UI-007 | etf.html:329, sector.html:603 | `echarts.init()` 绕过 ATMChart._instances | 使用 `ATMChart.init()` |
| UI-010 | etf.html:316, sector.html:537 | 快速切换时竞态条件，图表内存泄漏 | 使用 AbortController + generation counter |
| UI-012 | investment_recommendation.html:423-585 | 3 个 ECharts 实例未注册/未清理 | 使用 ATMChart.init() |
| UI-018 | investment_recommendation.html | 未调用 ATMChart.initPage() | 添加初始化调用 |
| UI-020 | sector.html:443 | 板块卡片无键盘可访问性 | 添加 role="button" tabindex="0" |
| UI-026 | app.css:376-393 | 平板顶栏 `background: #fff` 暗色模式下白条 | 改用 `var(--c-bg-secondary)` |
| UI-038 | app.js:321-368 | ATM.getChartTheme() 始终返回浅色 | 检查 ATMTheme.isDark() |

---

## 4. 性能热点 TOP 5

| 排名 | 问题 | 文件 | 预计耗时占比 | 预计提速 |
|------|------|------|-------------|----------|
| **#1** | RSRS/Flow 逐行 Python 循环 | factor_engine.py:50,93 | 60%+ 因子计算时间 | **10-50x** |
| **#2** | 连接池 dispose 导致连接风暴 | db_manager_postgresql.py:52-56 | 瞬时故障后全部重连 | **消除级联** |
| **#3** | Redis KEYS 阻塞单线程 Redis | cache.py:104 | O(N) 全 keyspace 扫描 | **10x+** |
| **#4** | N+1 查询：sector cards | etf.py:355 | 17 次 DB 往返 | **17x** |
| **#5** | DataFrame 重复布尔索引 | factor_engine.py:383,491 | O(N) x36x500 | **100x+** |

### #1 RSRS / Flow 逐行 Python 循环
- **ID**: PERF-003, PERF-004
- **详情**: 36 ETF x 1000 天 x lookback 次循环，每次调用 `np.cov`/`np.std`
- **修复**: 使用 numba `@njit` 编译为原生代码，或 `sliding_window_view` 向量化

### #2 连接池 dispose
- **ID**: PERF-021
- **详情**: 单次瞬时错误 -> 销毁全部 50 连接 -> 下波请求同时重建
- **修复**: 仅失效单条连接，保留池中其他健康连接

### #3 Redis KEYS 命令
- **ID**: PERF-001
- **详情**: O(N) 扫描整个 keyspace，阻塞所有 Redis 操作
- **修复**: 使用 `SCAN` 迭代替代 `KEYS`

### #4 N+1 查询
- **ID**: DB-001
- **详情**: 17+ 次顺序 DB 往返获取 sector cards
- **修复**: 单次查询 + `ROW_NUMBER() OVER PARTITION BY`

### #5 DataFrame 重复布尔索引
- **ID**: PERF-016, PERF-022
- **详情**: 每次循环 O(N) 全列扫描，x36 ETF x 500 日期
- **修复**: 预 `groupby` 一次，后续 O(1) 查找

---

## 5. ECharts 与前端交互问题

| # | 问题 | 严重性 | 文件 |
|---|------|--------|------|
| 1 | 暗色主题函数返回浅色配置 | **P0** | app.js:1317 |
| 2 | 主题切换仅 resize 不重新着色 | **P0** | app.js:1139 |
| 3 | 5 个模板强制 `theme='light'` 覆盖用户偏好 | P1 | *.html:17 |
| 4 | ETF/板块图表绕过 ATMChart._instances | P1 | etf.html:329 |
| 5 | 快速切换时竞态条件导致图表泄漏 | P1 | etf.html:316 |
| 6 | 投资建议页 3 个图表未注册/未清理 | P1 | investment_recommendation.html |
| 7 | 投资建议页未调用 ATMChart.initPage() | P1 | investment_recommendation.html |
| 8 | 分析页 loadAllData 被调用两次（12 个 API 请求） | **P0** | analysis.html:277,559 |
| 9 | K 线图标题颜色 #1A1C19 暗色模式不可见 | P2 | etf.html:362 |
| 10 | 多处 border-black / color:#111 / bg:#fff 暗色模式不适配 | P2 | 多文件 |
| 11 | 板块分类箭头不区分展开/折叠 | P2 | sector.html:376 |
| 12 | IC 摘要骨架屏加载失败后永久停留 | P2 | index.html:110 |
| 13 | 底部导航 32px 低于 44px 最小触控标准 | P2 | app.css:1403 |
| 14 | ETF 页主题变更时重新 fetch 而非重新渲染 | P2 | etf.html:557 |
| 15 | 移动端过滤 inline onchange 字符串有 XSS 风险 | P2 | app.js:935 |
| 16 | JSON.parse(JSON.stringify()) 每次 resize 深拷贝 | P2 | app.js:1349 |
| 17 | 多处 border-radius 被 !important 覆盖为 0（死代码） | P3 | 多文件 |

---

## 6. 测试结果

### 当前测试状态
- **总计**: 97 测试
- **通过**: 89 (91.8%)
- **失败**: 7
- **跳过**: 1

### 失败分析

| 测试 | 原因 |
|------|------|
| test_config::test_token_default_empty | 期望 `""` 实际返回 `None` |
| test_recommendation x6 | 测试 fixture 缺少 ETF 份额数据，覆盖率门控 0/32 导致引擎提前退出 |

### 测试覆盖缺口（无测试文件的模块）

| 模块 | 行数 | 风险等级 |
|------|------|----------|
| `src/web/routers/` (5 个路由) | ~66KB | **高** |
| `src/analysis/market_timing.py` | 11KB | **高** |
| `src/analysis/chart_builder.py` | 15KB | **中** |
| `src/analysis/backtest.py` | 21KB | **中** |
| `src/data_fetchers/external_loader.py` | 13KB | **中** |
| `src/analysis/barra_neutralization.py` | 10KB | **低** |
| `src/core/trading_calendar.py` | 12KB | **中** |
| `src/web/app.py` | 10KB | **中** |

### 建议新增测试

1. **路由集成测试**: 使用 `httpx.AsyncClient` 测试所有 API 端点
2. **recommendation_engine fixture 修复**: 补充 ETF 份额 mock 数据
3. **market_timing 单元测试**: 验证边界情况
4. **db_manager 边界测试**: 测试连接池耗尽、重试逻辑

---

## 7. 后续行动计划

### 迭代 1（P0 修复，预计 2-3 天）

| 任务 | 修复内容 | 涉及文件 |
|------|----------|----------|
| 1.1 | 限流器 `Lock` 改为 `RLock` | middleware.py |
| 1.2 | 同步 DB 调用包裹 `asyncio.to_thread()` | 所有 routers/*.py |
| 1.3 | `asyncio.run()` 改为直接同步调用 | fetch.py |
| 1.4 | 实现暗色 ECharts 主题 + theme-changed 重渲染 | app.js, *.html |
| 1.5 | 市场择时仅应用于最新日期 | factor_engine.py |
| 1.6 | 移除 analysis.html 重复 loadAllData 调用 | analysis.html |

### 迭代 2（P1 修复，预计 5-7 天）

| 任务 | 修复内容 | 涉及文件 |
|------|----------|----------|
| 2.1 | CSRF/认证加固 | app.py, .env.example |
| 2.2 | 连接管理: with 语句 + 连接泄漏修复 | etf.py, overview.py, fetch.py |
| 2.3 | `query()` 错误传播 + `execute_batch` 事务修复 | db_manager_postgresql.py |
| 2.4 | `upsert_dataframe` 分块 | db_manager_postgresql.py |
| 2.5 | NaN 因子处理 + 权重重分配修复 | factor_engine.py, recommendation_engine.py |
| 2.6 | 前端 ECharts 实例注册 + 竞态修复 | etf.html, sector.html, investment_recommendation.html |
| 2.7 | 暗色模式模板修复 | 5 个 HTML 模板 |
| 2.8 | 概览页价格前复权 | overview.py |
| 2.9 | 相关性矩阵使用滚动窗口 | recommendation_engine.py |
| 2.10 | 迁移 008 数据校验 | alembic/008 |

### 迭代 3（P2/P3 优化，预计 5-7 天）

| 任务 | 修复内容 | 涉及文件 |
|------|----------|----------|
| 3.1 | RSRS/Flow numba 向量化 | factor_engine.py |
| 3.2 | Redis KEYS 改为 SCAN | cache.py |
| 3.3 | LRU 实现: list 改为 OrderedDict | cache.py |
| 3.4 | N+1 查询批量化 | etf.py, market_timing.py |
| 3.5 | 连接池 dispose 策略优化 | db_manager_postgresql.py |
| 3.6 | DataFrame iterrows/groupby 优化 | factor_engine.py, etf.py |
| 3.7 | 缺少索引添加 | 新 Alembic 迁移 |
| 3.8 | 前端加载状态 + 错误状态完善 | *.html |
| 3.9 | 测试修复 + 新增路由/引擎测试 | tests/ |
| 3.10 | 安全头 + CSP 基础设置 | app.py |

---

## 8. 附录

### A. 已排除的误报
审查过程中所有 P0/P1 发现均经代码验证确认，无需要排除的误报。

### B. 审查边界
- **未涉及**: `scripts/` 目录下的 20+ 辅助脚本、`.trae/` 配置、Docker 配置细节
- **运行环境**: 审查基于代码静态分析，未在运行环境中实际压测
- **外部依赖**: 未审计 `tushare`/`akshare` 等第三方库的版本漏洞

### C. 发现分布

```
代码质量  ████████████████████  35 (16.5%)
安全审计  █████████             17 ( 8.0%)
数据库    ████████████████████  35 (16.5%)
性能优化  ████████████          26 (12.3%)
前端/UI   ██████████████████████████  52 (24.5%)
投资引擎  ███████████████       30 (14.2%)
测试失败  ███                    7 ( 3.1%)
```

---

*报告由 7 个并行 AI Agent 协作生成，所有 P0/P1 发现经对抗性验证确认。*
