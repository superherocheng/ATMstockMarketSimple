"""Rapid factor weight optimizer for rolling window validation.

Works on existing Z-scores from factor_daily table — no need to recompute
raw factors. Recombines Z-scores with new weights and evaluates rolling IC.

Usage:
    python -m scripts.factor_optimizer [--preset short]
"""
import argparse
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
FACTOR_COLUMNS = ["z_rsrs", "z_flow", "z_mom", "z_quality", "z_efficiency", "z_rsi_momentum"]
FACTOR_NAMES = ["RSRS", "Flow", "Mom", "Quality", "Efficiency", "RSI_Mom"]


def _init_db():
    from dotenv import load_dotenv
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(project_root, ".env"))
    from src.core.db_manager_postgresql import init_db_manager
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set")
    init_db_manager(db_url)


def _spearman_ic(x, y):
    valid = pd.notna(x) & pd.notna(y)
    x, y = x[valid], y[valid]
    if len(x) < MIN_ETF_COUNT:
        return np.nan
    corr, _ = scipy_stats.spearmanr(x, y)
    return float(corr) if not np.isnan(corr) else np.nan


def fetch_data(preset_id="short"):
    """Fetch factor Z-scores and price data."""
    from sqlalchemy import text
    from src.core.db_manager_postgresql import get_conn

    conn = get_conn()
    try:
        preset_row = conn.execute(text(
            "SELECT forward_days FROM ic_summary "
            "WHERE preset_id = :pid LIMIT 1"
        ), {"pid": preset_id}).fetchone()
        h = int(preset_row[0]) if preset_row else 10

        factor_rows = conn.execute(text(
            "SELECT etf_code, trade_date, factor, "
            "z_rsrs, z_flow, z_mom, z_quality, z_efficiency, z_rsi_momentum "
            "FROM factor_daily WHERE preset_id = :pid ORDER BY trade_date"
        ), {"pid": preset_id}).fetchall()

        price_rows = conn.execute(text(
            "SELECT ts_code, trade_date, close FROM sector_etf_daily "
            "ORDER BY ts_code, trade_date"
        )).fetchall()
    finally:
        conn.close()

    factor_df = pd.DataFrame(factor_rows, columns=[
        "etf_code", "trade_date", "factor",
    ] + FACTOR_COLUMNS)
    price_df = pd.DataFrame(price_rows, columns=["ts_code", "trade_date", "close"])

    for df in [factor_df, price_df]:
        df["trade_date"] = df["trade_date"].apply(
            lambda d: str(d).replace("-", "") if hasattr(d, "strftime") else str(d))

    price_df["close"] = price_df["close"].astype(float)
    price_lookup = {}
    for _, row in price_df.iterrows():
        price_lookup[(row["ts_code"], row["trade_date"])] = row["close"]

    all_dates = sorted(price_df["trade_date"].unique())
    date_idx = {d: i for i, d in enumerate(all_dates)}

    return factor_df, price_lookup, all_dates, date_idx, h


def compute_forward_returns(factor_df, price_lookup, all_dates, date_idx, h):
    """Compute forward returns."""
    factor_dates = sorted(factor_df["trade_date"].unique())
    rows = []
    for t in factor_dates:
        if t not in date_idx:
            continue
        idx = date_idx[t]
        if idx + 1 + h >= len(all_dates):
            continue
        entry_date = all_dates[idx + 1]
        exit_date = all_dates[idx + 1 + h]

        day_factors = factor_df[factor_df["trade_date"] == t]
        for _, row in day_factors.iterrows():
            code = row["etf_code"]
            c_entry = price_lookup.get((code, entry_date))
            c_exit = price_lookup.get((code, exit_date))
            if c_entry and c_exit and c_entry > 0:
                rows.append({
                    "etf_code": code,
                    "trade_date": t,
                    "forward_ret": c_exit / c_entry - 1,
                    **{col: row[col] for col in FACTOR_COLUMNS},
                })
    return pd.DataFrame(rows)


