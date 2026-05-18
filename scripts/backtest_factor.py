"""
因子回测脚本
============
基于复合因子 (0.3*z_flow + 0.7*z_mom) 回测行业ETF轮动策略，对比中证500基准。

用法:
    cd ATMstockMarketSimple
    python scripts/backtest_factor.py
"""
import sys
import math
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

# ── Configuration ──
PRESET_ID = "short"
TOP_N = 5
REBALANCE_INTERVAL = 10
BENCHMARK_CODE = "510500.SH"
LOOKBACK_DAYS = 365
RISK_FREE_RATE = 0.02


def load_data(db):
    """从数据库加载因子信号、ETF行情、基准行情"""
    factor_df = db.query(
        "SELECT etf_code, trade_date, factor, z_flow, z_mom, quadrant "
        "FROM factor_daily WHERE preset_id = :pid ORDER BY etf_code, trade_date",
        {"pid": PRESET_ID}
    )

    price_df = db.query(
        "SELECT ts_code, trade_date, close, pct_chg "
        "FROM sector_etf_daily ORDER BY ts_code, trade_date"
    )

    bench_df = db.query(
        "SELECT ts_code, trade_date, close, pct_chg "
        "FROM index_etf_daily WHERE ts_code = :code ORDER BY trade_date",
        {"code": BENCHMARK_CODE}
    )

    if factor_df.empty or price_df.empty or bench_df.empty:
        print("ERROR: 缺少必要数据，请先运行因子计算和行情抓取。")
        sys.exit(1)

    # Normalize dates to YYYYMMDD strings
    for df, col in [(factor_df, "trade_date"), (price_df, "trade_date"), (bench_df, "trade_date")]:
        df[col] = df[col].apply(
            lambda d: str(d).replace("-", "") if hasattr(d, "strftime") else str(d)
        )

    # pct_chg: percentage -> decimal
    price_df["ret"] = price_df["pct_chg"].astype(float) / 100.0
    bench_df["ret"] = bench_df["pct_chg"].astype(float) / 100.0

    return factor_df, price_df, bench_df


def get_rebalance_dates(dates, interval):
    """从交易日列表中每隔 interval 个取一个调仓日"""
    return dates[::interval]


def run_backtest(factor_df, price_df, bench_df, rebalance_dates, top_n=TOP_N):
    """核心回测逻辑：每日遍历，调仓日选因子前N名ETF等权持有"""
    # Pivot daily returns: rows=trade_date, cols=ts_code
    ret_matrix = price_df.pivot(index="trade_date", columns="ts_code", values="ret")
    ret_matrix = ret_matrix.sort_index()

    # Factor pivot: rows=trade_date, cols=etf_code, values=factor
    factor_pivot = factor_df.pivot(index="trade_date", columns="etf_code", values="factor")
    factor_pivot = factor_pivot.sort_index()

    # Benchmark daily returns
    bench_ret = bench_df.set_index("trade_date")["ret"].sort_index()

    # Align all to common trading dates
    all_dates = sorted(set(ret_matrix.index) & set(factor_pivot.index) & set(bench_ret.index))

    # Restrict to last 1 year
    if len(all_dates) > LOOKBACK_DAYS:
        all_dates = all_dates[-LOOKBACK_DAYS:]

    # Build date -> previous_date mapping to prevent look-ahead bias.
    # Factor on date T uses T's close price and T's share data (both
    # available only AFTER T's close).  So we must use T-1's factor
    # signal to trade at T, earning T's return.
    date_idx_map = {d: i for i, d in enumerate(all_dates)}

    rebalance_dates = get_rebalance_dates(all_dates, REBALANCE_INTERVAL)
    rebalance_set = set(rebalance_dates)

    current_holdings = []
    strat_rets = []
    bench_rets = []
    holdings_log = []

    for i, t in enumerate(all_dates):
        # Rebalance: use PREVIOUS day's factor (T-1) to avoid look-ahead
        if t in rebalance_set and i > 0:
            prev_t = all_dates[i - 1]
            if prev_t in factor_pivot.index:
                factors_prev = factor_pivot.loc[prev_t].dropna()
                if len(factors_prev) >= top_n:
                    current_holdings = factors_prev.nlargest(top_n).index.tolist()
                    holdings_log.append((t, prev_t, list(current_holdings)))
                elif len(factors_prev) > 0 and not current_holdings:
                    current_holdings = factors_prev.nlargest(
                        min(top_n, len(factors_prev))
                    ).index.tolist()
                    holdings_log.append((t, prev_t, list(current_holdings)))

        # Compute portfolio return
        if current_holdings and t in ret_matrix.index:
            holdings_rets = ret_matrix.loc[t, ret_matrix.columns.isin(current_holdings)]
            valid = holdings_rets.dropna()
            if len(valid) > 0:
                port_ret = valid.mean()
            else:
                port_ret = 0.0
        else:
            port_ret = 0.0

        # Benchmark return
        bm_ret = bench_ret.get(t, 0.0)

        strat_rets.append(port_ret)
        bench_rets.append(bm_ret)

    dates_series = pd.Series(all_dates)
    strat_series = pd.Series(strat_rets, index=dates_series, name="strategy")
    bench_series = pd.Series(bench_rets, index=dates_series, name="benchmark")

    return strat_series, bench_series, holdings_log


