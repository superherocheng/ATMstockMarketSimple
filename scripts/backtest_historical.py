"""
历史区间因子回测脚本
==================
从 Tushare 抓取指定区间的 ETF 行情和份额数据，
在内存中计算因子并回测，不写入数据库。

用法:
    cd ATMstockMarketSimple
    python scripts/backtest_historical.py
"""
import sys
import math
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
import tushare as ts

# ── Configuration ──
START_DATE = "20230101"
END_DATE = "20240801"
DATA_START = "20220601"  # Extra lookback for factor computation
TOP_N = 5
REBALANCE_INTERVAL = 10
BENCHMARK_CODE = "510500.SH"
RISK_FREE_RATE = 0.02

SECTOR_ETF = {
    "512480.SH": "半导体ETF",
    "515030.SH": "新能源车ETF",
    "512010.SH": "医药ETF",
    "512800.SH": "银行ETF",
    "512880.SH": "证券ETF",
    "159928.SZ": "消费ETF",
    "515880.SH": "通信ETF",
    "159206.SZ": "卫星ETF",
    "512400.SH": "有色ETF",
    "562500.SH": "机器人ETF",
    "159870.SZ": "化工ETF",
    "561360.SH": "石油ETF",
    "159611.SZ": "电力ETF",
    "512980.SH": "传媒ETF",
}

PRESET = {
    "flow_lookback": 10,
    "mom_lookback": 20,
}


def fetch_data(token):
    """从 Tushare 抓取历史数据"""
    ts.set_token(token)
    pro = ts.pro_api()

    print(f"Fetching sector ETF daily data ({DATA_START} ~ {END_DATE})...")
    kline_parts = []
    for code in SECTOR_ETF:
        for _ in range(3):
            try:
                df = pro.fund_daily(ts_code=code, start_date=DATA_START, end_date=END_DATE)
                if df is not None and len(df) > 0:
                    kline_parts.append(df)
                break
            except Exception as e:
                print(f"  Retry {code}: {e}")
                time.sleep(1)
        time.sleep(0.3)

    kline_df = pd.concat(kline_parts, ignore_index=True) if kline_parts else pd.DataFrame()
    kline_df = kline_df.sort_values(["ts_code", "trade_date"]).reset_index(drop=True)
    print(f"  Sector ETF kline: {len(kline_df)} rows, {kline_df['trade_date'].nunique()} dates")

    print(f"Fetching ETF share data ({DATA_START} ~ {END_DATE})...")
    share_parts = []
    for code in SECTOR_ETF:
        for _ in range(3):
            try:
                df = pro.fund_share(ts_code=code, start_date=DATA_START, end_date=END_DATE)
                if df is not None and len(df) > 0:
                    share_parts.append(df)
                break
            except Exception as e:
                print(f"  Retry {code} share: {e}")
                time.sleep(1)
        time.sleep(0.3)

    share_df = pd.concat(share_parts, ignore_index=True) if share_parts else pd.DataFrame()
    if not share_df.empty:
        share_df = share_df.sort_values(["ts_code", "trade_date"]).reset_index(drop=True)
    print(f"  ETF share: {len(share_df)} rows")

    print(f"Fetching benchmark CSI 500 ({DATA_START} ~ {END_DATE})...")
    bench_df = pro.fund_daily(ts_code=BENCHMARK_CODE, start_date=DATA_START, end_date=END_DATE)
    bench_df = bench_df.sort_values("trade_date").reset_index(drop=True)
    print(f"  Benchmark: {len(bench_df)} rows")

    return kline_df, share_df, bench_df


# ── Factor computation (same logic as factor_engine.py) ──

def _compute_flow_ewma(shares, lookback, halflife=3):
    if len(shares) < lookback + 1:
        return np.nan
    recent = shares.iloc[-lookback:].astype(float).values
    if len(recent) < 2:
        return np.nan
    x = np.arange(len(recent), dtype=float)
    y = recent / recent.mean()
    if np.isnan(y).any():
        return np.nan
    weights = np.exp(-np.log(2) * (len(recent) - 1 - x) / halflife)
    weights /= weights.sum()
    x_w = x - (x * weights).sum()
    y_w = y - (y * weights).sum()
    denom = (weights * x_w * x_w).sum()
    if denom == 0:
        return np.nan
    slope = (weights * x_w * y_w).sum() / denom
    return float(np.tanh(slope * 3))


