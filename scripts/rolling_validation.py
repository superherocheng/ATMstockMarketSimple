"""Rolling window validation framework for factor model iteration.

Computes per-window and per-factor IC/ICIR/win rate using rolling 3-month
windows with 1-month step. No look-ahead: factor at T predicts T+1 to T+1+H.

Usage:
    python -m scripts.rolling_validation [--preset short] [--window 3] [--step 1]
"""
import argparse
import sys
import os
import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

MIN_ETF_COUNT = 8

FACTOR_COLUMNS = ["z_rsrs", "z_flow", "z_mom", "z_quality", "z_efficiency", "z_rsi_momentum"]
FACTOR_NAMES = ["RSRS", "Flow", "Mom", "Quality", "Efficiency", "RSI_Mom"]


def _spearman_ic(x, y):
    valid = pd.notna(x) & pd.notna(y)
    x, y = x[valid], y[valid]
    if len(x) < MIN_ETF_COUNT:
        return np.nan
    corr, _ = scipy_stats.spearmanr(x, y)
    return float(corr) if not np.isnan(corr) else np.nan


def _init_db():
    """Initialize DB connection from .env or env var."""
    from dotenv import load_dotenv
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(project_root, ".env"))
    from src.core.db_manager_postgresql import init_db_manager
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set")
    init_db_manager(db_url)


def fetch_data(preset_id="short"):
    """Fetch factor values and price data from DB."""
    from sqlalchemy import text
    from src.core.db_manager_postgresql import get_conn

    conn = get_conn()
    try:
        preset_row = conn.execute(text(
            "SELECT forward_days FROM ic_summary "
            "WHERE preset_id = :pid LIMIT 1"
        ), {"pid": preset_id}).fetchone()
        if preset_row:
            h = int(preset_row[0])
        else:
            h = 10

        factor_rows = conn.execute(text(
            "SELECT etf_code, trade_date, factor, "
            "z_rsrs, z_flow, z_mom, z_quality, z_efficiency, z_rsi_momentum, "
            "quadrant "
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
        "z_rsrs", "z_flow", "z_mom", "z_quality", "z_efficiency", "z_rsi_momentum",
        "quadrant"
    ])
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
    """Compute forward returns for each (etf_code, trade_date) pair."""
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
                fwd_ret = c_exit / c_entry - 1
                rows.append({
                    "etf_code": code,
                    "trade_date": t,
                    "forward_ret": fwd_ret,
                    "factor": row["factor"],
                    "z_rsrs": row["z_rsrs"],
                    "z_flow": row["z_flow"],
                    "z_mom": row["z_mom"],
                    "z_quality": row["z_quality"],
                    "z_efficiency": row["z_efficiency"],
                    "z_rsi_momentum": row["z_rsi_momentum"],
                })

    return pd.DataFrame(rows)


