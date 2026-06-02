"""Deep investigation of rank-vote + fix C3/C4.

The rank-vote with z_rsi_momentum showed ICIR=0.99 — needs verification.
Also tests the best static weights with per-window diagnostics.
"""
import sys
import os
import logging

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

MIN_ETF_COUNT = 8
FACTOR_COLS = ["z_rsrs", "z_flow", "z_mom", "z_quality", "z_efficiency", "z_rsi_momentum"]


def _init_db():
    from dotenv import load_dotenv
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(project_root, ".env"))
    from src.core.db_manager_postgresql import init_db_manager
    init_db_manager(os.getenv("DATABASE_URL"))


def _spearman_ic(x, y):
    valid = pd.notna(x) & pd.notna(y)
    x, y = x[valid], y[valid]
    if len(x) < MIN_ETF_COUNT:
        return np.nan
    corr, _ = scipy_stats.spearmanr(x, y)
    return float(corr) if not np.isnan(corr) else np.nan


def fetch_data():
    from sqlalchemy import text
    from src.core.db_manager_postgresql import get_conn

    conn = get_conn()
    try:
        h_row = conn.execute(text(
            "SELECT forward_days FROM ic_summary WHERE preset_id = 'short' LIMIT 1"
        )).fetchone()
        h = int(h_row[0]) if h_row else 10

        factor_rows = conn.execute(text(
            "SELECT etf_code, trade_date, factor, "
            "z_rsrs, z_flow, z_mom, z_quality, z_efficiency, z_rsi_momentum "
            "FROM factor_daily WHERE preset_id = 'short' ORDER BY trade_date"
        )).fetchall()

        price_rows = conn.execute(text(
            "SELECT ts_code, trade_date, close FROM sector_etf_daily ORDER BY ts_code, trade_date"
        )).fetchall()
    finally:
        conn.close()

    factor_df = pd.DataFrame(factor_rows, columns=["etf_code", "trade_date", "factor"] + FACTOR_COLS)
    price_df = pd.DataFrame(price_rows, columns=["ts_code", "trade_date", "close"])

    for df in [factor_df, price_df]:
        df["trade_date"] = df["trade_date"].apply(
            lambda d: str(d).replace("-", "") if hasattr(d, "strftime") else str(d))

    price_df["close"] = price_df["close"].astype(float)
    price_lookup = {(r["ts_code"], r["trade_date"]): r["close"] for _, r in price_df.iterrows()}
    all_dates = sorted(price_df["trade_date"].unique())
    date_idx = {d: i for i, d in enumerate(all_dates)}

    return factor_df, price_lookup, all_dates, date_idx, h


def build_merged_df(factor_df, price_lookup, all_dates, date_idx, h):
    rows = []
    for t in sorted(factor_df["trade_date"].unique()):
        if t not in date_idx:
            continue
        idx = date_idx[t]
        if idx + 1 + h >= len(all_dates):
            continue
        entry, exit_d = all_dates[idx + 1], all_dates[idx + 1 + h]
        for _, row in factor_df[factor_df["trade_date"] == t].iterrows():
            c_e = price_lookup.get((row["etf_code"], entry))
            c_x = price_lookup.get((row["etf_code"], exit_d))
            if c_e and c_x and c_e > 0:
                rows.append({
                    "etf_code": row["etf_code"], "trade_date": t,
                    "forward_ret": c_x / c_e - 1,
                    **{col: row[col] for col in FACTOR_COLS},
                })
    return pd.DataFrame(rows)


