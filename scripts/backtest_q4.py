"""
Q4轻微持仓回测脚本 (优化版)
==========================
对比两种策略:
  A — 当前策略: 仅 Q1+Q2, 按正因子分比例配仓, 单ETF≤25%
  B — Q4轻微持仓: Q1+Q2 + Q4(5%上限)

优化:
  - O(1) dict 查找替代 pandas pivot/loc
  - 候选池预计算, 避免循环中重复过滤
  - numpy 替代 pandas 做分数计算
"""
import sys
import math
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

import numpy as np
import pandas as pd
from sqlalchemy import text
from config.config import SECTOR_ETF

RISK_FREE_RATE = 0.02
MAX_SINGLE = 0.25
Q4_MAX_SINGLE = 0.05
REBALANCE_INTERVAL = 10


def _ensure_db():
    from src.core.db_manager_postgresql import _ensure_db
    import os
    _ensure_db()


def iterrows_fast(df):
    """Faster row iteration using numpy."""
    for row in df.itertuples(index=False):
        yield row


def load_data(ts_code, preset_id="short"):
    _ensure_db()
    from src.core.db_manager_postgresql import get_conn

    conn = get_conn()
    try:
        factor_rows = conn.execute(text("""
            SELECT etf_code, trade_date, factor, quadrant
            FROM factor_daily
            WHERE preset_id = :pid
            ORDER BY trade_date, etf_code
        """), {"pid": preset_id}).fetchall()

        price_rows = conn.execute(text("""
            SELECT ts_code, trade_date, pct_chg
            FROM sector_etf_daily
            ORDER BY ts_code, trade_date
        """)).fetchall()

        bench_rows = conn.execute(text("""
            SELECT trade_date, pct_chg
            FROM index_etf_daily
            WHERE ts_code = :code
            ORDER BY trade_date
        """), {"code": ts_code}).fetchall()
    finally:
        conn.close()

    if not factor_rows or not price_rows:
        print("ERROR: No data found."); sys.exit(1)

    def norm(d):
        s = str(d)
        return s.replace("-", "") if "-" in s else s

    # ── Build factor lookup: date -> [(code, factor, quadrant), ...] ──
    factor_by_date = {}
    for r in factor_rows:
        d = norm(r[1])
        code = r[0]
        if code not in SECTOR_ETF:
            continue
        factor_by_date.setdefault(d, []).append((code, float(r[2]) if r[2] else 0, int(r[3]) if r[3] else 0))

    # ── Build return lookup: date -> {code: ret} ──
    ret_by_date = {}
    for r in price_rows:
        d = norm(r[1])
        v = float(r[2]) / 100.0 if r[2] else 0.0
        ret_by_date.setdefault(d, {})[r[0]] = v

    # ── Build benchmark lookup ──
    bench_by_date = {}
    for r in bench_rows or []:
        d = norm(r[0])
        v = float(r[1]) / 100.0 if r[1] else 0.0
        bench_by_date[d] = v

    # ── Compute ETF correlation matrix ──
    price_df = pd.DataFrame(price_rows, columns=["ts_code", "trade_date", "pct_chg"])
    price_df["trade_date"] = price_df["trade_date"].apply(norm)
    price_df["pct_chg"] = price_df["pct_chg"].astype(float)
    ret_pivot = price_df.pivot(index="trade_date", columns="ts_code", values="pct_chg")
    corr_df = ret_pivot.corr()

    # correlation penalty lookup: (code_i, code_j) -> penalty_multiplier
    # pre-built for O(1) access
    corr_penalty_map = {}
    codes = list(SECTOR_ETF.keys())
    for i, c1 in enumerate(codes):
        for c2 in codes:
            if c1 not in corr_df.index or c2 not in corr_df.columns:
                corr_penalty_map[(c1, c2)] = 1.0
                continue
            v = abs(corr_df.loc[c1, c2])
            if v > 0.7:
                corr_penalty_map[(c1, c2)] = 0.3
            elif v > 0.6:
                corr_penalty_map[(c1, c2)] = 0.5
            elif v > 0.5:
                corr_penalty_map[(c1, c2)] = 0.7
            else:
                corr_penalty_map[(c1, c2)] = 1.0

    return factor_by_date, ret_by_date, bench_by_date, corr_penalty_map