def rolling_window_stats(df, window_months=3, step_months=1):
    """Compute IC stats for each rolling window.

    Returns DataFrame with one row per window.
    """
    df["date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    all_dates = sorted(df["date"].unique())

    if len(all_dates) < 30:
        print(f"WARNING: Only {len(all_dates)} trading days available. Need more data.")
        return pd.DataFrame()

    windows = []
    start = all_dates[0]
    end = all_dates[-1]

    while True:
        window_end = start + timedelta(days=window_months * 30)
        if window_end > end:
            break

        mask = (df["date"] >= start) & (df["date"] < window_end)
        window_df = df[mask]

        if len(window_df) < 50:  # Need enough data points
            start = start + timedelta(days=step_months * 30)
            continue

        # Group by date, compute IC per date
        daily_ics = []
        factor_daily_ics = {name: [] for name in FACTOR_NAMES}
        factor_daily_ics["Composite"] = []

        for date, group in window_df.groupby("trade_date"):
            if len(group) < MIN_ETF_COUNT:
                continue

            # Composite IC
            ic = _spearman_ic(group["factor"], group["forward_ret"])
            if not np.isnan(ic):
                daily_ics.append(ic)
                factor_daily_ics["Composite"].append(ic)

            # Per-factor IC
            for col, name in zip(FACTOR_COLUMNS, FACTOR_NAMES):
                fic = _spearman_ic(group[col], group["forward_ret"])
                if not np.isnan(fic):
                    factor_daily_ics[name].append(fic)

        if len(daily_ics) < 5:
            start = start + timedelta(days=step_months * 30)
            continue

        ic_arr = np.array(daily_ics)
        ic_mean = float(ic_arr.mean())
        ic_std = float(ic_arr.std())
        icir = ic_mean / ic_std if ic_std > 0 else 0
        win_rate = float((ic_arr > 0).mean())

        row = {
            "window_start": start.strftime("%Y-%m-%d"),
            "window_end": window_end.strftime("%Y-%m-%d"),
            "n_days": len(daily_ics),
            "ic_mean": round(ic_mean, 4),
            "ic_std": round(ic_std, 4),
            "icir": round(icir, 4),
            "win_rate": round(win_rate, 4),
        }

        # Per-factor stats
        for name in FACTOR_NAMES + ["Composite"]:
            arr = np.array(factor_daily_ics[name])
            if len(arr) >= 3:
                m = float(arr.mean())
                s = float(arr.std())
                row[f"{name}_ICIR"] = round(m / s, 4) if s > 0 else 0
                row[f"{name}_IC"] = round(m, 4)
                row[f"{name}_WR"] = round(float((arr > 0).mean()), 4)
            else:
                row[f"{name}_ICIR"] = np.nan
                row[f"{name}_IC"] = np.nan
                row[f"{name}_WR"] = np.nan

        windows.append(row)
        start = start + timedelta(days=step_months * 30)

    return pd.DataFrame(windows)


def print_summary(windows_df, label=""):
    """Print formatted summary of rolling window results."""
    if windows_df.empty:
        print("No windows to summarize.")
        return {}

    print(f"\n{'='*80}")
    print(f"  ROLLING WINDOW VALIDATION {label}")
    print(f"{'='*80}")
    print(f"  Windows: {len(windows_df)}")
    print(f"  Period: {windows_df['window_start'].iloc[0]} -> {windows_df['window_end'].iloc[-1]}")
    print()

    # Composite stats
    avg_icir = windows_df["icir"].mean()
    avg_ic = windows_df["ic_mean"].mean()
    avg_wr = windows_df["win_rate"].mean()

    print(f"  COMPOSITE FACTOR:")
    print(f"    Avg ICIR    = {avg_icir:.4f}")
    print(f"    Avg IC mean = {avg_ic:.4f}")
    print(f"    Avg WinRate = {avg_wr:.4f}")
    print()

    # Per-factor ICIR
    print(f"  PER-FACTOR ROLLING ICIR (avg across windows):")
    print(f"  {'Factor':<12} {'Avg ICIR':>10} {'Avg IC':>10} {'Avg WR':>10} {'ICIR<0.2':>10}")
    for name in FACTOR_NAMES:
        icir_vals = windows_df[f"{name}_ICIR"].dropna()
        ic_vals = windows_df[f"{name}_IC"].dropna()
        wr_vals = windows_df[f"{name}_WR"].dropna()
        weak_count = (icir_vals < 0.2).sum()
        print(f"  {name:<12} {icir_vals.mean():>10.4f} {ic_vals.mean():>10.4f} {wr_vals.mean():>10.4f} {weak_count:>10}/{len(icir_vals)}")

    print()

    # Window-by-window detail
    print(f"  WINDOW DETAIL:")
    print(f"  {'Window':<28} {'ICIR':>7} {'IC':>7} {'WR':>7} {'N':>5}")
    for _, row in windows_df.iterrows():
        print(f"  {row['window_start']} ~ {row['window_end']:<10} "
              f"{row['icir']:>7.4f} {row['ic_mean']:>7.4f} {row['win_rate']:>7.4f} {row['n_days']:>5}")

    print(f"{'='*80}")

    return {
        "avg_icir": avg_icir,
        "avg_ic": avg_ic,
        "avg_wr": avg_wr,
    }


def main():
    parser = argparse.ArgumentParser(description="Rolling window factor validation")
    parser.add_argument("--preset", default="short", help="Preset ID (short/medium/long)")
    parser.add_argument("--window", type=int, default=3, help="Window size in months")
    parser.add_argument("--step", type=int, default=1, help="Step size in months")
    args = parser.parse_args()

    _init_db()
    logger.info(f"Fetching data for preset={args.preset}...")
    factor_df, price_lookup, all_dates, date_idx, h = fetch_data(args.preset)
    logger.info(f"Factor data: {len(factor_df)} rows, {factor_df['trade_date'].nunique()} dates")
    logger.info(f"Forward period H={h}")

    logger.info("Computing forward returns...")
    df = compute_forward_returns(factor_df, price_lookup, all_dates, date_idx, h)
    logger.info(f"Merged data: {len(df)} rows, {df['trade_date'].nunique()} dates")

    logger.info(f"Computing rolling {args.window}-month windows (step={args.step} month)...")
    windows_df = rolling_window_stats(df, args.window, args.step)

    stats = print_summary(windows_df, label=f"[preset={args.preset}]")

    # Print per-window per-factor ICIR for detailed diagnosis
    if not windows_df.empty:
        print("\n  PER-FACTOR ICIR PER WINDOW:")
        header = f"  {'Window':<28}"
        for name in FACTOR_NAMES:
            header += f" {name:>10}"
        print(header)
        for _, row in windows_df.iterrows():
            line = f"  {row['window_start']} ~ {row['window_end']:<10}"
            for name in FACTOR_NAMES:
                v = row.get(f"{name}_ICIR", np.nan)
                line += f" {v:>10.4f}" if not np.isnan(v) else f" {'N/A':>10}"
            print(line)

    # Goal check
    if stats:
        print(f"\n  GOAL CHECK:")
        icir_ok = stats['avg_icir'] >= 0.70
        ic_ok = stats['avg_ic'] >= 0.10
        wr_ok = stats['avg_wr'] >= 0.68
        print(f"    ICIR >= 0.70: {'PASS' if icir_ok else 'FAIL'} ({stats['avg_icir']:.4f})")
        print(f"    IC   >= 0.10: {'PASS' if ic_ok else 'FAIL'} ({stats['avg_ic']:.4f})")
        print(f"    WR   >= 0.68: {'PASS' if wr_ok else 'FAIL'} ({stats['avg_wr']:.4f})")
        if icir_ok and ic_ok and wr_ok:
            print("    *** ALL GOALS MET ***")
        else:
            missing = []
            if not icir_ok: missing.append("ICIR")
            if not ic_ok: missing.append("IC")
            if not wr_ok: missing.append("WR")
            print(f"    Missing: {', '.join(missing)}")

    return windows_df


if __name__ == "__main__":
    main()