def _compute_mom(closes, lookback, vol_window=60):
    if len(closes) < lookback + 1:
        return np.nan
    close_today = float(closes.iloc[-1])
    close_past = float(closes.iloc[-(lookback + 1)])
    if close_past == 0:
        return np.nan
    mom = close_today / close_past - 1
    if len(closes) >= vol_window + 1:
        daily_ret = closes.astype(float).pct_change().dropna().tail(vol_window)
        if len(daily_ret) >= 30:
            vol = daily_ret.std()
            if vol > 0:
                return float(mom / vol)
    return float(mom)


def _cross_sectional_zscore(values):
    p10 = values.quantile(0.10)
    p90 = values.quantile(0.90)
    clipped = values.clip(p10, p90)
    std = clipped.std()
    if std == 0 or pd.isna(std):
        return pd.Series(0.0, index=values.index)
    return (clipped - clipped.mean()) / std


def compute_factors(kline_df, share_df):
    """Compute factor values for all dates in kline_df"""
    flow_lb = PRESET["flow_lookback"]
    mom_lb = PRESET["mom_lookback"]
    lookback_needed = max(flow_lb, mom_lb) + 1

    all_dates = sorted(kline_df["trade_date"].unique())

    # Find first computable date
    computable_dates = []
    for d in all_dates:
        history = kline_df[kline_df["trade_date"] <= d]
        if len(history) > 0:
            max_len = history.groupby("ts_code").size().max()
            if max_len >= lookback_needed:
                computable_dates.append(d)

    print(f"  Computing factors for {len(computable_dates)} dates...")

    factor_rows = []
    for i, d in enumerate(computable_dates):
        etf_codes = kline_df["ts_code"].unique()
        day_rows = []

        for code in etf_codes:
            etf_kline = kline_df[(kline_df["ts_code"] == code) & (kline_df["trade_date"] <= d)].sort_values("trade_date")
            etf_shares = share_df[(share_df["ts_code"] == code) & (share_df["trade_date"] <= d)].sort_values("trade_date")

            if len(etf_kline) < lookback_needed or len(etf_shares) < flow_lb:
                continue

            flow = _compute_flow_ewma(etf_shares["fd_share"], flow_lb)
            mom = _compute_mom(etf_kline["close"], mom_lb)

            if pd.isna(flow) or pd.isna(mom):
                continue

            day_rows.append({"etf_code": code, "trade_date": d, "flow": flow, "mom": mom})

        if len(day_rows) < 2:
            continue

        day_df = pd.DataFrame(day_rows)
        day_df["z_flow"] = _cross_sectional_zscore(day_df["flow"]).values
        day_df["z_mom"] = _cross_sectional_zscore(day_df["mom"]).values
        day_df["factor"] = 0.3 * day_df["z_flow"] + 0.7 * day_df["z_mom"]
        day_df["quadrant"] = day_df.apply(
            lambda r: 1 if r["z_flow"] >= 0 and r["z_mom"] >= 0
            else 2 if r["z_flow"] >= 0 and r["z_mom"] < 0
            else 3 if r["z_flow"] < 0 and r["z_mom"] < 0
            else 4, axis=1
        )
        factor_rows.extend(day_df.to_dict("records"))

        if (i + 1) % 50 == 0:
            print(f"    {i+1}/{len(computable_dates)} dates done")

    print(f"  Factor rows computed: {len(factor_rows)}")
    return pd.DataFrame(factor_rows)


def _compute_rsi(closes, period=14):
    deltas = np.diff(closes.astype(float))
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.convolve(gains, np.ones(period) / period, mode="valid")
    avg_loss = np.convolve(losses, np.ones(period) / period, mode="valid")
    rs = avg_gain / np.where(avg_loss == 0, 1e-10, avg_loss)
    rsi = 100 - 100 / (1 + rs)
    return float(rsi[-1]) if len(rsi) > 0 else 50.0


def _compute_market_timing(bench_kline, date):
    """Simplified market timing matching market_timing.py logic."""
    kl = bench_kline[bench_kline["trade_date"] <= date].tail(40)
    if len(kl) < 21:
        return 0.0
    closes = kl["close"].astype(float).values
    if len(closes) < 21:
        return 0.0

    # RSI score
    rsi = _compute_rsi(closes, 14)
    rsi_score = 0.0
    if rsi < 40:
        rsi_score = min(0.5, (40 - rsi) / 40 * 0.5)
    elif rsi > 75:
        rsi_score = -min(0.2, (rsi - 75) / 25 * 0.2)

    # Momentum score
    mom_20 = closes[-1] / closes[-21] - 1 if len(closes) >= 21 else 0
    mom_score = 0.0
    if mom_20 > 0.08:
        mom_score = -min(0.3, (mom_20 - 0.08) / 0.10 * 0.3)
    elif mom_20 < -0.08:
        mom_score = min(0.3, (abs(mom_20) - 0.08) / 0.10 * 0.3)

    raw_score = max(-1.0, min(1.0, rsi_score + mom_score))
    return raw_score * 0.3  # adjustment in [-0.3, +0.3]


