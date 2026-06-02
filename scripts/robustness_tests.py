"""Robustness Test Suite: 3 sequential goals with hard stop on failure.

Goal 1: 6-month rolling window pressure test (ICIR≥0.65, WR≥70%, max drawdown≤0.30)
Goal 2: Transaction cost erosion test (0.10% one-way, excess return≥15%, Sharpe≥1.2, turnover≤200%)
Goal 3: Generalization test on expanded ETF pool (data permitting)
"""
import sys
import os
import warnings
import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MIN_ETF = 8
H = 15
WEIGHTS = {"z_rsrs": 0.38, "z_flow": 0.22, "z_mom": 0.32, "z_quality": 0.0, "z_efficiency": 0.0, "z_rsi_momentum": 0.08}
COST_ONE_WAY = 0.001  # 0.10%


def _init_db():
    from dotenv import load_dotenv
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(project_root, ".env"))
    from src.core.db_manager_postgresql import init_db_manager
    init_db_manager(os.getenv("DATABASE_URL"))


def _spearman_ic(x, y):
    valid = pd.notna(x) & pd.notna(y)
    x, y = x[valid], y[valid]
    if len(x) < MIN_ETF:
        return np.nan
    corr, _ = scipy_stats.spearmanr(x, y)
    return float(corr) if not np.isnan(corr) else np.nan


def fetch_data():
    from sqlalchemy import text
    from src.core.db_manager_postgresql import get_conn
    conn = get_conn()
    try:
        factor_rows = conn.execute(text(
            "SELECT etf_code, trade_date, factor, quadrant, "
            "z_rsrs, z_flow, z_mom, z_quality, z_efficiency, z_rsi_momentum "
            "FROM factor_daily WHERE preset_id = 'optimized' ORDER BY trade_date"
        )).fetchall()
        price_rows = conn.execute(text(
            "SELECT ts_code, trade_date, close FROM sector_etf_daily ORDER BY ts_code, trade_date"
        )).fetchall()
    finally:
        conn.close()

    factor_df = pd.DataFrame(factor_rows, columns=[
        "etf_code", "trade_date", "factor", "quadrant",
        "z_rsrs", "z_flow", "z_mom", "z_quality", "z_efficiency", "z_rsi_momentum"])
    price_df = pd.DataFrame(price_rows, columns=["ts_code", "trade_date", "close"])

    for df in [factor_df, price_df]:
        df["trade_date"] = df["trade_date"].apply(
            lambda d: str(d).replace("-", "") if hasattr(d, "strftime") else str(d))
    price_df["close"] = price_df["close"].astype(float)

    price_lookup = {(r["ts_code"], r["trade_date"]): r["close"] for _, r in price_df.iterrows()}
    all_dates = sorted(price_df["trade_date"].unique())
    date_idx = {d: i for i, d in enumerate(all_dates)}

    return factor_df, price_lookup, all_dates, date_idx


