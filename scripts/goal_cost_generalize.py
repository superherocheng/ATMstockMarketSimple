"""Robustness Test: Cost erosion + Generalization.

Goal 1: Transaction cost test (0.10% one-way, 3-month windows)
Goal 2: Expanded ETF pool generalization (30-50 ETFs, data permitting)
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
TOP_N = 5
COST = 0.001  # 0.10% one-way
WEIGHTS = {"z_rsrs": 0.38, "z_flow": 0.22, "z_mom": 0.32, "z_quality": 0.0, "z_efficiency": 0.0, "z_rsi_momentum": 0.08}


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
        etf_count = conn.execute(text(
            "SELECT COUNT(DISTINCT ts_code) FROM sector_etf_daily"
        )).fetchone()[0]
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

    return factor_df, price_lookup, all_dates, date_idx, etf_count


def build_daily_df(factor_df, price_lookup, all_dates, date_idx):
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
                })
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════
#  GOAL 1: Transaction Cost Erosion Test
# ═══════════════════════════════════════════════════════════
def goal1_cost_test(df, price_lookup, all_dates, date_idx):
    print("=" * 80)
    print("  GOAL 1: TRANSACTION COST EROSION TEST")
    print(f"  Single-way cost: {COST*100:.2f}%, Top-{TOP_N} portfolio, H={H} days")
    print("=" * 80)

    etf_codes = sorted(df["etf_code"].unique())
    factor_dates = sorted(df["trade_date"].unique())

    # Build price lookup for all ETFs and dates
    price_series = {}
    for code in etf_codes:
        s = {}
        for d in all_dates:
            p = price_lookup.get((code, d))
            if p:
                s[d] = float(p)
        price_series[code] = s

    # Strategy: rank ETFs by factor every H days, hold top-N
    # Rebalance at each H-day interval
    rebalance_points = list(range(0, len(factor_dates), H))

    results = []
    prev_holdings = set()

    for rp_idx in range(len(rebalance_points) - 1):
        rp = rebalance_points[rp_idx]
        next_rp = rebalance_points[rp_idx + 1]

        rb_date = factor_dates[rp]
        next_rb_date = factor_dates[min(next_rp, len(factor_dates) - 1)]

        # Get factor rankings at rebalance date
        day = df[df["trade_date"] == rb_date].sort_values("factor", ascending=False)
        if len(day) < TOP_N:
            continue

        top_etfs = day.head(TOP_N)["etf_code"].tolist()
        current_holdings = set(top_etfs)

        # Compute turnover ratio
        if prev_holdings:
            buys = len(current_holdings - prev_holdings)
            sells = len(prev_holdings - current_holdings)
            turnover = (buys + sells) / (2 * TOP_N)  # Single-side turnover
        else:
            turnover = 1.0

        # Compute portfolio return
        port_ret = 0
        valid = 0
        for code in top_etfs:
            p_s = price_series.get(code, {}).get(rb_date)
            p_e = price_series.get(code, {}).get(next_rb_date)
            if p_s and p_e and p_s > 0:
                port_ret += (p_e / p_s - 1) / TOP_N
                valid += 1

        # Compute benchmark return (equal-weight all ETFs)
        bench_ret = 0
        bench_valid = 0
        for code in etf_codes:
            p_s = price_series.get(code, {}).get(rb_date)
            p_e = price_series.get(code, {}).get(next_rb_date)
            if p_s and p_e and p_s > 0:
                bench_ret += (p_e / p_s - 1) / len(etf_codes)
                bench_valid += 1

        if valid < TOP_N // 2:
            prev_holdings = current_holdings
            continue

        # Apply transaction cost
        total_cost = turnover * 2 * COST  # Buy + sell cost on changed portion
        net_ret = port_ret - total_cost
        excess_ret = port_ret - bench_ret - total_cost

        results.append({
            "date": rb_date, "next_date": next_rb_date,
            "gross_ret": port_ret, "bench_ret": bench_ret,
            "cost": total_cost, "net_ret": net_ret,
            "excess_ret": excess_ret, "turnover": turnover,
            "holdings": top_etfs,
        })
        prev_holdings = current_holdings

    if not results:
        print("  ❌ No valid rebalance periods")
        return False, {}

    ret_df = pd.DataFrame(results)
    periods_per_year = 250 / H

    # Metrics
    annual_gross = ((1 + ret_df["gross_ret"].mean()) ** periods_per_year - 1) * 100
    annual_net = ((1 + ret_df["net_ret"].mean()) ** periods_per_year - 1) * 100
    annual_excess = ((1 + ret_df["excess_ret"].mean()) ** periods_per_year - 1) * 100
    annual_bench = ((1 + ret_df["bench_ret"].mean()) ** periods_per_year - 1) * 100

    net_std = ret_df["net_ret"].std()
    sharpe = (ret_df["net_ret"].mean() / net_std * np.sqrt(periods_per_year)) if net_std > 0 else 0

    monthly_turnover = ret_df["turnover"].mean() * (250 / H / 12) * 100  # Monthly turnover %

    # Also compute IC metrics on the same data
    ic_results = rolling_ic_eval(df)

    print(f"\n  PORTFOLIO SIMULATION RESULTS:")
    print(f"    Rebalance periods: {len(ret_df)}")
    print(f"    Annualized gross return:   {annual_gross:.2f}%")
    print(f"    Annualized benchmark:      {annual_bench:.2f}%")
    print(f"    Annualized net return:     {annual_net:.2f}%")
    print(f"    Annualized excess return:  {annual_excess:.2f}%")
    print(f"    Sharpe ratio (net):        {sharpe:.4f}")
    print(f"    Monthly turnover:          {monthly_turnover:.1f}%")
    print(f"    Avg per-period cost:       {ret_df['cost'].mean()*100:.3f}%")

    print(f"\n  Per-period detail:")
    for _, r in ret_df.iterrows():
        print(f"    {r['date']}: gross={r['gross_ret']*100:.2f}%, bench={r['bench_ret']*100:.2f}%, "
              f"net={r['net_ret']*100:.2f}%, excess={r['excess_ret']*100:.2f}%, "
              f"turnover={r['turnover']*100:.1f}%")

    excess_ok = annual_excess >= 15
    sharpe_ok = sharpe >= 1.2
    turnover_ok = monthly_turnover <= 200

    print(f"\n  GOAL CHECK:")
    print(f"    Excess return ≥ 15%: {'PASS' if excess_ok else 'FAIL'} ({annual_excess:.2f}%)")
    print(f"    Sharpe ≥ 1.2:       {'PASS' if sharpe_ok else 'FAIL'} ({sharpe:.4f})")
    print(f"    Turnover ≤ 200%:    {'PASS' if turnover_ok else 'FAIL'} ({monthly_turnover:.1f}%)")

    passed = excess_ok and sharpe_ok and turnover_ok
    stats = {
        "annual_excess": annual_excess, "sharpe": sharpe, "monthly_turnover": monthly_turnover,
        "icir": ic_results.get("avg_icir", 0), "win_rate": ic_results.get("avg_wr", 0),
        "n_periods": len(ret_df),
    }

    if passed:
        print(f"\n  ✅ 目标1通过，模型净收益仍可观")
    else:
        print(f"\n  ⚠️ 目标1失败，成本吃掉过多收益")
        missing = []
        if not excess_ok: missing.append(f"超额收益({annual_excess:.1f}%)")
        if not sharpe_ok: missing.append(f"夏普({sharpe:.2f})")
        if not turnover_ok: missing.append(f"换手率({monthly_turnover:.1f}%)")
        print(f"    缺失: {', '.join(missing)}")

    return passed, stats


def rolling_ic_eval(df, window_months=3, step_months=1):
    """Compute rolling IC metrics for reference."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    all_d = sorted(df["date"].unique())
    results = []
    start = all_d[0]
    while True:
        w_end = start + pd.Timedelta(days=window_months * 30)
        if w_end > all_d[-1]:
            break
        mask = (df["date"] >= start) & (df["date"] < w_end)
        wdf = df[mask]
        if len(wdf) < 20:
            start = start + pd.Timedelta(days=step_months * 30)
            continue
        ics = []
        for _, g in wdf.groupby("trade_date"):
            if len(g) >= MIN_ETF:
                ic = _spearman_ic(g["factor"], g["forward_ret"])
                if not np.isnan(ic):
                    ics.append(ic)
        if len(ics) >= 3:
            a = np.array(ics)
            m, s = float(a.mean()), float(a.std())
            results.append({"start": start.strftime("%Y-%m-%d"), "icir": m / s if s > 0 else 0,
                           "ic_mean": m, "win_rate": float((a > 0).mean())})
        start = start + pd.Timedelta(days=step_months * 30)
    if not results:
        return {}
    return {
        "avg_icir": round(np.mean([r["icir"] for r in results]), 4),
        "avg_ic": round(np.mean([r["ic_mean"] for r in results]), 4),
        "avg_wr": round(np.mean([r["win_rate"] for r in results]), 4),
        "n_windows": len(results),
    }


