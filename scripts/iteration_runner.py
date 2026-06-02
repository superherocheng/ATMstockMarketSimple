"""Fine-grained weight search + Priority B new factor testing.

Iterates over:
1. Fine-grained RSRS/Flow/Mom/RSI weight grid
2. New synthetic factors (low-vol, short-term reversal)
"""
import sys
import os
import logging
from itertools import product

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


def fetch_all_data(preset_id="short"):
    """Fetch raw price + share data for factor construction."""
    from sqlalchemy import text
    from src.core.db_manager_postgresql import get_conn

    conn = get_conn()
    try:
        h_row = conn.execute(text(
            "SELECT forward_days FROM ic_summary WHERE preset_id = :pid LIMIT 1"
        ), {"pid": preset_id}).fetchone()
        h = int(h_row[0]) if h_row else 10

        kline_rows = conn.execute(text(
            "SELECT ts_code, trade_date, open, high, low, close, pct_chg "
            "FROM sector_etf_daily ORDER BY ts_code, trade_date"
        )).fetchall()

        share_rows = conn.execute(text(
            "SELECT ts_code, trade_date, fd_share FROM etf_share ORDER BY ts_code, trade_date"
        )).fetchall()

        factor_rows = conn.execute(text(
            "SELECT etf_code, trade_date, factor, "
            "z_rsrs, z_flow, z_mom, z_quality, z_efficiency, z_rsi_momentum "
            "FROM factor_daily WHERE preset_id = :pid ORDER BY trade_date"
        ), {"pid": preset_id}).fetchall()
    finally:
        conn.close()

    kline_df = pd.DataFrame(kline_rows, columns=["ts_code", "trade_date", "open", "high", "low", "close", "pct_chg"])
    share_df = pd.DataFrame(share_rows, columns=["ts_code", "trade_date", "fd_share"])
    factor_df = pd.DataFrame(factor_rows, columns=["etf_code", "trade_date", "factor"] + FACTOR_COLS)

    for df in [kline_df, share_df, factor_df]:
        df["trade_date"] = df["trade_date"].apply(
            lambda d: str(d).replace("-", "") if hasattr(d, "strftime") else str(d))

    kline_df["close"] = kline_df["close"].astype(float)
    kline_df["high"] = kline_df["high"].astype(float)
    kline_df["low"] = kline_df["low"].astype(float)
    kline_df["pct_chg"] = kline_df["pct_chg"].astype(float)
    share_df["fd_share"] = share_df["fd_share"].astype(float)

    price_lookup = {}
    for _, row in kline_df.iterrows():
        price_lookup[(row["ts_code"], row["trade_date"])] = row["close"]

    all_dates = sorted(kline_df["trade_date"].unique())
    date_idx = {d: i for i, d in enumerate(all_dates)}

    return kline_df, share_df, factor_df, price_lookup, all_dates, date_idx, h


def _rank_zscore(values):
    """Cross-sectional rank-based Z-score."""
    ranks = values.rank()
    rs = ranks.std()
    if rs == 0 or pd.isna(rs):
        return pd.Series(0.0, index=values.index)
    return (ranks - ranks.mean()) / rs