def build_daily_df(factor_df, price_lookup, all_dates, date_idx):
    """Build daily-level DataFrame with factor scores and forward returns."""
    rows = []
    for t in sorted(factor_df["trade_date"].unique()):
        if t not in date_idx:
            continue
        idx = date_idx[t]
        if idx + 1 + H >= len(all_dates):
            continue
        entry, exit_d = all_dates[idx + 1], all_dates[idx + 1 + H]
        day = factor_df[factor_df["trade_date"] == t]
        for _, row in day.iterrows():
            c_e = price_lookup.get((row["etf_code"], entry))
            c_x = price_lookup.get((row["etf_code"], exit_d))
            if c_e and c_x and c_e > 0:
                rows.append({
                    "etf_code": row["etf_code"], "trade_date": t,
                    "forward_ret": c_x / c_e - 1,
                    "factor": row["factor"], "quadrant": row["quadrant"],
                    **{c: row[c] for c in ["z_rsrs", "z_flow", "z_mom", "z_quality", "z_efficiency", "z_rsi_momentum"]},
                })
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════
#  GOAL 1: 6-Month Rolling Window Pressure Test
# ═══════════════════════════════════════════════════════════
def goal1(df):
    print("=" * 80)
    print("  GOAL 1: 6-MONTH ROLLING WINDOW PRESSURE TEST")
    print("=" * 80)

    df["date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    all_d = sorted(df["date"].unique())
    print(f"  Data range: {all_d[0].strftime('%Y-%m-%d')} to {all_d[-1].strftime('%Y-%m-%d')}")
    print(f"  Total trading days: {len(all_d)}, ETFs: {df['etf_code'].nunique()}")

    # 6-month rolling windows, 1-month step
    window_months = 6
    step_months = 1
    windows = []
    start = all_d[0]

    while True:
        w_end = start + pd.Timedelta(days=window_months * 30)
        if w_end > all_d[-1]:
            break
        mask = (df["date"] >= start) & (df["date"] < w_end)
        wdf = df[mask]
        if len(wdf) < 50:
            start = start + pd.Timedelta(days=step_months * 30)
            continue

        # Compute daily IC within this window
        daily_ics = []
        for date, group in wdf.groupby("trade_date"):
            if len(group) >= MIN_ETF:
                ic = _spearman_ic(group["factor"], group["forward_ret"])
                if not np.isnan(ic):
                    daily_ics.append({"date": pd.to_datetime(date, format="%Y%m%d"), "ic": ic})

        if len(daily_ics) < 10:
            start = start + pd.Timedelta(days=step_months * 30)
            continue

        ic_arr = np.array([d["ic"] for d in daily_ics])
        m, s = float(ic_arr.mean()), float(ic_arr.std())
        icir = m / s if s > 0 else 0
        wr = float((ic_arr > 0).mean())

        # Compute monthly ICIR within this window for drawdown
        ic_df = pd.DataFrame(daily_ics)
        ic_df["month"] = ic_df["date"].dt.to_period("M")
        monthly_icir = []
        for month, mg in ic_df.groupby("month"):
            if len(mg) >= 3:
                mm = mg["ic"].mean()
                ms = mg["ic"].std()
                monthly_icir.append(mm / ms if ms > 0 else 0)

        max_drawdown = 0
        if len(monthly_icir) >= 2:
            peak = monthly_icir[0]
            for v in monthly_icir[1:]:
                if v > peak:
                    peak = v
                dd = peak - v
                if dd > max_drawdown:
                    max_drawdown = dd

        windows.append({
            "start": start.strftime("%Y-%m-%d"),
            "end": w_end.strftime("%Y-%m-%d"),
            "icir": icir, "ic_mean": m, "win_rate": wr,
            "n_days": len(daily_ics), "monthly_icir": monthly_icir,
            "max_drawdown": max_drawdown,
        })
        start = start + pd.Timedelta(days=step_months * 30)

    print(f"\n  Computed {len(windows)} six-month rolling windows:")
    for w in windows:
        dd_str = f"DD={w['max_drawdown']:.2f}" if w['monthly_icir'] else "DD=N/A"
        print(f"    {w['start']} ~ {w['end']}: ICIR={w['icir']:.4f}, IC={w['ic_mean']:.4f}, WR={w['win_rate']:.4f}, {dd_str} (n={w['n_days']})")
        if w['monthly_icir']:
            for j, mi in enumerate(w['monthly_icir']):
                print(f"      Monthly ICIR[{j+1}] = {mi:.4f}")

    if not windows:
        print("\n  ❌ Not enough data for 6-month windows.")
        return False, {}

    avg_icir = np.mean([w["icir"] for w in windows])
    avg_wr = np.mean([w["win_rate"] for w in windows])
    max_dd = max(w["max_drawdown"] for w in windows)

    icir_ok = avg_icir >= 0.65
    wr_ok = avg_wr >= 0.70
    dd_ok = max_dd <= 0.30

    print(f"\n  RESULTS:")
    print(f"    Avg ICIR = {avg_icir:.4f} {'✓' if icir_ok else '✗'} (target ≥ 0.65)")
    print(f"    Avg WR   = {avg_wr:.4f} {'✓' if wr_ok else '✗'} (target ≥ 0.70)")
    print(f"    Max DD   = {max_dd:.4f} {'✓' if dd_ok else '✗'} (target ≤ 0.30)")

    passed = icir_ok and wr_ok and dd_ok
    stats = {"avg_icir": avg_icir, "avg_wr": avg_wr, "max_dd": max_dd, "n_windows": len(windows)}

    if passed:
        print(f"\n  ✅ 目标1通过，模型在 6 个月窗口中依然稳健")
    else:
        print(f"\n  ❌ 目标1失败，6个月窗口下指标不达标")
        missing = []
        if not icir_ok: missing.append("ICIR")
        if not wr_ok: missing.append("胜率")
        if not dd_ok: missing.append("回撤")
        print(f"    缺失: {', '.join(missing)}")

    return passed, stats


# ═══════════════════════════════════════════════════════════
#  GOAL 2: Transaction Cost Erosion Test
# ═══════════════════════════════════════════════════════════
def goal2(df, factor_df, price_lookup, all_dates, date_idx):
    print("\n" + "=" * 80)
    print("  GOAL 2: TRANSACTION COST EROSION TEST")
    print("=" * 80)

    # Build a daily top-N rotation portfolio simulation
    # Strategy: each day, rank ETFs by factor score, hold top-5, rebalance at H=15 day intervals
    TOP_N = 5
    REBALANCE_DAYS = H  # Rebalance every H days

    factor_dates = sorted(df["trade_date"].unique())
    etf_codes = sorted(df["etf_code"].unique())

    # Build price series for each ETF
    price_series = {}
    for code in etf_codes:
        series = {}
        for d in all_dates:
            p = price_lookup.get((code, d))
            if p:
                series[d] = float(p)
        price_series[code] = series

    # Simulate portfolio: hold top-N ETFs by factor score, rebalance every REBALANCE_DAYS
    portfolio_returns = []
    benchmark_returns = []
    holdings = []
    prev_holdings = set()

    dates_with_factors = sorted(df["trade_date"].unique())
    rebalance_dates = dates_with_factors[::REBALANCE_DAYS] if len(dates_with_factors) > REBALANCE_DAYS else dates_with_factors

    for i in range(len(rebalance_dates) - 1):
        rb_date = rebalance_dates[i]
        next_rb = rebalance_dates[i + 1]

        # Get factor rankings at rebalance date
        day = df[df["trade_date"] == rb_date].sort_values("factor", ascending=False)
        if len(day) < TOP_N:
            continue

        top_etfs = day.head(TOP_N)["etf_code"].tolist()
        current_holdings = set(top_etfs)

        # Compute turnover
        if prev_holdings:
            turnover = len(current_holdings.symmetric_difference(prev_holdings)) / TOP_N
        else:
            turnover = 1.0
        holdings.append({"date": rb_date, "holdings": top_etfs, "turnover": turnover})

        # Compute portfolio return until next rebalance
        port_ret = 0
        bench_ret = 0
        valid_etfs = 0

        for code in top_etfs:
            p_start = price_series.get(code, {}).get(rb_date)
            p_end = price_series.get(code, {}).get(next_rb)
            if p_start and p_end and p_start > 0:
                port_ret += (p_end / p_start - 1) / TOP_N
                valid_etfs += 1

        # Benchmark: equal-weight all ETFs
        bench_count = 0
        for code in etf_codes:
            p_start = price_series.get(code, {}).get(rb_date)
            p_end = price_series.get(code, {}).get(next_rb)
            if p_start and p_end and p_start > 0:
                bench_ret += (p_end / p_start - 1) / len(etf_codes)
                bench_count += 1

        if valid_etfs > 0:
            # Apply transaction cost on turnover
            cost = turnover * 2 * COST_ONE_WAY  # Round-trip cost on changed positions
            net_ret = port_ret - cost
            excess_ret = port_ret - bench_ret - cost

            portfolio_returns.append({
                "date": rb_date, "gross_ret": port_ret, "net_ret": net_ret,
                "excess_ret": excess_ret, "bench_ret": bench_ret, "turnover": turnover,
            })

        prev_holdings = current_holdings

    if len(portfolio_returns) < 6:
        print(f"\n  ⚠️ 只有 {len(portfolio_returns)} 个调仓期，不足以进行可靠统计")
        # Still compute what we can

    ret_df = pd.DataFrame(portfolio_returns)
    if ret_df.empty:
        print("  ❌ 无有效回测数据")
        return False, {}

    # Compute metrics
    avg_monthly_excess = ret_df["excess_ret"].mean()
    avg_monthly_turnover = ret_df["turnover"].mean()

    # Annualize (assuming ~24 rebalance periods per year with H=15)
    periods_per_year = 250 / REBALANCE_DAYS
    annual_excess = (1 + avg_monthly_excess) ** periods_per_year - 1 if avg_monthly_excess > -1 else -1

    # Sharpe ratio (annualized)
    if ret_df["net_ret"].std() > 0:
        sharpe = (ret_df["net_ret"].mean() / ret_df["net_ret"].std()) * np.sqrt(periods_per_year)
    else:
        sharpe = 0

    monthly_turnover_pct = avg_monthly_turnover * 100

    print(f"\n  PORTFOLIO SIMULATION (Top-{TOP_N}, Rebalance every {REBALANCE_DAYS} days):")
    print(f"    Rebalance periods: {len(ret_df)}")
    print(f"    Avg gross return per period: {ret_df['gross_ret'].mean():.4f}")
    print(f"    Avg net return per period:   {ret_df['net_ret'].mean():.4f}")
    print(f"    Avg benchmark return:        {ret_df['bench_ret'].mean():.4f}")
    print(f"    Avg cost per period:         {COST_ONE_WAY * 2:.4f} × turnover")
    print(f"\n  METRICS:")
    print(f"    Annualized excess return: {annual_excess*100:.2f}% {'✓' if annual_excess >= 0.15 else '✗'} (target ≥ 15%)")
    print(f"    Sharpe ratio:             {sharpe:.4f} {'✓' if sharpe >= 1.2 else '✗'} (target ≥ 1.2)")
    print(f"    Monthly turnover:         {monthly_turnover_pct:.1f}% {'✓' if monthly_turnover_pct <= 200 else '✗'} (target ≤ 200%)")

    # Per-period detail
    print(f"\n  Per-period detail:")
    for _, r in ret_df.iterrows():
        print(f"    {r['date']}: gross={r['gross_ret']:.4f}, net={r['net_ret']:.4f}, "
              f"excess={r['excess_ret']:.4f}, turnover={r['turnover']:.2f}")

    excess_ok = annual_excess >= 0.15
    sharpe_ok = sharpe >= 1.2
    turnover_ok = monthly_turnover_pct <= 200

    passed = excess_ok and sharpe_ok and turnover_ok
    stats = {"annual_excess": annual_excess, "sharpe": sharpe, "monthly_turnover": monthly_turnover_pct,
             "n_periods": len(ret_df)}

    if passed:
        print(f"\n  ✅ 目标2通过，模型净收益仍可观")
    else:
        print(f"\n  ⚠️ 目标2失败，成本吃掉过多收益")
        missing = []
        if not excess_ok: missing.append("超额收益")
        if not sharpe_ok: missing.append("夏普比率")
        if not turnover_ok: missing.append("换手率")
        print(f"    缺失: {', '.join(missing)}")

    return passed, stats


def main():
    _init_db()
    factor_df, price_lookup, all_dates, date_idx = fetch_data()
    df = build_daily_df(factor_df, price_lookup, all_dates, date_idx)
    print(f"Data: {len(df)} rows, {df['trade_date'].nunique()} dates, {df['etf_code'].nunique()} ETFs")
    print(f"Date range: {df['trade_date'].min()} ~ {df['trade_date'].max()}")

    # ── GOAL 1 ──
    g1_pass, g1_stats = goal1(df)

    if not g1_pass:
        print(f"\n{'='*80}")
        print("  FINAL: ❌ GOAL 1 FAILED — 任务终止")
        print(f"{'='*80}")
        print(f"""
[目标 1 测试结果]
失败
关键指标：
  6个月滚动平均 ICIR = {g1_stats.get('avg_icir', 0):.4f}
  胜率 = {g1_stats.get('avg_wr', 0)*100:.1f}%
  最大单月 ICIR 回撤 = {g1_stats.get('max_dd', 0):.4f}
  窗口数 = {g1_stats.get('n_windows', 0)}

结论与建议：建议：放弃当前模型或回退到无 MA 过滤的版本。
""")
        return

    # ── GOAL 2 ──
    g2_pass, g2_stats = goal2(df, factor_df, price_lookup, all_dates, date_idx)

    if not g2_pass:
        print(f"\n{'='*80}")
        print("  FINAL: ⚠️ GOAL 2 FAILED — 任务终止")
        print(f"{'='*80}")
        print(f"""
[目标 2 测试结果]
失败
关键指标：
  6个月滚动平均 ICIR = {g1_stats['avg_icir']:.4f}
  胜率 = {g1_stats['avg_wr']*100:.1f}%
  最大单月 ICIR 回撤 = {g1_stats['max_dd']:.4f}
  年化超额收益 = {g2_stats.get('annual_excess', 0)*100:.2f}%
  夏普比率 = {g2_stats.get('sharpe', 0):.4f}
  月均换手率 = {g2_stats.get('monthly_turnover', 0):.1f}%

结论与建议：建议：引入换手率惩罚或降低调仓频率。
""")
        return

    # ── GOAL 3: Generalization ──
    # Check if we have enough ETF data to expand
    print("\n" + "=" * 80)
    print("  GOAL 3: GENERALIZATION TEST (EXPANDED ETF POOL)")
    print("=" * 80)

    from sqlalchemy import text
    from src.core.db_manager_postgresql import get_conn
    conn = get_conn()
    try:
        # Check how many ETFs we have data for
        count = conn.execute(text(
            "SELECT COUNT(DISTINCT ts_code) FROM sector_etf_daily"
        )).fetchone()[0]
    finally:
        conn.close()

    print(f"\n  Current ETF pool: {df['etf_code'].nunique()} ETFs in sector_etf_daily")
    print(f"  Total ETFs in DB: {count}")

    if count < 30:
        print(f"\n  📉 目标3跳过: 数据库中仅有 {count} 只ETF，不满足30-50只的要求。")
        print(f"  当前数据不足以执行泛化性测试。")

        print(f"\n{'='*80}")
        print("  FINAL: GOAL 1 & 2 PASSED, GOAL 3 SKIPPED (insufficient data)")
        print(f"{'='*80}")
        print(f"""
[稳健性测试总结]
目标1 (压力测试): ✅ 通过
目标2 (成本测试): ✅ 通过
目标3 (泛化测试): ⏭️ 跳过（ETF池不足30只，需扩大数据覆盖）

关键指标：
  6个月滚动平均 ICIR = {g1_stats['avg_icir']:.4f}
  胜率 = {g1_stats['avg_wr']*100:.1f}%
  最大单月 ICIR 回撤 = {g1_stats['max_dd']:.4f}
  年化超额收益 = {g2_stats['annual_excess']*100:.2f}%
  夏普比率 = {g2_stats['sharpe']:.4f}
  月均换手率 = {g2_stats['monthly_turnover']:.1f}%

结论：模型在当前17只ETF池上通过了压力测试和成本侵蚀测试，
建议扩大ETF覆盖至30+只后重新验证泛化性。
""")
        return

    # If we reach here, we have enough ETFs to test generalization
    print("  TODO: Expand ETF pool and re-run model...")
    # This would require fetching new ETF data, computing factors, etc.
    # For now, flag as needing data expansion


if __name__ == "__main__":
    main()