def main():
    _init_db()
    factor_df, price_lookup, all_dates, date_idx, etf_count = fetch_data()
    df = build_daily_df(factor_df, price_lookup, all_dates, date_idx)
    print(f"Data: {len(df)} rows, {df['trade_date'].nunique()} dates, {df['etf_code'].nunique()} ETFs")
    print(f"Date range: {df['trade_date'].min()} ~ {df['trade_date'].max()}")
    print(f"Total ETFs in DB: {etf_count}")

    # ── GOAL 1 ──
    g1_pass, g1_stats = goal1_cost_test(df, price_lookup, all_dates, date_idx)

    if not g1_pass:
        print(f"\n{'='*80}")
        print("  FINAL: ⚠️ GOAL 1 FAILED")
        print(f"{'='*80}")
        print(f"""
[目标 1 测试结果]
失败
关键指标：
  滚动平均 ICIR = {g1_stats.get('icir', 0):.4f}
  胜率 = {g1_stats.get('win_rate', 0)*100:.1f}%
  年化超额收益 = {g1_stats.get('annual_excess', 0):.2f}%
  夏普比率 = {g1_stats.get('sharpe', 0):.4f}
  月均换手率 = {g1_stats.get('monthly_turnover', 0):.1f}%
结论与建议：建议：引入换手率惩罚或降低调仓频率。
""")
        return

    # ── GOAL 2: Generalization ──
    print("\n" + "=" * 80)
    print("  GOAL 2: GENERALIZATION TEST (EXPANDED ETF POOL)")
    print("=" * 80)

    current_etfs = df['etf_code'].nunique()
    print(f"\n  Current ETF pool: {current_etfs} sector ETFs")
    print(f"  Total ETFs in sector_etf_daily: {etf_count}")

    if etf_count < 30:
        print(f"\n  📉 目标3跳过: sector_etf_daily 中仅有 {etf_count} 只ETF，不满足30只的最低要求。")
        print(f"  需要额外获取 {30 - etf_count}+ 只ETF数据才能执行泛化性测试。")

        print(f"\n{'='*80}")
        print("  FINAL: ✅ GOAL 1 PASSED, GOAL 2 SKIPPED (insufficient data)")
        print(f"{'='*80}")
        print(f"""
[稳健性测试总结]
目标1 (成本侵蚀): ✅ 通过
目标2 (泛化测试): ⏭️ 跳过（sector ETF池仅{etf_count}只，需30+只）

关键指标：
  滚动平均 ICIR = {g1_stats['icir']:.4f}
  胜率 = {g1_stats.get('win_rate', 0)*100:.1f}%
  年化超额收益 = {g1_stats['annual_excess']:.2f}%
  夏普比率 = {g1_stats['sharpe']:.4f}
  月均换手率 = {g1_stats['monthly_turnover']:.1f}%

结论：模型通过了交易成本侵蚀测试，在计入0.10%单边成本后
仍保持正超额收益。建议扩大ETF覆盖至30+只后验证泛化性。
""")
        return

    # Check what ETFs are available
    print(f"  数据充分，检查ETF组成...")
    from sqlalchemy import text
    from src.core.db_manager_postgresql import get_conn
    conn = get_conn()
    try:
        etf_list = conn.execute(text(
            "SELECT DISTINCT ts_code FROM sector_etf_daily ORDER BY ts_code"
        )).fetchall()
    finally:
        conn.close()

    codes = [r[0] for r in etf_list]
    print(f"  Available ETFs ({len(codes)}): {', '.join(codes)}")

    if len(codes) < 30:
        print(f"\n  📉 ETF数量不足 ({len(codes)}/{30})，跳过泛化测试")
        print(f"\n{'='*80}")
        print(f"  FINAL: ✅ GOAL 1 PASSED, GOAL 2 SKIPPED")
        print(f"{'='*80}")
        return

    print(f"\n  ✅ ETF池足够大 ({len(codes)}只)，可以执行泛化测试")
    print(f"  TODO: 扩展因子计算并验证...")


if __name__ == "__main__":
    main()
