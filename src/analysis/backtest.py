"""
统一回测引擎
============
将回测核心逻辑抽象为可复用模块，替代 scripts/ 中多个碎片化的回测脚本。

提供:
- BacktestEngine: 完整的因子回测引擎，支持调仓模拟和绩效评估
- StopLossEngine: 持仓期间止损监控引擎
"""
import math
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class RebalanceFrequency(Enum):
    """调仓频率"""
    DAILY = 1
    WEEKLY = 5
    BIWEEKLY = 10
    MONTHLY = 21


class AllocationMethod(Enum):
    """持仓分配方式"""
    EQUAL_WEIGHT = "equal_weight"
    FACTOR_WEIGHT = "factor_weight"


@dataclass
class BacktestConfig:
    """回测配置"""
    # 手续费参数
    commission_rate: float = 0.0003   # 万分之三
    min_commission: float = 5.0       # 最低佣金5元
    stamp_tax_rate: float = 0.001     # 千分之一印花税（卖出）
    slippage: float = 0.001           # 滑点0.1%

    # 调仓参数
    rebalance_freq: RebalanceFrequency = RebalanceFrequency.WEEKLY
    top_n: int = 5                    # 持仓数量
    max_position: float = 0.25        # 单ETF最大仓位
    budget: float = 1.0               # 总预算（1.0 = 满仓）
    allocation: AllocationMethod = AllocationMethod.EQUAL_WEIGHT

    # 基准
    benchmark_code: str = "510300.SH"

    # 回测时间范围
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    # 市场时机调整（与 recommendation_engine.py 联动）
    market_timing_adjustment: float = 0.0


@dataclass
class BacktestResult:
    """回测结果"""
    # 收益率序列
    portfolio_returns: pd.Series
    benchmark_returns: pd.Series

    # 累计净值
    portfolio_nav: pd.Series
    benchmark_nav: pd.Series

    # 性能指标
    total_return: float
    annualized_return: float
    annualized_volatility: float
    sharpe_ratio: float
    max_drawdown: float
    calmar_ratio: float
    win_rate: float
    total_trades: int
    avg_holding_period: float

    # 调仓记录
    trades: pd.DataFrame = field(default_factory=pd.DataFrame)

    # 每日持仓
    positions: pd.DataFrame = field(default_factory=pd.DataFrame)