def compute_new_factors(kline_df, share_df, all_dates, date_idx, h, price_lookup):
    """Compute new candidate factors from raw data.

    Returns a DataFrame with columns: etf_code, trade_date, forward_ret,
    z_rsrs, z_flow, z_mom (existing) + new factors.
    """
    # ── Compute per-ETF factor series ──
    raw_parts = []
    for code in kline_df["ts_code"].unique():
        ek = kline_df[kline_df["ts_code"] == code].sort_values("trade_date").copy()
        es = share_df[share_df["ts_code"] == code].sort_values("trade_date").copy()

        if len(ek) < 30:
            continue

        closes = ek["close"].values
        highs = ek["high"].values
        lows = ek["low"].values
        pcts = ek["pct_chg"].values
        shares = es["fd_share"].values if len(es) > 0 else np.array([])

        df = ek[["ts_code", "trade_date"]].copy()

        # New Factor A: Low Volatility (neg rank of 3-month return std)
        vol_window = 60
        n = len(closes)
        low_vol = np.full(n, np.nan)
        for i in range(vol_window, n):
            rets = np.diff(closes[i - vol_window:i + 1]) / closes[i - vol_window:i]
            if len(rets) >= 30:
                low_vol[i] = -np.std(rets, ddof=0)  # Negative: low vol = high score
        df["low_vol"] = low_vol

        # New Factor B: Short-term Reversal (neg rank of 5-day return)
        rev5 = np.full(n, np.nan)
        for i in range(5, n):
            if closes[i - 5] > 0:
                rev5[i] = -(closes[i] / closes[i - 5] - 1)  # Negative: recent losers get high score
        df["short_rev"] = rev5

        # New Factor C: Rank-RSRS (percentile RSRS - more robust)
        from src.analysis.factor_engine import _compute_rsrs_series
        rsrs_raw = _compute_rsrs_series(highs, lows, 20)
        df["rsrs_raw"] = rsrs_raw

        # New Factor D: Rank-Mom (rank percentile instead of vol-adj)
        rank_mom = np.full(n, np.nan)
        for i in range(20, n):
            rank_mom[i] = closes[i] / closes[i - 20] - 1
        df["rank_mom"] = rank_mom

        raw_parts.append(df)

    if not raw_parts:
        return pd.DataFrame()

    raw_all = pd.concat(raw_parts, ignore_index=True)

    # ── Compute cross-sectional Z-scores per date ──
    new_factor_cols = ["low_vol", "short_rev"]
    all_new_dates = sorted(raw_all["trade_date"].unique())

    zscore_rows = []
    for d in all_new_dates:
        day = raw_all[raw_all["trade_date"] == d].copy()
        day = day.dropna(subset=["low_vol", "short_rev"])
        if len(day) < MIN_ETF_COUNT:
            continue
        for col in new_factor_cols:
            day[f"z_{col}"] = _rank_zscore(day[col]).values
        for _, row in day.iterrows():
            zscore_rows.append({
                "etf_code": row["ts_code"],
                "trade_date": row["trade_date"],
                "z_low_vol": row["z_low_vol"],
                "z_short_rev": row["z_short_rev"],
            })

    new_z_df = pd.DataFrame(zscore_rows)

    if new_z_df.empty:
        return pd.DataFrame()

    # ── Compute forward returns ──
    fwd_rows = []
    factor_dates = sorted(new_z_df["trade_date"].unique())
    for t in factor_dates:
        if t not in date_idx:
            continue
        idx = date_idx[t]
        if idx + 1 + h >= len(all_dates):
            continue
        entry_date = all_dates[idx + 1]
        exit_date = all_dates[idx + 1 + h]

        day_z = new_z_df[new_z_df["trade_date"] == t]
        for _, row in day_z.iterrows():
            code = row["etf_code"]
            c_e = price_lookup.get((code, entry_date))
            c_x = price_lookup.get((code, exit_date))
            if c_e and c_x and c_e > 0:
                fwd_rows.append({
                    "etf_code": code,
                    "trade_date": t,
                    "forward_ret": c_x / c_e - 1,
                    "z_low_vol": row["z_low_vol"],
                    "z_short_rev": row["z_short_rev"],
                })

    return pd.DataFrame(fwd_rows)


def evaluate_combo(df_merged, weight_dict, window_months=3, step_months=1):
    """Evaluate a weight combination on merged data."""
    composite = np.zeros(len(df_merged))
    for col, w in weight_dict.items():
        if col in df_merged.columns:
            composite += w * df_merged[col].fillna(0).values

    df = df_merged.copy()
    df["composite"] = composite
    df["date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    all_d = sorted(df["date"].unique())

    results = []
    start = all_d[0]
    end = all_d[-1]
    while True:
        w_end = start + pd.Timedelta(days=window_months * 30)
        if w_end > end:
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
            ic = _spearman_ic(g["composite"], g["forward_ret"])
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
        "n_windows": len(results),
        "windows": results,
    }