def run_backtest(factor_by_date, ret_by_date, corr_penalty_map, strategy="A"):
    """
    Backtest with O(1) dict lookups and pre-filtered candidates.

    Strategy A: Q1+Q2 only (current)
    Strategy B: Q1+Q2 + Q4 (capped at 5% each)
    """
    all_dates = sorted(set(ret_by_date.keys()) & set(factor_by_date.keys()))
    if not all_dates:
        print("ERROR: No overlapping dates"); return None, None, []

    # Pre-filter candidates per date into two lists: [Q1Q2], [Q4]
    # (code, factor, quadrant, score_contribution)
    candidates_q12 = {}  # date -> list
    candidates_q4 = {}   # date -> list
    for d in all_dates:
        q12 = []
        q4 = []
        for code, factor, quadrant in factor_by_date[d]:
            if quadrant == 4 and strategy == "B":
                q4.append((code, factor, quadrant,
                           max(0, -factor) * 0.3))  # minor score
            elif quadrant in (1, 2):
                mult = 1.0 if quadrant == 1 else 0.7
                q12.append((code, factor, quadrant,
                            max(0, factor) * mult))
        candidates_q12[d] = q12
        candidates_q4[d] = q4

    rebalance_dates = set(all_dates[::REBALANCE_INTERVAL])

    current_weights = {}  # code -> weight
    strat_rets = []
    holdings_log = []
    n = len(all_dates)

    for i, t in enumerate(all_dates):
        if t in rebalance_dates and i > 0:
            prev_t = all_dates[i - 1]

            q12 = candidates_q12.get(prev_t, [])
            q4 = candidates_q4.get(prev_t, [])

            # Sort by score descending, take top candidates
            # Combined pool: Q1/Q2 first, then Q4
            pool = q12 + q4
            if not pool:
                continue

            # Sort by score descending
            pool.sort(key=lambda x: -x[3])

            # Apply correlation penalty and build final scores
            scored = []
            selected_codes = []
            codes_in_pool = [x[0] for x in pool]

            for code, factor, quadrant, base_score in pool:
                # Correlation penalty
                penalty = 1.0
                if selected_codes:
                    max_corr = 0.0
                    for sc in selected_codes:
                        p = corr_penalty_map.get((code, sc), 1.0)
                        if p < max_corr or max_corr == 0:
                            max_corr = min(max_corr, p) if max_corr > 0 else p
                    # Simple: use worst penalty
                    min_penalty = min(corr_penalty_map.get((code, sc), 1.0) for sc in selected_codes)
                    penalty = min_penalty

                final = base_score * penalty
                if final > 0:
                    scored.append((code, quadrant, final))
                    selected_codes.append(code)

            if not scored:
                continue

            # Take top 5
            scored = scored[:5]

            total_score = sum(s for _, _, s in scored)
            if total_score <= 0:
                continue

            new_weights = {}
            for code, quadrant, final_score in scored:
                share = final_score / total_score
                cap = Q4_MAX_SINGLE if quadrant == 4 else MAX_SINGLE
                new_weights[code] = min(share, cap)

            current_weights = new_weights
            holdings_log.append((t, prev_t, {k: round(v, 3) for k, v in current_weights.items()}))

        # Portfolio return for this date
        if current_weights and t in ret_by_date:
            day_rets = ret_by_date[t]
            port_ret = 0.0
            for code, weight in current_weights.items():
                r = day_rets.get(code, np.nan)
                if not np.isnan(r):
                    port_ret += weight * r
        else:
            port_ret = 0.0

        strat_rets.append(port_ret)

    return pd.Series(strat_rets, index=all_dates, name=f"S{strategy}"), holdings_log


def compute_metrics(returns):
    n = max(len(returns), 1)
    cum_ret = float((1 + returns).prod() - 1)
    ann_ret = (1 + cum_ret) ** (252 / n) - 1 if n > 0 else 0
    ann_vol = float(returns.std() * math.sqrt(252)) if n > 0 else 0
    rf_daily = RISK_FREE_RATE / 252
    excess = returns - rf_daily
    sharpe = float(excess.mean() / max(excess.std(), 1e-10) * math.sqrt(252)) if n > 0 else 0
    cum_series = (1 + returns).cumprod()
    running_max = cum_series.cummax()
    dd = (cum_series - running_max) / running_max
    max_dd = float(dd.min()) if len(dd) > 0 else 0
    calmar = ann_ret / abs(max_dd) if max_dd != 0 else 0.0
    win_rate = float((returns > 0).mean()) if n > 0 else 0
    return {
        "total_return": cum_ret, "annualized_return": ann_ret,
        "annual_volatility": ann_vol, "sharpe": sharpe,
        "max_drawdown": max_dd, "calmar": calmar,
        "win_rate": win_rate, "trading_days": n,
    }