def _correlation_penalty(code, selected, corr_matrix):
    """Correlation penalty matching recommendation_engine.py."""
    if not selected or code not in corr_matrix.index:
        return 1.0
    max_corr = 0.0
    for sel in selected:
        if sel in corr_matrix.columns and code in corr_matrix.index:
            c = abs(corr_matrix.loc[code, sel])
            if not np.isnan(c):
                max_corr = max(max_corr, c)
    if max_corr > 0.7:
        return 0.3
    elif max_corr > 0.6:
        return 0.5
    elif max_corr > 0.5:
        return 0.7
    return 1.0


def run_backtest(factor_df, kline_df, bench_df):
    """Core backtest loop matching recommendation engine logic."""
    ret_matrix = kline_df.pivot(index="trade_date", columns="ts_code", values="pct_chg")
    ret_matrix = (ret_matrix / 100.0).sort_index()

    factor_pivot = factor_df.pivot(index="trade_date", columns="etf_code", values="factor")
    factor_pivot = factor_pivot.sort_index()

    # Also need quadrant data
    quad_pivot = factor_df.pivot(index="trade_date", columns="etf_code", values="quadrant")
    quad_pivot = quad_pivot.sort_index()

    bench_ret = (bench_df.set_index("trade_date")["pct_chg"] / 100.0).sort_index()

    # Compute ETF return correlation matrix for penalty
    corr_matrix = ret_matrix.corr()

    all_dates = sorted(
        set(ret_matrix.index) & set(factor_pivot.index) & set(bench_ret.index)
    )
    all_dates = [d for d in all_dates if START_DATE <= d <= END_DATE]

    if not all_dates:
        print("ERROR: No overlapping dates in the target range!")
        return None, None, []

    rebalance_dates = all_dates[::REBALANCE_INTERVAL]
    rebalance_set = set(rebalance_dates)

    current_weights = {}  # code -> weight
    strat_rets = []
    bench_rets = []
    holdings_log = []

    for i, t in enumerate(all_dates):
        if t in rebalance_set and i > 0:
            prev_t = all_dates[i - 1]
            if prev_t in factor_pivot.index and prev_t in quad_pivot.index:
                factors_prev = factor_pivot.loc[prev_t]
                quads_prev = quad_pivot.loc[prev_t]

                # Select Q1 + Q2 only (matching recommendation engine)
                candidates = []
                for code in factors_prev.index:
                    if pd.isna(factors_prev[code]) or pd.isna(quads_prev[code]):
                        continue
                    q = int(quads_prev[code])
                    if q not in (1, 2):
                        continue
                    quad_mult = 1.0 if q == 1 else 0.7
                    candidates.append({
                        "code": code, "factor": float(factors_prev[code]),
                        "quadrant": q, "quad_mult": quad_mult,
                    })

                if not candidates:
                    pass  # keep previous weights (go to cash if empty)
                else:
                    # Score with correlation penalty
                    scored = []
                    selected_codes = []
                    for c in sorted(candidates, key=lambda x: -abs(x["factor"])):
                        score = abs(c["factor"]) * c["quad_mult"] * _correlation_penalty(c["code"], selected_codes, corr_matrix)
                        scored.append((c, score))
                        selected_codes.append(c["code"])

                    # Top 5 max
                    scored = sorted(scored, key=lambda x: -x[1])[:TOP_N]

                    # Market timing
                    timing_adj = _compute_market_timing(bench_df, prev_t)
                    total_budget = max(0.3, min(1.3, 1.0 + timing_adj))

                    # Position sizing: Q1=60%, Q2=40%
                    q1_items = [(c, s) for c, s in scored if c["quadrant"] == 1]
                    q2_items = [(c, s) for c, s in scored if c["quadrant"] == 2]

                    q1_budget = total_budget * 0.60
                    q2_budget = total_budget * 0.40

                    new_weights = {}
                    max_single = min(0.25, total_budget / max(len(scored), 1) + 0.05)

                    for items, budget in [(q1_items, q1_budget), (q2_items, q2_budget)]:
                        if not items:
                            continue
                        total_score = max(sum(s for _, s in items), 1e-6)
                        for c, s in items:
                            raw_w = budget * (s / total_score)
                            new_weights[c["code"]] = min(raw_w, max_single)

                    current_weights = new_weights
                    holdings_log.append((t, prev_t, {k: round(v, 3) for k, v in current_weights.items()}))

        # Compute portfolio return (weighted)
        if current_weights and t in ret_matrix.index:
            port_ret = 0.0
            for code, weight in current_weights.items():
                if code in ret_matrix.columns:
                    r = ret_matrix.loc[t, code]
                    if not np.isnan(r):
                        port_ret += weight * r
        else:
            port_ret = 0.0

        bm_ret = bench_ret.get(t, 0.0)
        strat_rets.append(port_ret)
        bench_rets.append(bm_ret)

    strat_series = pd.Series(strat_rets, index=all_dates, name="strategy")
    bench_series = pd.Series(bench_rets, index=all_dates, name="benchmark")

    return strat_series, bench_series, holdings_log