class BacktestEngine:
    """
    统一回测引擎

    对因子信号进行历史回测，模拟调仓交易并计算绩效指标。

    使用方式:
        config = BacktestConfig(top_n=5, rebalance_freq=RebalanceFrequency.WEEKLY)
        engine = BacktestEngine(config)
        result = engine.run(factor_data, price_data)
    """

    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()

    def run(self, factor_data: pd.DataFrame,
            price_data: pd.DataFrame) -> BacktestResult:
        """
        运行完整回测。

        参数:
            factor_data: DataFrame, 必须包含列 [date, code, factor_score]。
                         每个 (date, code) 代表该 ETF 在该交易日的因子得分。
            price_data:  DataFrame, 必须包含列 [date, code, close]。
                         close 为复权收盘价，用于计算日收益率。

        返回:
            BacktestResult 包含完整回测结果。
        """
        # ── 验证输入 ──
        _validate_columns(factor_data, ["date", "code", "factor_score"])
        _validate_columns(price_data, ["date", "code", "close"])

        # ── 1. 对齐交易日期 ──
        factor_dates = sorted(factor_data["date"].unique())
        price_dates = sorted(price_data["date"].unique())
        all_dates = sorted(set(factor_dates) & set(price_dates))

        if len(all_dates) < 2:
            raise ValueError(
                "Insufficient overlapping dates between factor_data and price_data"
            )

        # 应用回测期过滤
        if self.config.start_date:
            all_dates = [d for d in all_dates if d >= self.config.start_date]
        if self.config.end_date:
            all_dates = [d for d in all_dates if d <= self.config.end_date]

        if len(all_dates) < 2:
            raise ValueError("No data in the specified date range")

        # ── 2. 构建收益率矩阵和因子矩阵 ──
        price_pivot = price_data.pivot(index="date", columns="code", values="close")
        price_pivot = price_pivot.sort_index()

        # 日收益率
        ret_matrix = price_pivot.pct_change().loc[all_dates]

        # 因子得分矩阵
        factor_pivot = factor_data.pivot(
            index="date", columns="code", values="factor_score"
        )
        factor_pivot = factor_pivot.sort_index().loc[all_dates]

        # ── 3. 模拟交易 ──
        portfolio_returns, trades, positions = self._simulate_trading(
            factor_pivot, ret_matrix, all_dates
        )

        # ── 4. 基准收益率 ──
        if self.config.benchmark_code in price_pivot.columns:
            bench_close = price_pivot[self.config.benchmark_code]
            benchmark_returns = bench_close.pct_change().loc[all_dates]
        else:
            logger.warning(
                "Benchmark code %s not found in price_data; using zero returns",
                self.config.benchmark_code,
            )
            benchmark_returns = pd.Series(0.0, index=all_dates)

        # ── 5. 计算绩效指标 ──
        metrics = self._compute_metrics(portfolio_returns, benchmark_returns)

        # ── 6. 构建累计净值 ──
        portfolio_nav = (1 + portfolio_returns).cumprod()
        benchmark_nav = (1 + benchmark_returns).cumprod()

        return BacktestResult(
            portfolio_returns=portfolio_returns,
            benchmark_returns=benchmark_returns,
            portfolio_nav=portfolio_nav,
            benchmark_nav=benchmark_nav,
            total_return=metrics["total_return"],
            annualized_return=metrics["annualized_return"],
            annualized_volatility=metrics["annualized_volatility"],
            sharpe_ratio=metrics["sharpe_ratio"],
            max_drawdown=metrics["max_drawdown"],
            calmar_ratio=metrics["calmar_ratio"],
            win_rate=metrics["win_rate"],
            total_trades=metrics["total_trades"],
            avg_holding_period=metrics["avg_holding_period"],
            trades=trades,
            positions=positions,
        )

    def _simulate_trading(
        self,
        factor_pivot: pd.DataFrame,
        ret_matrix: pd.DataFrame,
        all_dates: List[str],
    ) -> Tuple[pd.Series, pd.DataFrame, pd.DataFrame]:
        """
        模拟调仓交易。

        调仓日逻辑:
          1. 使用前一交易日（T-1）的因子得分选择 Top-N ETF
          2. 按配置方式分配权重（等权/因子加权）
          3. 计算买入/卖出产生的佣金和滑点
          4. 非调仓日持有不动，按权重计算组合收益

        返回:
            (portfolio_returns, trades_df, positions_df)
        """
        interval = self.config.rebalance_freq.value
        budget = self.config.budget
        top_n = self.config.top_n
        max_pos = self.config.max_position
        allocation = self.config.allocation

        # 调仓日索引
        rebalance_indices = set(range(0, len(all_dates), interval))
        # 剔除第一个日期（无前一交易日信号）
        rebalance_indices.discard(0)

        portfolio_returns = pd.Series(0.0, index=all_dates)
        current_weights: Dict[str, float] = {}
        trades_records = []
        position_records = []

        for i, t in enumerate(all_dates):
            # ── 调仓日：基于 T-1 信号重新构建组合 ──
            if i in rebalance_indices:
                prev_t = all_dates[i - 1]
                if prev_t in factor_pivot.index:
                    factors = factor_pivot.loc[prev_t].dropna()
                    if len(factors) >= 1:
                        # 选择 Top-N
                        selected = factors.nlargest(min(top_n, len(factors)))

                        # 分配权重
                        if allocation == AllocationMethod.FACTOR_WEIGHT:
                            total_score = max(selected.sum(), 1e-6)
                            raw_weights = (selected / total_score * budget).to_dict()
                        else:
                            # EQUAL_WEIGHT: 等权
                            eq_weight = budget / len(selected)
                            raw_weights = {code: eq_weight for code in selected.index}

                        # 应用单ETF仓位上限
                        new_weights = {}
                        for code, w in raw_weights.items():
                            new_weights[code] = min(w, max_pos)

                        # 检查是否需要再平衡剩余预算
                        total_alloc = sum(new_weights.values())
                        if total_alloc < budget - 1e-8 and len(new_weights) > 0:
                            # 将剩余预算按比例分配到已有仓位
                            shortfall = budget - total_alloc
                            for code in new_weights:
                                new_weights[code] += shortfall / len(new_weights)
                                new_weights[code] = min(new_weights[code], max_pos)

                        # ── 交易记录与成本计算 ──
                        old_codes = set(current_weights.keys())
                        new_codes = set(new_weights.keys())

                        turnover = 0.0
                        # 卖出（收印花税）
                        for code in old_codes - new_codes:
                            turnover += current_weights[code]
                        # 减少仓位（卖出部分）
                        for code in old_codes & new_codes:
                            diff = abs(new_weights[code] - current_weights[code])
                            if new_weights[code] < current_weights[code]:
                                turnover += diff
                            else:
                                turnover += diff

                        # 交易成本 = 佣金 + 印花税(仅卖出) + 滑点
                        commission = turnover * self.config.commission_rate
                        commission = max(commission, self.config.min_commission * turnover)
                        stamp_tax = sum(
                            current_weights[code]
                            for code in old_codes - new_codes
                            if code in old_codes
                        ) * self.config.stamp_tax_rate
                        slippage_cost = turnover * self.config.slippage

                        trade_cost = commission + stamp_tax + slippage_cost

                        trades_records.append({
                            "date": t,
                            "signal_date": prev_t,
                            "turnover": turnover,
                            "commission": commission,
                            "stamp_tax": stamp_tax,
                            "slippage": slippage_cost,
                            "total_cost": trade_cost,
                            "holdings": list(new_weights.keys()),
                            "weights": new_weights,
                        })

                        current_weights = new_weights

            # ── 非调仓日：记录持仓 ──
            if current_weights and i in rebalance_indices or (i not in rebalance_indices and current_weights):
                position_records.append({
                    "date": t,
                    **{code: w for code, w in current_weights.items()},
                })

            # ── 计算当日组合收益 ──
            if current_weights and t in ret_matrix.index:
                daily_ret = 0.0
                for code, weight in current_weights.items():
                    if code in ret_matrix.columns:
                        r = ret_matrix.loc[t, code]
                        if not (np.isnan(r) or np.isinf(r)):
                            daily_ret += weight * r

                # 扣除交易成本（调仓日从当日收益中扣除）
                trade_cost = 0.0
                if i in rebalance_indices and trades_records:
                    trade_cost = trades_records[-1]["total_cost"]
                portfolio_returns[t] = daily_ret - trade_cost
            else:
                portfolio_returns[t] = 0.0

        # 构建 DataFrame
        trades_df = pd.DataFrame(trades_records) if trades_records else pd.DataFrame()
        pos_df = pd.DataFrame(position_records) if position_records else pd.DataFrame()
        if not pos_df.empty:
            pos_df = pos_df.set_index("date").fillna(0.0)

        return portfolio_returns, trades_df, pos_df

    def _compute_metrics(
        self,
        portfolio_returns: pd.Series,
        benchmark_returns: pd.Series,
        risk_free_rate: float = 0.02,
    ) -> dict:
        """计算回测绩效指标。"""
        n = len(portfolio_returns)
        if n < 2:
            return {
                "total_return": 0.0,
                "annualized_return": 0.0,
                "annualized_volatility": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "calmar_ratio": 0.0,
                "win_rate": 0.0,
                "total_trades": 0,
                "avg_holding_period": 0.0,
            }

        # 累计收益率
        total_return = float((1 + portfolio_returns).prod() - 1)

        # 年化收益率
        ann_ret = (1 + total_return) ** (252 / n) - 1 if n > 0 else 0.0

        # 年化波动率
        ann_vol = float(portfolio_returns.std() * math.sqrt(252))

        # Sharpe Ratio
        rf_daily = risk_free_rate / 252
        excess = portfolio_returns - rf_daily
        if ann_vol > 0:
            sharpe = float(excess.mean() / excess.std() * math.sqrt(252))
        else:
            sharpe = 0.0

        # 最大回撤
        cum_series = (1 + portfolio_returns).cumprod()
        running_max = cum_series.cummax()
        drawdown = (cum_series - running_max) / running_max
        max_dd = float(drawdown.min())

        # Calmar Ratio
        calmar = ann_ret / abs(max_dd) if max_dd != 0 else float("inf")

        # 日胜率
        win_rate = float((portfolio_returns > 0).mean())

        # 交易统计（从 trades DataFrame 获取）
        total_trades = 0
        avg_holding_period = 0.0

        return {
            "total_return": total_return,
            "annualized_return": ann_ret,
            "annualized_volatility": ann_vol,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_dd,
            "calmar_ratio": calmar,
            "win_rate": win_rate,
            "total_trades": total_trades,
            "avg_holding_period": avg_holding_period,
        }