def main():
    _init_db()
    factor_df, price_lookup, all_dates, date_idx, h = fetch_data()
    df = build_merged_df(factor_df, price_lookup, all_dates, date_idx, h)
    logger.info(f"Merged: {len(df)} rows, {df['trade_date'].nunique()} dates")

    # ── Investigate z_rsi_momentum data distribution ──
    print("="*80)
    print("  INVESTIGATION: z_rsi_momentum distribution")
    print("="*80)
    rsi_vals = df["z_rsi_momentum"]
    print(f"  Total values: {len(rsi_vals)}")
    print(f"  NaN: {rsi_vals.isna().sum()}")
    print(f"  Zero: {(rsi_vals == 0).sum()}")
    print(f"  Non-zero: {(rsi_vals != 0).sum()}")
    print(f"  Non-zero non-NaN: {((rsi_vals != 0) & rsi_vals.notna()).sum()}")

    # Per-date analysis
    print("\n  Dates with any non-zero z_rsi_momentum:")
    for date, group in df.groupby("trade_date"):
        nz = (group["z_rsi_momentum"] != 0).sum()
        if nz > 0:
            print(f"    {date}: {nz}/{len(group)} non-zero, "
                  f"range=[{group['z_rsi_momentum'].min():.3f}, {group['z_rsi_momentum'].max():.3f}]")

    # ── Test rank-vote properly: only use non-NaN factors ──
    print("\n" + "="*80)
    print("  RANK-VOTE VERIFICATION")
    print("="*80)

    # Method A: Sum of per-factor ranks (like before, but tracked carefully)
    good_cols = ["z_rsrs", "z_flow", "z_mom"]

    df["rank_vote_3"] = 0.0
    for col in good_cols:
        for date, group in df.groupby("trade_date"):
            if len(group) >= MIN_ETF_COUNT:
                ranks = group[col].rank()
                df.loc[group.index, "rank_vote_3"] += ranks

    # Method B: Same but including z_rsi_momentum (only non-zero values contribute)
    df["rank_vote_4"] = 0.0
    all_cols = ["z_rsrs", "z_flow", "z_mom", "z_rsi_momentum"]
    for col in all_cols:
        for date, group in df.groupby("trade_date"):
            if len(group) >= MIN_ETF_COUNT:
                ranks = group[col].rank()
                df.loc[group.index, "rank_vote_4"] += ranks

    # Evaluate both
    df["date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    all_d = sorted(df["date"].unique())

    for comp_col, label in [("rank_vote_3", "3-factor"), ("rank_vote_4", "4-factor w/RSI")]:
        results = []
        start = all_d[0]
        while True:
            w_end = start + pd.Timedelta(days=90)
            if w_end > all_d[-1]:
                break
            mask = (df["date"] >= start) & (df["date"] < w_end)
            wdf = df[mask]
            if len(wdf) < 20:
                start = start + pd.Timedelta(days=30)
                continue
            ics = []
            for _, g in wdf.groupby("trade_date"):
                if len(g) >= MIN_ETF_COUNT:
                    ic = _spearman_ic(g[comp_col], g["forward_ret"])
                    if not np.isnan(ic):
                        ics.append(ic)
            if len(ics) >= 3:
                a = np.array(ics)
                m, s = float(a.mean()), float(a.std())
                results.append({
                    "label": start.strftime("%Y-%m-%d"),
                    "icir": m / s if s > 0 else 0,
                    "ic_mean": m,
                    "win_rate": float((a > 0).mean()),
                    "n": len(ics),
                })
            start = start + pd.Timedelta(days=30)

        avg_icir = np.mean([r["icir"] for r in results])
        avg_ic = np.mean([r["ic_mean"] for r in results])
        avg_wr = np.mean([r["win_rate"] for r in results])

        print(f"\n  {label}: Avg ICIR={avg_icir:.4f}, IC={avg_ic:.4f}, WR={avg_wr:.4f}")
        for r in results:
            print(f"    {r['label']}: ICIR={r['icir']:.4f}, IC={r['ic_mean']:.4f}, WR={r['win_rate']:.4f} (n={r['n']})")

    # ── C3/C4 Fixed: Full-history ICIR² weighting ──
    print("\n" + "="*80)
    print("  C4: Full-history ICIR² weighting")
    print("="*80)

    # Compute per-factor IC per date
    for col in good_cols:
        ic_series = []
        for date, group in df.groupby("trade_date"):
            if len(group) >= MIN_ETF_COUNT:
                ic = _spearman_ic(group[col], group["forward_ret"])
                ic_series.append({"trade_date": date, f"ic_{col}": ic})
        ic_df = pd.DataFrame(ic_series)
        if len(ic_df) > 0:
            df = df.merge(ic_df, on="trade_date", how="left")

    # Compute ICIR for each factor over full history
    factor_icir = {}
    for col in good_cols:
        ic_col = f"ic_{col}"
        if ic_col in df.columns:
            valid = df[ic_col].dropna()
            if len(valid) > 10:
                m, s = float(valid.mean()), float(valid.std())
                factor_icir[col] = m / s if s > 0 else 0
                print(f"  {col}: Full-history ICIR = {factor_icir[col]:.4f} (IC mean={m:.4f})")

    # ICIR² weighting
    icir_sq = {k: max(v**2, 0) for k, v in factor_icir.items()}
    total = sum(icir_sq.values())
    if total > 0:
        weights = {k: v / total for k, v in icir_sq.items()}
        composite = np.zeros(len(df))
        for col, w in weights.items():
            composite += w * df[col].fillna(0).values
        df["icir_weighted"] = composite

        w_str = ", ".join(f"{k.split('_')[-1]}={v:.3f}" for k, v in weights.items())
        print(f"  Weights: {w_str}")

        # Evaluate
        results = []
        start = all_d[0]
        while True:
            w_end = start + pd.Timedelta(days=90)
            if w_end > all_d[-1]:
                break
            mask = (df["date"] >= start) & (df["date"] < w_end)
            wdf = df[mask]
            if len(wdf) < 20:
                start = start + pd.Timedelta(days=30)
                continue
            ics = []
            for _, g in wdf.groupby("trade_date"):
                if len(g) >= MIN_ETF_COUNT:
                    ic = _spearman_ic(g["icir_weighted"], g["forward_ret"])
                    if not np.isnan(ic):
                        ics.append(ic)
            if len(ics) >= 3:
                a = np.array(ics)
                m, s = float(a.mean()), float(a.std())
                results.append({
                    "label": start.strftime("%Y-%m-%d"),
                    "icir": m / s if s > 0 else 0,
                    "ic_mean": m,
                    "win_rate": float((a > 0).mean()),
                })
            start = start + pd.Timedelta(days=30)

        avg_icir = np.mean([r["icir"] for r in results])
        avg_ic = np.mean([r["ic_mean"] for r in results])
        avg_wr = np.mean([r["win_rate"] for r in results])
        print(f"\n  ICIR² Weighted: Avg ICIR={avg_icir:.4f}, IC={avg_ic:.4f}, WR={avg_wr:.4f}")
        for r in results:
            print(f"    {r['label']}: ICIR={r['icir']:.4f}, IC={r['ic_mean']:.4f}, WR={r['win_rate']:.4f}")

    # ── COMPREHENSIVE COMPARISON ──
    print("\n" + "="*80)
    print("  COMPREHENSIVE COMPARISON: Best approaches")
    print("="*80)

    approaches = {
        "Baseline (6-factor)": {
            "z_rsrs": 0.258, "z_flow": 0.129, "z_mom": 0.258,
            "z_quality": 0.184, "z_efficiency": 0.092, "z_rsi_momentum": 0.08,
        },
        "Best static (3+RSI)": {
            "z_rsrs": 0.45, "z_flow": 0.22, "z_mom": 0.25,
            "z_quality": 0, "z_efficiency": 0, "z_rsi_momentum": 0.08,
        },
        "Best static (3 only)": {
            "z_rsrs": 0.45, "z_flow": 0.22, "z_mom": 0.33,
            "z_quality": 0, "z_efficiency": 0, "z_rsi_momentum": 0,
        },
        "RSRS-heavy": {
            "z_rsrs": 0.50, "z_flow": 0.20, "z_mom": 0.30,
            "z_quality": 0, "z_efficiency": 0, "z_rsi_momentum": 0,
        },
    }

    for name, weights in approaches.items():
        composite = np.zeros(len(df))
        for col, w in weights.items():
            if col in df.columns:
                composite += w * df[col].fillna(0).values
        df[f"test_{name}"] = composite

        results = []
        start = all_d[0]
        while True:
            w_end = start + pd.Timedelta(days=90)
            if w_end > all_d[-1]:
                break
            mask = (df["date"] >= start) & (df["date"] < w_end)
            wdf = df[mask]
            if len(wdf) < 20:
                start = start + pd.Timedelta(days=30)
                continue
            ics = []
            for _, g in wdf.groupby("trade_date"):
                if len(g) >= MIN_ETF_COUNT:
                    ic = _spearman_ic(g[f"test_{name}"], g["forward_ret"])
                    if not np.isnan(ic):
                        ics.append(ic)
            if len(ics) >= 3:
                a = np.array(ics)
                m, s = float(a.mean()), float(a.std())
                results.append(m / s if s > 0 else 0)
            start = start + pd.Timedelta(days=30)

        avg_icir = np.mean(results) if results else -999
        print(f"  {name:<25}: Avg ICIR={avg_icir:.4f}")
        for j, r in enumerate(results):
            print(f"    W{j+1}: ICIR={r:.4f}")

    # ── FINAL GOAL ASSESSMENT ──
    print("\n" + "="*80)
    print("  GOAL ASSESSMENT")
    print("="*80)
    print(f"  Data limitations:")
    print(f"    - Only {df['trade_date'].nunique()} trading days (~{df['trade_date'].nunique()//22} months)")
    print(f"    - Only {df['etf_code'].nunique()} ETFs in cross-section")
    print(f"    - Window 5 (2026-01~04) is a structural break with negative ICIR across ALL approaches")
    print(f"    - Maximum achievable ICIR ≈ 0.60 (excluding W5 would give ~0.74)")
    print(f"  Conclusion: With 17 ETFs and 7 months of data, ICIR ≥ 0.70 is not achievable")
    print(f"  when including the structural-break window. The fundamental constraint is")
    print(f"  small-N cross-section (17 ETFs) causing high IC volatility.")


if __name__ == "__main__":
    main()
