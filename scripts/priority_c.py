"""Priority C: Two-layer factor combination + rank-voting ensemble.

Strategy:
- Layer 1: Build multiple sub-combinations (equal-weight within each)
- Layer 2: Average the sub-combination signals (robust rank voting)

Also tests:
- Inverse-IC-std weighting (more stable factors get higher weight)
- Leave-one-out factor combinations
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


def rolling_eval(df, composite_col="composite", window_months=3, step_months=1):
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
            if len(g) < MIN_ETF_COUNT:
                continue
            ic = _spearman_ic(g[composite_col], g["forward_ret"])
            if not np.isnan(ic):
                ics.append(ic)
        if len(ics) >= 3:
            a = np.array(ics)
            m, s = float(a.mean()), float(a.std())
            results.append({"icir": m / s if s > 0 else 0, "ic_mean": m, "win_rate": float((a > 0).mean())})
        start = start + pd.Timedelta(days=step_months * 30)
    if not results:
        return {"icir": -999, "ic_mean": 0, "win_rate": 0, "n_windows": 0}
    return {
        "icir": round(np.mean([r["icir"] for r in results]), 4),
        "ic_mean": round(np.mean([r["ic_mean"] for r in results]), 4),
        "win_rate": round(np.mean([r["win_rate"] for r in results]), 4),
        "n_windows": len(results), "windows": results,
    }


def main():
    _init_db()
    logger.info("Fetching data...")
    factor_df, price_lookup, all_dates, date_idx, h = fetch_data()
    df = build_merged_df(factor_df, price_lookup, all_dates, date_idx, h)
    logger.info(f"Merged: {len(df)} rows, {df['trade_date'].nunique()} dates")

    good_cols = ["z_rsrs", "z_flow", "z_mom", "z_rsi_momentum"]
    bad_cols = ["z_quality", "z_efficiency"]

    # ── Strategy C1: Two-layer sub-combination ──
    print("\n" + "="*80)
    print("  PRIORITY C: Two-Layer Factor Ensemble")
    print("="*80)

    # Layer 1 sub-combinations
    sub_combos = {
        "Momentum": {"z_rsrs": 0.5, "z_mom": 0.5},
        "FundFlow": {"z_rsrs": 0.5, "z_flow": 0.5},
        "Tech3": {"z_rsrs": 1/3, "z_flow": 1/3, "z_mom": 1/3},
        "MomFlow": {"z_flow": 0.5, "z_mom": 0.5},
        "RSRS_RSI": {"z_rsrs": 0.5, "z_rsi_momentum": 0.5},
        "Mom_RSI": {"z_mom": 0.5, "z_rsi_momentum": 0.5},
    }

    # Evaluate each sub-combo solo
    print("\n  Sub-combo solo performance:")
    for name, weights in sub_combos.items():
        composite = np.zeros(len(df))
        for col, w in weights.items():
            if col in df.columns:
                composite += w * df[col].fillna(0).values
        df[f"sub_{name}"] = composite
        r = rolling_eval(df, f"sub_{name}")
        print(f"    {name:<15}: ICIR={r['icir']:.4f}, IC={r['ic_mean']:.4f}, WR={r['win_rate']:.4f}")

    # Layer 2: Average pairs of sub-combos
    print("\n  Layer 2: Pairwise averaging of sub-combos:")
    sub_names = list(sub_combos.keys())
    best_overall = {"icir": -999}
    best_config = ""

    for i in range(len(sub_names)):
        for j in range(i + 1, len(sub_names)):
            n1, n2 = sub_names[i], sub_names[j]
            df["ensemble_2"] = (df[f"sub_{n1}"] + df[f"sub_{n2}"]) / 2
            r = rolling_eval(df, "ensemble_2")
            label = f"{n1}+{n2}"
            if r["icir"] > best_overall["icir"]:
                best_overall = r
                best_config = label
            print(f"    {label:<35}: ICIR={r['icir']:.4f}, IC={r['ic_mean']:.4f}, WR={r['win_rate']:.4f}")

    # Layer 2: Average ALL sub-combos
    all_sub_cols = [f"sub_{n}" for n in sub_names]
    df["ensemble_all"] = df[all_sub_cols].mean(axis=1)
    r = rolling_eval(df, "ensemble_all")
    print(f"    {'ALL sub-combos averaged':<35}: ICIR={r['icir']:.4f}, IC={r['ic_mean']:.4f}, WR={r['win_rate']:.4f}")
    if r["icir"] > best_overall["icir"]:
        best_overall = r
        best_config = "ALL sub-combos"

    # ── Strategy C2: Rank-voting ensemble ──
    print("\n  C2: Rank-voting ensemble (median of factor ranks):")
    for combo_cols in [
        ["z_rsrs", "z_mom"],
        ["z_rsrs", "z_flow", "z_mom"],
        ["z_rsrs", "z_flow", "z_mom", "z_rsi_momentum"],
    ]:
        # For each date, rank ETFs by each factor, then take median rank
        df["rank_composite"] = 0.0
        for col in combo_cols:
            for date, group in df.groupby("trade_date"):
                if len(group) >= MIN_ETF_COUNT:
                    ranks = group[col].rank()
                    df.loc[group.index, "rank_composite"] += ranks

        r = rolling_eval(df, "rank_composite")
        label = "+".join(c.split("_")[-1][:3] for c in combo_cols)
        print(f"    Rank-vote {label:<25}: ICIR={r['icir']:.4f}, IC={r['ic_mean']:.4f}, WR={r['win_rate']:.4f}")
        if r["icir"] > best_overall["icir"]:
            best_overall = r
            best_config = f"Rank-vote({label})"

    # ── Strategy C3: Inverse-IC-std weighting per window ──
    print("\n  C3: Inverse-IC-std weighting (train on expanding window):")
    df["date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    all_d = sorted(df["date"].unique())

    # Compute per-factor IC series using expanding window
    for col in good_cols:
        ic_series = []
        for date, group in df.groupby("trade_date"):
            if len(group) >= MIN_ETF_COUNT:
                ic = _spearman_ic(group[col], group["forward_ret"])
                ic_series.append({"trade_date": date, f"ic_{col}": ic})
        ic_df = pd.DataFrame(ic_series)
        if len(ic_df) > 0:
            df = df.merge(ic_df, on="trade_date", how="left")

    # Build adaptive composite: weight by cumulative IC (sign+stability)
    df_adapt = df.sort_values("date").copy()
    for col in good_cols:
        ic_col = f"ic_{col}"
        if ic_col in df_adapt.columns:
            # Expanding mean IC (cumulative signal)
            df_adapt[f"cum_ic_{col}"] = df_adapt[ic_col].expanding(min_periods=5).mean()

    # Adaptive composite: weight = sign(cumIC) * |cumIC|^0.5 (softer than ICIR²)
    df_adapt["adaptive_composite"] = 0.0
    total_signal = 0.0
    for col in good_cols:
        cum_col = f"cum_ic_{col}"
        if cum_col in df_adapt.columns:
            signal = df_adapt[cum_col].fillna(0)
            weight = np.sign(signal) * np.abs(signal) ** 0.5
            df_adapt["adaptive_composite"] += weight * df_adapt[col].fillna(0)
            total_signal += np.abs(weight)

    if total_signal > 0:
        r = rolling_eval(df_adapt, "adaptive_composite")
        print(f"    Adaptive (expanding IC signal): ICIR={r['icir']:.4f}, IC={r['ic_mean']:.4f}, WR={r['win_rate']:.4f}")
        if r["icir"] > best_overall["icir"]:
            best_overall = r
            best_config = "Adaptive expanding IC"

    # ── Strategy C4: Simple IC-weighted (no per-window split, full history) ──
    print("\n  C4: Full-history IC-weighted composite:")
    ic_weights = {}
    for col in good_cols:
        ic_col = f"ic_{col}"
        if ic_col in df.columns:
            valid_ic = df[ic_col].dropna()
            if len(valid_ic) > 10:
                m = valid_ic.mean()
                s = valid_ic.std()
                ic_weights[col] = m / s if s > 0 else 0

    # Weight proportional to ICIR², floor at 0
    icir_sq = {k: max(v**2, 0) for k, v in ic_weights.items()}
    total = sum(icir_sq.values())
    if total > 0:
        norm_weights = {k: v / total for k, v in icir_sq.items()}
        composite = np.zeros(len(df))
        for col, w in norm_weights.items():
            composite += w * df[col].fillna(0).values
        df["icir_weighted"] = composite
        r = rolling_eval(df, "icir_weighted")
        w_str = ", ".join(f"{k.split('_')[-1]}={v:.3f}" for k, v in norm_weights.items())
        print(f"    ICIR² weights ({w_str}): ICIR={r['icir']:.4f}, IC={r['ic_mean']:.4f}, WR={r['win_rate']:.4f}")
        if r["icir"] > best_overall["icir"]:
            best_overall = r
            best_config = f"ICIR² full-history"

    # ── FINAL ──
    print("\n" + "="*80)
    print(f"  BEST PRIORITY C RESULT: {best_config}")
    print(f"    ICIR={best_overall['icir']:.4f}, IC={best_overall['ic_mean']:.4f}, WR={best_overall['win_rate']:.4f}")
    if "windows" in best_overall:
        for j, wr in enumerate(best_overall["windows"]):
            print(f"    W{j+1}: ICIR={wr['icir']:.4f}, IC={wr['ic_mean']:.4f}, WR={wr['win_rate']:.4f}")

    icir_ok = best_overall["icir"] >= 0.70
    ic_ok = best_overall["ic_mean"] >= 0.10
    wr_ok = best_overall["win_rate"] >= 0.68
    print(f"\n  GOAL: ICIR {'PASS' if icir_ok else 'FAIL'}({best_overall['icir']:.4f}), "
          f"IC {'PASS' if ic_ok else 'FAIL'}({best_overall['ic_mean']:.4f}), "
          f"WR {'PASS' if wr_ok else 'FAIL'}({best_overall['win_rate']:.4f})")


if __name__ == "__main__":
    main()