# ════════════════════════════════════════════════════════════
#  StopLossEngine
# ════════════════════════════════════════════════════════════

class StopLossEngine:
    """
    止损引擎

    在持仓期间监控损失，当单ETF亏损达到阈值时触发减仓信号。
    支持固定止损、浮动止损（trailing stop）两种模式。

    使用方式:
        engine = StopLossEngine()
        signals = engine.check_stop_loss(
            positions={"512480.SH": 0.2},
            current_prices={"512480.SH": 1.5},
            entry_prices={"512480.SH": 1.6},
        )
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {
            "stop_loss_threshold": -0.05,          # 止损线 -5%
            "position_reduction_ratio": 0.5,        # 触发止损后减仓50%
            "max_loss": -0.10,                      # 硬止损线 -10%
            "trailing_stop_activation": 0.05,       # 浮动止损激活阈值 +5%
            "trailing_stop_distance": 0.03,         # 浮动止损距离 3%
        }

    def check_stop_loss(
        self,
        positions: Dict[str, float],
        current_prices: Dict[str, float],
        entry_prices: Dict[str, float],
        high_prices: Optional[Dict[str, float]] = None,
    ) -> Dict[str, dict]:
        """
        检查止损信号。

        参数:
            positions:      {code: current_weight} 当前持仓权重
            current_prices: {code: current_price} 当前价格
            entry_prices:   {code: entry_price} 入场价格
            high_prices:    {code: highest_price_since_entry} 入场后最高价
                            （用于浮动止损计算）；若为 None 则仅使用固定止损。

        返回:
            {code: {
                "action": str,               # "hold" / "reduce" / "liquidate"
                "current_loss": float,        # 当前亏损比例
                "suggested_reduction": float,  # 建议减仓比例
                "reason": str,                # 触发原因
            }}
        """
        signals = {}
        high_prices = high_prices or {}

        for code in positions:
            if code not in current_prices or code not in entry_prices:
                signals[code] = {
                    "action": "hold",
                    "current_loss": 0.0,
                    "suggested_reduction": 0.0,
                    "reason": "Missing price data",
                }
                continue

            current_price = current_prices[code]
            entry_price = entry_prices[code]

            if entry_price <= 0:
                signals[code] = {
                    "action": "hold",
                    "current_loss": 0.0,
                    "suggested_reduction": 0.0,
                    "reason": "Invalid entry price",
                }
                continue

            # 当前亏损比例
            current_loss = current_price / entry_price - 1

            threshold = self.config["stop_loss_threshold"]
            max_loss = self.config["max_loss"]
            reduction_ratio = self.config["position_reduction_ratio"]

            # ── 硬止损：亏损超过 max_loss ──
            if current_loss <= max_loss:
                signals[code] = {
                    "action": "liquidate",
                    "current_loss": current_loss,
                    "suggested_reduction": 1.0,
                    "reason": (
                        f"Hard stop-loss triggered: loss={current_loss:.1%}, "
                        f"threshold={max_loss:.1%}"
                    ),
                }
                continue

            # ── 浮动止损 ──
            if code in high_prices and high_prices[code] is not None:
                highest = high_prices[code]
                activation = self.config["trailing_stop_activation"]
                distance = self.config["trailing_stop_distance"]

                # 从入场价到最高价的涨幅
                run_up = highest / entry_price - 1

                # 仅当涨幅超过激活阈值时才启用浮动止损
                if run_up >= activation:
                    # 当前价格相对于最高点的回撤
                    pullback = 1 - current_price / highest

                    if pullback >= distance:
                        signals[code] = {
                            "action": "reduce",
                            "current_loss": current_loss,
                            "suggested_reduction": reduction_ratio,
                            "reason": (
                                f"Trailing stop triggered: pullback={pullback:.1%} "
                                f"from high={highest:.4f}, distance={distance:.1%}"
                            ),
                        }
                        continue

            # ── 固定止损 ──
            if current_loss <= threshold:
                signals[code] = {
                    "action": "reduce",
                    "current_loss": current_loss,
                    "suggested_reduction": reduction_ratio,
                    "reason": (
                        f"Stop-loss triggered: loss={current_loss:.1%}, "
                        f"threshold={threshold:.1%}"
                    ),
                }
                continue

            # ── 无止损信号 ──
            signals[code] = {
                "action": "hold",
                "current_loss": current_loss,
                "suggested_reduction": 0.0,
                "reason": "No stop-loss signal",
            }

        return signals


# ════════════════════════════════════════════════════════════
#  Internal helpers
# ════════════════════════════════════════════════════════════

def _validate_columns(df: pd.DataFrame, required: List[str]):
    """验证 DataFrame 包含必需的列。"""
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"DataFrame missing required columns: {missing}. "
            f"Available columns: {list(df.columns)}"
        )