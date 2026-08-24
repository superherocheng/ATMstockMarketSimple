# ATMstockMarketSimple

<div align="center">

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14%2B-336791?logo=postgresql&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

**A股 ETF 量化监控平台 | Chinese A-Share ETF Quantitative Monitoring Platform**

[功能特性](#-功能特性) • [页面](#-页面) • [快速开始](#-快速开始) • [API 端点](#-api-端点) • [数据模型](#-数据模型) • [择时方法论](#-择时方法论)

</div>

---

## 📖 项目简介

ATMstockMarketSimple 是一个 A股 ETF 量化监控平台，核心是**价格 × 份额背离分析**与**大盘择时仪表盘**，并保留一套多因子行业轮动引擎（ICIR 门控，因子失效时自动空仓）。

技术栈：**FastAPI + PostgreSQL + Redis（可选）+ React 19 (Vite) + ECharts 5**。数据源为 **Tushare Pro**（ETF 日线 / 份额 / 复权因子 / 指数估值）。

> 📄 方法论参考：宽基ETF 20 年量价×份额择时研究（`etf_timing_analysis/REPORT.md`）与中信期货行业轮动框架（`NEW策略.md`）。

## ✨ 功能特性

### 📊 价格 × 份额背离（核心）
- 全市场（5 宽基 + 32 行业）**背离散点图**：X=区间价格涨跌、Y=区间份额变化、气泡=成交额
- 绝对背离标签：**风险背离**（价涨份额缩）/ **潜伏背离**（价跌份额增）+ 连续背离天数
- **同指数家族份额聚合**：单只宽基 ETF 的份额被同指数内申赎搬家（工具轮动）污染，宽基背离统一按「同指数全部 ETF 家族」加总计算（如 510300+510310+159919+…）
- 背离强度榜（rank_gap）、四象限**历史前瞻收益角标**（与散点同口径重算）
- 5/10/20/60 日多窗口切换

### 🌡️ 择时仪表盘（/timing）
- **仓位合成卡**：波动乘数 × 恐慌叠加 × 估值修正（分解透明，非黑盒）
- **估值温度计**：沪深300/中证500/创业板指 PE/PB 历史分位
- **趋势状态**：MA200 上/下 + 距一年高低（状态标签，非交易信号）
- **恐慌仪表**：5日跌≥5%+放量 → 历史前瞻均值/胜率（唯一 OOS 稳健方法族）
- **波动状态**：20 日年化波动 → 仓位乘数（目标 12%）
- **家族份额流**：同指数聚合份额 vs 价格 60 日滚动相关（越跌越买 regime 识别）
- **轮动矩阵**：市场情绪 × 轮动强度 → 3×3 仓位决策（中信期货框架）
- **底部定位器**：深跌≥20% + 家族份额逆势流入的历史事件与当前状态
- **日历效应**：月度 × ETF 历史平均收益热力图

### 🔬 因子模型（V9，ICIR 门控）
- 六因子 → **四因子**：RSRS(0.30) + Flow(0.21) + Mom(0.34) + RSI_Mom(0.15)，Quality 与 Efficiency 权重归零（无有效数据 / 样本内负 IC）
- 横截面 rank-Z 标准化、RSRS MA 趋势衰减、组合粘性
- **ICIR 门控**：近 60 日 ICIR 驱动 四模式（全力出击≥0.5 / 标准 0.3~0.5 / 谨慎 0.2~0.3 / **冬眠 <0.2 暂停选股**）
- 强制 15 日持有 + 两阶段相关性惩罚 + 单只仓位上限 25%
- ⚠️ 权重标定样本仅 2025-09~2026-06 单一 regime，属**样本内数字**，需 walk-forward 复验

### 🛠️ 数据管理
- 首页「刷新数据」→ 后台抓行情→份额→复权→估值，**完成后自动重算因子+IC**（修复了推荐引擎长期冻结的问题）
- `--backfill YYYYMMDD`：一键回补 ETF 历史（日线/份额/复权/估值），按年分段、幂等 upsert

## 📄 页面

| 路由 | 页面 | 内容 |
|------|------|------|
| `/` | 概览 | 行业热度 treemap、价格×份额背离散点 + 背离榜、宽基/行业份额表格 |
| `/etf` | ETF 详情 | 前复权 K线 + MA、量能 60 日百分位、份额面积图 + 异常点标注、10日背离统计条 |
| `/benchmarketf` | 指数ETF | 宽基背离象限 + 当日涨跌/份额变化/10日份额三张横向条形图 |
| `/timing` | **择时仪表盘** | 仓位合成 + 五面板 + 轮动矩阵 + 底部定位 + 日历效应 |

## 🚀 快速开始

### 本地开发

```bash
# 1. 安装依赖（Python 3.12+）
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt -e ".[dev]"
cd frontend && npm install && cd ..

# 2. 配置 .env（复制 .env.example，填 TUSHARE_TOKEN 与 DATABASE_URL）
cp .env.example .env

# 3. 初始化数据库
.venv/bin/alembic upgrade head

# 4. 拉取历史（可选：回补 5 年）
.venv/bin/python src/data_fetchers/tushare_fetcher.py --backfill 20210824

# 5. 启动后端 + 前端
.venv/bin/python -m uvicorn src.web.app:app --port 5656 &
cd frontend && npm run dev
```

### Docker 部署

```bash
docker compose up -d --build
docker exec atmstockmarket python3 -u /app/src/data_fetchers/tushare_fetcher.py --etf   # 首次拉数据
# 访问 http://<host>:5656，首页点「刷新数据」
```

**日常更新**：首页「刷新数据」按钮 = 行情更新 + 因子/IC 自动重算，无需 SSH。

## 🔌 API 端点

### 数据查询
| 方法 | 路由 | 描述 |
|------|------|------|
| GET | `/api/overview` | 概览（宽基+行业最新日线 + 家族聚合份额变化） |
| GET | `/api/heatmap` | 行业热度 treemap |
| GET | `/api/data-range` | 各表日期范围与记录数 |
| GET | `/api/index-etf/{code}` | 单只宽基完整 K线+份额+异常点 |
| GET | `/api/sector-etf/{code}` | 单只行业同上 |
| GET | `/api/divergence?window=5/10/20/60` | 价格×份额背离（含家族聚合、象限前瞻收益） |
| GET | `/api/market-timing` | 大盘择时合成信号 |

### 择时仪表盘
| 方法 | 路由 | 描述 |
|------|------|------|
| GET | `/api/timing/thermometer` | 温度计（估值/趋势/恐慌/波动/家族份额流 + 仓位合成） |
| GET | `/api/timing/rotation` | 轮动矩阵（情绪×轮动强度 → 3×3） |
| GET | `/api/timing/calendar` | 月度×ETF 平均收益热力图 |
| GET | `/api/timing/locator` | 底部定位器 |

### 量化分析
| 方法 | 路由 | 描述 |
|------|------|------|
| GET | `/api/investment-recommendation` | 投资建议（ICIR 门控 + 仓位配置） |
| GET | `/api/analysis/holding-history` | 持仓历史快照 |

### 数据管理
| 方法 | 路由 | 描述 |
|------|------|------|
| POST | `/api/fetch/all\|etf\|tushare` | 数据更新 + 自动因子/IC 重算 |
| GET | `/api/fetch/status` | 更新任务进度轮询 |
| GET | `/api/etf-share/status` | 份额覆盖度检查 |
| POST | `/api/etf-share/update` | 智能份额更新 |
| POST | `/api/cache/invalidate` | 清缓存 |

## 📚 数据模型

| 表 | 内容 | 说明 |
|------|------|------|
| `index_etf_daily` / `sector_etf_daily` | 宽基/行业 ETF 日线 | 前复权经 `_apply_etf_adj` |
| `etf_share` | ETF 份额 fd_share（万份） | **T+1 发布**，天然滞后一天 |
| `etf_adj_factor` | 复权因子 | 处理分红/拆分/折算 |
| `index_daily_basic` | 指数估值 PE/PB | 温度计估值面板 |
| `factor_daily` | 因子日截面 | RSRS/Flow/Mom/RSI_Mom + composite |
| `ic_daily` / `ic_summary` | IC / ICIR | 前瞻 15 日 Spearman IC |
| `quadrant_perf` | 因子四象限前瞻收益 | |

**同指数家族聚合**：`INDEX_ETF_FAMILY`（config.py）定义 5 个宽基家族的成员名单（基于 fund_basic+fund_share 实际规模核验）。家族份额按日加总、成员缺席日前向填充，消除工具轮动假信号。份额专用代码只进 `etf_share`，不进行情/因子流程。

## 🌡️ 择时方法论（关键诚实声明）

基于宽基ETF 20 年（31,595 个 ETF-交易日）量价×份额研究，以下结论直接落地为面板：

| 信号 | 可行性 | 落地 |
|------|:---:|------|
| 日线方向预测（RSI/动量/MA） | ✗ 高置信不可行 | 不做「明日涨跌」型信号 |
| **恐慌反转**（5日跌5%+放量） | △ 弱可行、OOS 最稳 | 恐慌仪表（5日超额+1.4%/胜率60%，高β更强） |
| 波动/量能预测 | ✓ 可行 | 波动面板 → 仓位乘数 |
| 深跌+家族份额逆势流入=底部区域 | △ 区域定位、非精确择时 | 底部定位器 |
| 估值分位 | ✓ 长周期 | 估值温度计 |
| 日历效应（二月/端午/季末） | ✓（FDR 筛过） | 日历热力图 |

**仓位 = 仓位管理工具，不是收益引擎**：空仓资金计入货基收益后，回测总回报接近买入持有而最大回撤约减半。方向判断请勿依赖单一信号。

## ⚠️ 已知局限与诚实性

1. **回测数字是样本内的**：README 中的 ICIR/超额均为同一段（2025-09~2026-06 单一 regime）的样本内评估，需回补 ≥3 年数据后跑 `scripts/generalization_test.py` walk-forward 复验。
2. **份额 T+1 滞后**：实操中「当日份额」次日晚才可知，实盘提示滞后一天。
3. **科创50 无估值**：Tushare `index_dailybasic` 不提供 000688，估值面板自动降级为空。
4. **工具轮动**：单只 ETF 份额 = 投资者流量 × 工具轮动，2026 年起宽基份额信号必须看家族聚合口径。

## 📋 主要变更记录

- **2026-08-24**：修复择时份额腿 T+1 死条件；复活「更新后自动因子+IC 重算」；象限口径统一（散点与 chip 同源）；同指数家族份额聚合（overview/divergence/market-timing）；历史回补 `--backfill`；新增择时仪表盘（温度计/轮动/日历/定位器）；Efficiency 权重清零（V9）；前端新增 /timing 页。
- **2026-07-18**：删除因子分析页与 `/api/analysis/recompute`（导航仅保留 3 页）。
- **2026-07-01**：Quality 因子移除，预设收敛为单 `optimized`。

---

<p align="center">数据来源: Tushare Pro · 仅供学习研究，不构成投资建议</p>