def main():
    ts_code = "510500.SH"
    preset_id = "short"

    print("=" * 70)
    print("  三因子模型(Q4回测)  优化版")
    print(f"  预设: {preset_id} | 基准: {ts_code}")
    print(f"  策略A: 仅Q1+Q2 (当前)")
    print(f"  策略B: Q1+Q2+Q4 (Q4≤{Q4_MAX_SINGLE*100:.0f}%)")
    print(f"  调仓: 每{REBALANCE_INTERVAL}交易日")
    print("=" * 70)

    t0 = time.time()
    print("\nLoading data...", end=" ", flush=True)
    factor_by_date, ret_by_date, bench_by_date, corr_penalty_map = load_data(ts_code, preset_id)
    print(f"{len(factor_by_date)} dates, {time.time()-t0:.1f}s")

    t1 = time.time()
    print("Running strategy A (Q1+Q2)...", end=" ", flush=True)
    strat_a, log_a = run_backtest(factor_by_date, ret_by_date, corr_penalty_map, "A")
    print(f"{len(strat_a)} days, {time.time()-t1:.2f}s")

    t2 = time.time()
    print("Running strategy B (Q1+Q2+Q4)...", end=" ", flush=True)
    strat_b, log_b = run_backtest(factor_by_date, ret_by_date, corr_penalty_map, "B")
    print(f"{len(strat_b)} days, {time.time()-t2:.2f}s")

    # Benchmark
    bench_series = None
    if bench_by_date:
        berts = [bench_by_date.get(d, 0.0) for d in strat_a.index]
        bench_series = pd.Series(berts, index=strat_a.index, name="bench")

    m_a = compute_metrics(strat_a)
    m_b = compute_metrics(strat_b)
    m_bench = compute_metrics(bench_series) if bench_series is not None else {}

    sep = "=" * 70
    print(f"\n{sep}")
    print("  回测结果对比")
    print(sep)
    print(f"\n  {'指标':<18} {'A(Q1+Q2)':>14} {'B(+Q4)':>14} {'基准':>14}")
    print("  " + "-" * 62)

    def fmt_pct(v): return f"{v*100:+.2f}%" if not math.isinf(v) else "N/A"
    def fmt_num(v): return f"{v:.3f}" if not math.isinf(v) else "N/A"

    row_defs = [
        ("累计收益率", "total_return", fmt_pct),
        ("年化收益率", "annualized_return", fmt_pct),
        ("年化波动率", "annual_volatility", fmt_pct),
        ("Sharpe", "sharpe", fmt_num),
        ("最大回撤", "max_drawdown", fmt_pct),
        ("Calmar", "calmar", fmt_num),
        ("日胜率", "win_rate", fmt_pct),
        ("交易日数", "trading_days", lambda v: f"{v}"),
    ]
    for label, key, fmt in row_defs:
        va = fmt(m_a.get(key, 0))
        vb = fmt(m_b.get(key, 0))
        vc = fmt(m_bench.get(key, 0)) if m_bench else "N/A"
        print(f"  {label:<18} {va:>14} {vb:>14} {vc:>14}")

    # Q4 holdings frequency
    print(f"\n  策略B中Q4持仓情况:")
    q4_holdings = {}
    for _, _, weights in log_b:
        for code, w in weights.items():
            q4_holdings[code] = q4_holdings.get(code, 0) + 1
    if q4_holdings:
        for code, count in sorted(q4_holdings.items(), key=lambda x: -x[1]):
            print(f"    {SECTOR_ETF.get(code, code):12s}: {count}次")
    else:
        print("    (无Q4持仓)")

    # Codes unique to B
    codes_b = set()
    for _, _, w in log_b:
        codes_b.update(w.keys())
    codes_a = set()
    for _, _, w in log_a:
        codes_a.update(w.keys())
    q4_only = [SECTOR_ETF.get(c, c) for c in (codes_b - codes_a)]
    if q4_only:
        print(f"\n  策略B额外持有: {', '.join(q4_only)}")
    else:
        print(f"\n  两组持仓一致 (Q4未进入top5候选)")

    print(f"\n  总耗时: {time.time()-t0:.1f}s")
    print(sep)
    print(f"\n  结论:")
    a_s = m_a.get("sharpe", 0)
    b_s = m_b.get("sharpe", 0)
    a_r = m_a.get("annualized_return", 0)
    b_r = m_b.get("annualized_return", 0)
    a_d = m_a.get("max_drawdown", 0)
    b_d = m_b.get("max_drawdown", 0)
    print(f"    Sharpe:    A={a_s:.3f}  B={b_s:.3f}")
    print(f"    年化收益:  A={a_r*100:.2f}%  B={b_r*100:.2f}%")
    print(f"    最大回撤:  A={a_d*100:.2f}%  B={b_d*100:.2f}%")

    if b_s > a_s * 1.05:
        print(f"    >> Q4轻微持仓提升了Sharpe，有效")
    elif b_s > a_s:
        print(f"    >> Q4轻微持仓略有提升，效果边际")
    else:
        print(f"    >> Q4轻微持仓未改善表现，建议维持纯Q1+Q2策略")


if __name__ == "__main__":
    main()