def evaluate_weights(df, weights_dict, window_months=3, step_months=1):
    """Evaluate a weight combination using rolling windows.

    weights_dict: {factor_name: weight, ...} keys from FACTOR_COLUMNS
    Returns dict of average metrics.
    """
    # Build composite factor
    composite = np.zeros(len(df))
    for col in FACTOR_COLUMNS:
        w = weights_dict.get(col, 0.0)
        vals = df[col].fillna(0).values
        composite += w * vals

    df = df.copy()
    df["composite"] = composite

    df["date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    all_dates_sorted = sorted(df["date"].unique())

    if len(all_dates_sorted) < 30:
        return {"icir": -999, "ic_mean": 0, "win_rate": 0, "n_windows": 0}

    window_results = []
    start = all_dates_sorted[0]
    end = all_dates_sorted[-1]

    while True:
        window_end = start + pd.Timedelta(days=window_months * 30)
        if window_end > end:
            break

        mask = (df["date"] >= start) & (df["date"] < window_end)
        window_df = df[mask]

        if len(window_df) < 30:
            start = start + pd.Timedelta(days=step_months * 30)
            continue

        daily_ics = []
        for date, group in window_df.groupby("trade_date"):
            if len(group) < MIN_ETF_COUNT:
                continue
            ic = _spearman_ic(group["composite"], group["forward_ret"])
            if not np.isnan(ic):
                daily_ics.append(ic)

        if len(daily_ics) < 5:
            start = start + pd.Timedelta(days=step_months * 30)
            continue

        ic_arr = np.array(daily_ics)
        ic_mean = float(ic_arr.mean())
        ic_std = float(ic_arr.std())
        icir = ic_mean / ic_std if ic_std > 0 else 0
        win_rate = float((ic_arr > 0).mean())

        window_results.append({"icir": icir, "ic_mean": ic_mean, "win_rate": win_rate})
        start = start + pd.Timedelta(days=step_months * 30)

    if not window_results:
        return {"icir": -999, "ic_mean": 0, "win_rate": 0, "n_windows": 0}

    avg_icir = np.mean([r["icir"] for r in window_results])
    avg_ic = np.mean([r["ic_mean"] for r in window_results])
    avg_wr = np.mean([r["win_rate"] for r in window_results])

    return {
        "icir": round(avg_icir, 4),
        "ic_mean": round(avg_ic, 4),
        "win_rate": round(avg_wr, 4),
        "n_windows": len(window_results),
        "windows": window_results,
    }


def grid_search_weights(df, window_months=3, step_months=1):
    """Grid search over weight combinations focusing on Priority A.

    Strategy: systematically zero out harmful factors and re-allocate.
    """
    print("\n" + "="*80)
    print("  PRIORITY A: WEIGHT OPTIMIZATION (Grid Search)")
    print("="*80)

    # Baseline weights from short preset
    baseline = {
        "z_rsrs": 0.258, "z_flow": 0.129, "z_mom": 0.258,
        "z_quality": 0.184, "z_efficiency": 0.092, "z_rsi_momentum": 0.08
    }

    results = []

    # Test 1: Baseline
    r = evaluate_weights(df, baseline, window_months, step_months)
    results.append(("Baseline (current)", baseline, r))
    print(f"\n  Baseline: ICIR={r['icir']:.4f}, IC={r['ic_mean']:.4f}, WR={r['win_rate']:.4f}")

    # Test 2: Zero Quality
    w = dict(baseline)
    w["z_quality"] = 0.0
    _redistribute(w, "z_quality", ["z_rsrs", "z_flow", "z_mom", "z_efficiency", "z_rsi_momentum"])
    r = evaluate_weights(df, w, window_months, step_months)
    results.append(("Zero Quality", dict(w), r))
    print(f"  Zero Quality: ICIR={r['icir']:.4f}, IC={r['ic_mean']:.4f}, WR={r['win_rate']:.4f}")

    # Test 3: Zero Efficiency
    w = dict(baseline)
    w["z_efficiency"] = 0.0
    _redistribute(w, "z_efficiency", ["z_rsrs", "z_flow", "z_mom", "z_quality", "z_rsi_momentum"])
    r = evaluate_weights(df, w, window_months, step_months)
    results.append(("Zero Efficiency", dict(w), r))
    print(f"  Zero Efficiency: ICIR={r['icir']:.4f}, IC={r['ic_mean']:.4f}, WR={r['win_rate']:.4f}")

    # Test 4: Zero Quality + Efficiency
    w = dict(baseline)
    w["z_quality"] = 0.0
    w["z_efficiency"] = 0.0
    _redistribute(w, "z_quality", ["z_rsrs", "z_flow", "z_mom", "z_rsi_momentum"])
    _redistribute(w, "z_efficiency", ["z_rsrs", "z_flow", "z_mom", "z_rsi_momentum"])
    r = evaluate_weights(df, w, window_months, step_months)
    results.append(("Zero Quality+Eff", dict(w), r))
    print(f"  Zero Quality+Eff: ICIR={r['icir']:.4f}, IC={r['ic_mean']:.4f}, WR={r['win_rate']:.4f}")

    # Test 5: Zero Quality + Efficiency + RSI_Mom (pure 3-factor)
    w = dict(baseline)
    w["z_quality"] = 0.0
    w["z_efficiency"] = 0.0
    w["z_rsi_momentum"] = 0.0
    _redistribute(w, "z_quality", ["z_rsrs", "z_flow", "z_mom"])
    _redistribute(w, "z_efficiency", ["z_rsrs", "z_flow", "z_mom"])
    _redistribute(w, "z_rsi_momentum", ["z_rsrs", "z_flow", "z_mom"])
    r = evaluate_weights(df, w, window_months, step_months)
    results.append(("Pure 3-factor (RSRS+Flow+Mom)", dict(w), r))
    print(f"  Pure 3-factor: ICIR={r['icir']:.4f}, IC={r['ic_mean']:.4f}, WR={r['win_rate']:.4f}")

    # Test 6: Zero Quality + Efficiency, boost RSRS and Mom
    for rsrs_w, mom_w in [(0.30, 0.30), (0.35, 0.30), (0.30, 0.35), (0.40, 0.30), (0.35, 0.35)]:
        w = {
            "z_rsrs": rsrs_w, "z_flow": round(1.0 - rsrs_w - mom_w - 0.08, 4),
            "z_mom": mom_w, "z_quality": 0.0, "z_efficiency": 0.0,
            "z_rsi_momentum": 0.08
        }
        r = evaluate_weights(df, w, window_months, step_months)
        label = f"RSRS={rsrs_w},Mom={mom_w},Flow={w['z_flow']:.3f}"
        results.append((label, dict(w), r))
        print(f"  {label}: ICIR={r['icir']:.4f}, IC={r['ic_mean']:.4f}, WR={r['win_rate']:.4f}")

    # Test 7: Dynamic ICIR² weighting (Priority A core)
    print("\n  --- Dynamic ICIR² Weighting ---")
    r = evaluate_dynamic_weights(df, window_months, step_months)
    results.append(("Dynamic ICIR²", None, r))

    # Rank results by ICIR
    print("\n" + "="*80)
    print("  RANKING (by ICIR):")
    print("="*80)
    ranked = sorted(results, key=lambda x: x[2]["icir"], reverse=True)
    for i, (label, weights, r) in enumerate(ranked[:10], 1):
        print(f"  {i:>2}. ICIR={r['icir']:.4f} IC={r['ic_mean']:.4f} WR={r['win_rate']:.4f} | {label}")

    # Show best result details
    best_label, best_w, best_r = ranked[0]
    print(f"\n  BEST: {best_label}")
    if best_w:
        print(f"  Weights: {best_w}")
    if "windows" in best_r:
        print(f"  Per-window ICIR:")
        for j, wr in enumerate(best_r["windows"]):
            print(f"    Window {j+1}: ICIR={wr['icir']:.4f}, IC={wr['ic_mean']:.4f}, WR={wr['win_rate']:.4f}")

    return ranked


def _redistribute(weights, dead_key, alive_keys):
    """Redistribute dead weight proportionally to alive factors."""
    dead_w = weights[dead_key]
    alive_total = sum(weights.get(k, 0) for k in alive_keys)
    if alive_total > 0:
        scale = (alive_total + dead_w) / alive_total
        for k in alive_keys:
            weights[k] = round(weights.get(k, 0) * scale, 6)
    weights[dead_key] = 0.0


def evaluate_dynamic_weights(df, window_months=3, step_months=1):
    """Evaluate dynamic ICIR² weighting within each window.

    For each window:
    1. Compute per-factor ICIR on the first half (training)
    2. Weight ∝ max(ICIR², 0) — negative ICIR factors get zero weight
    3. Evaluate composite IC on the second half (validation)
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    all_dates_sorted = sorted(df["date"].unique())

    window_results = []
    start = all_dates_sorted[0]
    end = all_dates_sorted[-1]

    while True:
        window_end = start + pd.Timedelta(days=window_months * 30)
        if window_end > end:
            break

        mask = (df["date"] >= start) & (df["date"] < window_end)
        window_df = df[mask]
        if len(window_df) < 30:
            start = start + pd.Timedelta(days=window_months * 30)
            continue

        # Split into train/validation halves
        dates_in_window = sorted(window_df["date"].unique())
        mid = dates_in_window[len(dates_in_window) // 2]

        train_df = window_df[window_df["date"] <= mid]
        val_df = window_df[window_df["date"] > mid]

        # Compute per-factor ICIR on training half
        factor_icir = {}
        for col in FACTOR_COLUMNS:
            daily_ics = []
            for date, group in train_df.groupby("trade_date"):
                if len(group) < MIN_ETF_COUNT:
                    continue
                ic = _spearman_ic(group[col], group["forward_ret"])
                if not np.isnan(ic):
                    daily_ics.append(ic)
            if len(daily_ics) >= 3:
                m = np.mean(daily_ics)
                s = np.std(daily_ics)
                factor_icir[col] = m / s if s > 0 else 0
            else:
                factor_icir[col] = 0

        # Dynamic weights: ∝ max(ICIR², 0)
        icir_sq = {k: max(v**2, 0) for k, v in factor_icir.items()}
        total_icir_sq = sum(icir_sq.values())
        if total_icir_sq == 0:
            # Equal weight fallback
            weights = {col: 1.0 / len(FACTOR_COLUMNS) for col in FACTOR_COLUMNS}
        else:
            weights = {col: icir_sq[col] / total_icir_sq for col in FACTOR_COLUMNS}

        # Evaluate on validation half
        composite = np.zeros(len(val_df))
        for col in FACTOR_COLUMNS:
            composite += weights[col] * val_df[col].fillna(0).values
        val_df = val_df.copy()
        val_df["composite"] = composite

        daily_ics = []
        for date, group in val_df.groupby("trade_date"):
            if len(group) < MIN_ETF_COUNT:
                continue
            ic = _spearman_ic(group["composite"], group["forward_ret"])
            if not np.isnan(ic):
                daily_ics.append(ic)

        if len(daily_ics) >= 3:
            ic_arr = np.array(daily_ics)
            m = float(ic_arr.mean())
            s = float(ic_arr.std())
            icir = m / s if s > 0 else 0
            wr = float((ic_arr > 0).mean())
            window_results.append({
                "icir": icir, "ic_mean": m, "win_rate": wr,
                "weights": weights, "factor_icir": factor_icir,
            })

        start = start + pd.Timedelta(days=window_months * 30)

    if not window_results:
        return {"icir": -999, "ic_mean": 0, "win_rate": 0, "n_windows": 0}

    avg_icir = np.mean([r["icir"] for r in window_results])
    avg_ic = np.mean([r["ic_mean"] for r in window_results])
    avg_wr = np.mean([r["win_rate"] for r in window_results])

    print(f"  Dynamic ICIR²: ICIR={avg_icir:.4f}, IC={avg_ic:.4f}, WR={avg_wr:.4f}")
    print(f"    Per-window dynamic weights:")
    for j, wr in enumerate(window_results):
        w_str = ", ".join(f"{k.split('_')[-1]}={v:.3f}" for k, v in wr["weights"].items() if v > 0.01)
        print(f"    Window {j+1}: ICIR={wr['icir']:.4f} | {w_str}")

    return {
        "icir": round(avg_icir, 4),
        "ic_mean": round(avg_ic, 4),
        "win_rate": round(avg_wr, 4),
        "n_windows": len(window_results),
        "windows": window_results,
    }


def main():
    parser = argparse.ArgumentParser(description="Factor weight optimizer")
    parser.add_argument("--preset", default="short")
    parser.add_argument("--window", type=int, default=3)
    parser.add_argument("--step", type=int, default=1)
    args = parser.parse_args()

    _init_db()
    logger.info(f"Fetching data for preset={args.preset}...")
    factor_df, price_lookup, all_dates, date_idx, h = fetch_data(args.preset)
    logger.info(f"Factor data: {len(factor_df)} rows, {factor_df['trade_date'].nunique()} dates, H={h}")

    logger.info("Computing forward returns...")
    df = compute_forward_returns(factor_df, price_lookup, all_dates, date_idx, h)
    logger.info(f"Merged data: {len(df)} rows, {df['trade_date'].nunique()} dates")

    ranked = grid_search_weights(df, args.window, args.step)

    return ranked


if __name__ == "__main__":
    main()