def main():
    _init_db()
    logger.info("Fetching all data...")
    kline_df, share_df, factor_df, price_lookup, all_dates, date_idx, h = fetch_all_data("short")
    logger.info(f"Kline: {len(kline_df)}, Share: {len(share_df)}, Factor: {len(factor_df)}, H={h}")

    # ── Merge existing Z-scores with forward returns ──
    fwd_rows = []
    factor_dates = sorted(factor_df["trade_date"].unique())
    for t in factor_dates:
        if t not in date_idx:
            continue
        idx = date_idx[t]
        if idx + 1 + h >= len(all_dates):
            continue
        entry_date = all_dates[idx + 1]
        exit_date = all_dates[idx + 1 + h]
        day = factor_df[factor_df["trade_date"] == t]
        for _, row in day.iterrows():
            code = row["etf_code"]
            c_e = price_lookup.get((code, entry_date))
            c_x = price_lookup.get((code, exit_date))
            if c_e and c_x and c_e > 0:
                fwd_rows.append({
                    "etf_code": code, "trade_date": t,
                    "forward_ret": c_x / c_e - 1,
                    **{col: row[col] for col in FACTOR_COLS},
                })
    base_df = pd.DataFrame(fwd_rows)
    logger.info(f"Base merged: {len(base_df)} rows, {base_df['trade_date'].nunique()} dates")

    # ── Compute new factors ──
    logger.info("Computing new candidate factors...")
    new_df = compute_new_factors(kline_df, share_df, all_dates, date_idx, h, price_lookup)
    logger.info(f"New factors: {len(new_df)} rows")

    # Merge new factors into base
    if not new_df.empty:
        merge_cols = ["etf_code", "trade_date", "z_low_vol", "z_short_rev"]
        merged = base_df.merge(new_df[merge_cols], on=["etf_code", "trade_date"], how="left")
        merged["z_low_vol"] = merged["z_low_vol"].fillna(0)
        merged["z_short_rev"] = merged["z_short_rev"].fillna(0)
    else:
        merged = base_df.copy()
        merged["z_low_vol"] = 0
        merged["z_short_rev"] = 0

    # ── PHASE 1: Fine-grained weight search on 3 good factors ──
    print("\n" + "="*80)
    print("  PHASE 1: Fine-grained RSRS/Flow/Mom weight search")
    print("="*80)

    best_result = None
    best_weights = None
    best_label = ""

    for rsrs_w in [0.35, 0.38, 0.40, 0.42, 0.45, 0.48, 0.50]:
        for mom_w in [0.25, 0.28, 0.30, 0.32, 0.35]:
            for rsi_w in [0.0, 0.05, 0.08, 0.10]:
                flow_w = round(1.0 - rsrs_w - mom_w - rsi_w, 4)
                if flow_w < 0.05 or flow_w > 0.40:
                    continue
                w = {
                    "z_rsrs": rsrs_w, "z_flow": flow_w, "z_mom": mom_w,
                    "z_quality": 0, "z_efficiency": 0, "z_rsi_momentum": rsi_w,
                }
                r = evaluate_combo(merged, w)
                label = f"R={rsrs_w},M={mom_w},F={flow_w:.3f},RSI={rsi_w}"
                if r["icir"] > (best_result["icir"] if best_result else -999):
                    best_result = r
                    best_weights = w
                    best_label = label

    print(f"  Best Phase 1: {best_label}")
    print(f"    ICIR={best_result['icir']:.4f}, IC={best_result['ic_mean']:.4f}, WR={best_result['win_rate']:.4f}")
    if "windows" in best_result:
        for j, wr in enumerate(best_result["windows"]):
            print(f"    Window {j+1}: ICIR={wr['icir']:.4f}, IC={wr['ic_mean']:.4f}, WR={wr['win_rate']:.4f}")

    # ── PHASE 2: Add new factors (Priority B) ──
    print("\n" + "="*80)
    print("  PHASE 2: Priority B — New factor addition")
    print("="*80)

    # First, evaluate new factors solo
    for col, name in [("z_low_vol", "Low-Vol"), ("z_short_rev", "Short-Rev")]:
        r = evaluate_combo(merged, {col: 1.0})
        print(f"  Solo {name}: ICIR={r['icir']:.4f}, IC={r['ic_mean']:.4f}, WR={r['win_rate']:.4f}")

    # Try adding new factors to best Phase 1 weights
    for new_col, new_name in [("z_low_vol", "Low-Vol"), ("z_short_rev", "Short-Rev")]:
        for new_w in [0.05, 0.10, 0.15, 0.20]:
            w = dict(best_weights)
            # Scale down existing weights proportionally
            scale = 1.0 - new_w
            for k in w:
                w[k] = round(w[k] * scale, 6)
            w[new_col] = new_w
            r = evaluate_combo(merged, w)
            label = f"Best+{new_name}={new_w}"
            print(f"  {label}: ICIR={r['icir']:.4f}, IC={r['ic_mean']:.4f}, WR={r['win_rate']:.4f}")
            if r["icir"] > best_result["icir"]:
                best_result = r
                best_weights = w
                best_label = label

    # Try both new factors together
    for lv_w in [0.05, 0.10, 0.15]:
        for sr_w in [0.05, 0.10, 0.15]:
            w = dict(best_weights)
            total_new = lv_w + sr_w
            scale = 1.0 - total_new
            for k in w:
                w[k] = round(w[k] * scale, 6)
            w["z_low_vol"] = lv_w
            w["z_short_rev"] = sr_w
            r = evaluate_combo(merged, w)
            label = f"Best+LV={lv_w}+SR={sr_w}"
            if r["icir"] > best_result["icir"]:
                best_result = r
                best_weights = w
                best_label = label
                print(f"  {label}: ICIR={r['icir']:.4f}, IC={r['ic_mean']:.4f}, WR={r['win_rate']:.4f} *** NEW BEST")

    # ── FINAL RESULT ──
    print("\n" + "="*80)
    print(f"  OVERALL BEST: {best_label}")
    print(f"    ICIR={best_result['icir']:.4f}, IC={best_result['ic_mean']:.4f}, WR={best_result['win_rate']:.4f}")
    print(f"    Weights: {best_weights}")
    if "windows" in best_result:
        print(f"    Per-window:")
        for j, wr in enumerate(best_result["windows"]):
            print(f"      W{j+1}: ICIR={wr['icir']:.4f}, IC={wr['ic_mean']:.4f}, WR={wr['win_rate']:.4f}")

    # Goal check
    icir_ok = best_result["icir"] >= 0.70
    ic_ok = best_result["ic_mean"] >= 0.10
    wr_ok = best_result["win_rate"] >= 0.68
    print(f"\n  GOAL CHECK: ICIR {'PASS' if icir_ok else 'FAIL'}({best_result['icir']:.4f}), "
          f"IC {'PASS' if ic_ok else 'FAIL'}({best_result['ic_mean']:.4f}), "
          f"WR {'PASS' if wr_ok else 'FAIL'}({best_result['win_rate']:.4f})")

    return best_result, best_weights


if __name__ == "__main__":
    main()