def compute_metrics(returns):
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
    sep = "=" * 70
    print()
    print(sep)
    print("  因子历史回测报告  Historical Factor Backtest")
    print(f"  策略: Top-{TOP_N} 行业ETF等权轮动 (因子: 0.3*z_flow + 0.7*z_mom)")
    print(f"  预设: short (flow=10d, mom=20d) | 调仓: 每{REBALANCE_INTERVAL}个交易日")
    print(f"  基准: 中证500 ETF ({BENCHMARK_CODE})")
    dates = strat_series.index.tolist()
    print(f"  回测期: {dates[0]} ~ {dates[-1]} ({strat_m['trading_days']}个交易日)")
    print(sep)

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

    strat_cum = (1 + strat_series).cumprod()
    bench_cum = (1 + bench_series).cumprod()
    print()
    print(f"  策略最终净值: {strat_cum.iloc[-1]:.4f}")
    print(f"  基准最终净值: {bench_cum.iloc[-1]:.4f}")
    if strat_cum.iloc[-1] > bench_cum.iloc[-1]:
        print(f"  >>> 策略跑赢基准 {(strat_cum.iloc[-1] - bench_cum.iloc[-1]) * 100:.2f}%")
    else:
        print(f"  >>> 策略跑输基准 {(bench_cum.iloc[-1] - strat_cum.iloc[-1]) * 100:.2f}%")

    # ASCII chart
    print()
    print("  累计收益曲线 (ASCII)")
    print("  " + "-" * 60)

    chart_height = 22
    chart_width = 55
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
    print(f"  {dates[0]}                       {dates[-1]}")
    print(f"  图例: * 策略   - 基准   X 重叠")

    # Rebalance log (show first 10)
    print()
    print(f"  调仓记录 (共{len(holdings_log)}次，展示前10次)")
    print("  " + "-" * 56)
    for date, signal_date, weights in holdings_log[:10]:
        items = [f"{SECTOR_ETF.get(c, c)}:{w*100:.0f}%" for c, w in weights.items()]
        print(f"  {date} (信号{signal_date})  {', '.join(items)}")
    if len(holdings_log) > 10:
        print(f"  ... 省略 {len(holdings_log) - 10} 次")

    print()
    print(sep)


def main():
    from dotenv import load_dotenv
    import os

    load_dotenv(PROJECT_ROOT / ".env")
    token = os.getenv("TUSHARE_TOKEN", "")
    if not token or token == "your_tushare_token_here":
        print("ERROR: TUSHARE_TOKEN not configured in .env")
        sys.exit(1)

    print(f"Backtest period: {START_DATE} ~ {END_DATE}")
    print(f"Data lookback from: {DATA_START} (for factor computation)")
    print()

    # Step 1: Fetch data
    kline_df, share_df, bench_df = fetch_data(token)

    # Step 2: Compute factors in-memory
    print("Computing factors...")
    factor_df = compute_factors(kline_df, share_df)

    if factor_df.empty:
        print("ERROR: No factor data computed. Check data availability.")
        sys.exit(1)

    # Step 3: Run backtest
    print("Running backtest...")
    strat_series, bench_series, holdings_log = run_backtest(factor_df, kline_df, bench_df)

    if strat_series is None:
        sys.exit(1)

    # Step 4: Report
    strat_m = compute_metrics(strat_series)
    bench_m = compute_metrics(bench_series)
    print_report(strat_m, bench_m, strat_series, bench_series, holdings_log)


if __name__ == "__main__":
    main()