def compute_metrics(returns, label=""):
    """计算回测性能指标"""
    n = len(returns)
    if n == 0:
        return {}

    cum_ret = (1 + returns).prod() - 1
    ann_ret = (1 + cum_ret) ** (252 / n) - 1 if n > 0 else 0
    ann_vol = returns.std() * math.sqrt(252)

    rf_daily = RISK_FREE_RATE / 252
    excess = returns - rf_daily
    sharpe = (excess.mean() / excess.std() * math.sqrt(252)) if excess.std() > 0 else 0

    cum_series = (1 + returns).cumprod()
    running_max = cum_series.cummax()
    drawdown = (cum_series - running_max) / running_max
    max_dd = drawdown.min()

    calmar = ann_ret / abs(max_dd) if max_dd != 0 else float('inf')
    win_rate = (returns > 0).mean()

    return {
        "label": label,
        "total_return": cum_ret,
        "annualized_return": ann_ret,
        "annual_volatility": ann_vol,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "calmar": calmar,
        "win_rate": win_rate,
        "trading_days": n,
    }


def print_report(strat_m, bench_m, strat_series, bench_series, holdings_log):
    """打印回测报告"""
    sep = "=" * 70
    print()
    print(sep)
    print("  因子回测报告  Factor Backtest Report")
    print(f"  策略: Top-{TOP_N} 行业ETF等权轮动 (因子: 0.3*z_flow + 0.7*z_mom)")
    print(f"  预设: {PRESET_ID} | 调仓: 每{REBALANCE_INTERVAL}个交易日")
    print(f"  基准: 中证500 ETF ({BENCHMARK_CODE})")
    dates = strat_series.index.tolist()
    print(f"  回测期: {dates[0]} ~ {dates[-1]} "
          f"({strat_m['trading_days']}个交易日)")
    print(sep)

    # Performance table
    print()
    print(f"  {'指标':<18} {'策略':>12} {'基准(中证500)':>14} {'超额':>10}")
    print("  " + "-" * 56)

    def fmt_pct(v):
        return f"{v*100:+.2f}%" if not math.isinf(v) else "N/A"

    def fmt_num(v):
        return f"{v:.3f}" if not math.isinf(v) else "N/A"

    rows = [
        ("累计收益率", "total_return", fmt_pct),
        ("年化收益率", "annualized_return", fmt_pct),
        ("年化波动率", "annual_volatility", fmt_pct),
        ("Sharpe Ratio", "sharpe", fmt_num),
        ("最大回撤", "max_drawdown", fmt_pct),
        ("Calmar Ratio", "calmar", fmt_num),
        ("日胜率", "win_rate", fmt_pct),
    ]

    for label, key, fmt in rows:
        sv = strat_m[key]
        bv = bench_m[key]
        diff = sv - bv
        print(f"  {label:<18} {fmt(sv):>12} {fmt(bv):>14} {fmt(diff):>10}")

    # Win/Lose summary
    strat_cum = (1 + strat_series).cumprod()
    bench_cum = (1 + bench_series).cumprod()
    print()
    print(f"  策略最终净值: {strat_cum.iloc[-1]:.4f}")
    print(f"  基准最终净值: {bench_cum.iloc[-1]:.4f}")
    if strat_cum.iloc[-1] > bench_cum.iloc[-1]:
        print(f"  >>> 策略跑赢基准 {(strat_cum.iloc[-1] - bench_cum.iloc[-1]) * 100:.2f}%")
    else:
        print(f"  >>> 策略跑输基准 {(bench_cum.iloc[-1] - strat_cum.iloc[-1]) * 100:.2f}%")

    # ASCII cumulative return chart
    print()
    print("  累计收益曲线 (ASCII)")
    print("  " + "-" * 60)

    chart_height = 20
    chart_width = 55

    # Downsample to chart_width points
    n_points = len(strat_cum)
    if n_points > chart_width:
        indices = np.linspace(0, n_points - 1, chart_width, dtype=int)
        strat_sampled = strat_cum.values[indices]
        bench_sampled = bench_cum.values[indices]
    else:
        strat_sampled = strat_cum.values
        bench_sampled = bench_cum.values
        chart_width = n_points

    all_vals = np.concatenate([strat_sampled, bench_sampled])
    vmin = all_vals.min()
    vmax = all_vals.max()
    vrange = vmax - vmin if vmax > vmin else 1

    grid = [[' ' for _ in range(chart_width)] for _ in range(chart_height)]

    for series, marker in [(bench_sampled, '-'), (strat_sampled, '*')]:
        for i, v in enumerate(series):
            col = i
            row = chart_height - 1 - int((v - vmin) / vrange * (chart_height - 1))
            row = max(0, min(chart_height - 1, row))
            if grid[row][col] == ' ':
                grid[row][col] = marker
            elif grid[row][col] != marker:
                grid[row][col] = 'X'

    for row in grid:
        print("  " + ''.join(row))

    print(f"  {vmin:.2f}" + " " * (chart_width - 12) + f"{vmax:.2f}")
    print(f"  {strat_series.index[0]}                       {strat_series.index[-1]}")
    print(f"  图例: * 策略   - 基准   X 重叠")

    # Rebalance history
    print()
    print(f"  调仓记录 (共{len(holdings_log)}次)")
    print("  " + "-" * 56)
    from config.config import SECTOR_ETF
    for date, signal_date, holdings in holdings_log:
        names = [SECTOR_ETF.get(c, c) for c in holdings]
        print(f"  {date} (信号来自{signal_date})  {', '.join(names)}")

    print()
    print(sep)


def main():
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")

    import os
    from src.core.db_manager_postgresql import init_db_manager, close_db_manager

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set. Check .env file.")
        sys.exit(1)

    db = init_db_manager(db_url)

    try:
        print("Loading data...")
        factor_df, price_df, bench_df = load_data(db)

        print(f"  Factor records: {len(factor_df)}")
        print(f"  Price records:  {len(price_df)}")
        print(f"  Benchmark recs: {len(bench_df)}")

        print("Running backtest...")
        strat_series, bench_series, holdings_log = run_backtest(
            factor_df, price_df, bench_df,
            get_rebalance_dates([], REBALANCE_INTERVAL),
        )

        strat_m = compute_metrics(strat_series, "Strategy")
        bench_m = compute_metrics(bench_series, "Benchmark")

        print_report(strat_m, bench_m, strat_series, bench_series, holdings_log)

    finally:
        close_db_manager()


if __name__ == "__main__":
    main()
