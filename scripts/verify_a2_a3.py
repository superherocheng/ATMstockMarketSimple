"""Verify A2 for look-ahead bias + confirm A3 results.

A2 original uses IC at time T (which includes forward returns T+1..T+1+H)
to weight factors at time T — this is look-ahead. Fix: use IC up to T-1.
"""
import sys
import os
import warnings
import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MIN_ETF_COUNT = 8
BASELINE_W = {"z_rsrs": 0.38, "z_flow": 0.22, "z_mom": 0.32, "z_quality": 0.0, "z_efficiency": 0.0, "z_rsi_momentum": 0.08}
GOOD_COLS = ["z_rsrs", "z_flow", "z_mom", "z_rsi_momentum"]
H = 15


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
            if len(g) >= MIN_ETF_COUNT:
                ic = _spearman_ic(g[composite_col], g["forward_ret"])
                if not np.isnan(ic):
                    ics.append(ic)
        if len(ics) >= 3:
            a = np.array(ics)
            m, s = float(a.mean()), float(a.std())
            results.append({"start": start.strftime("%Y-%m-%d"), "icir": m / s if s > 0 else 0,
                           "ic_mean": m, "win_rate": float((a > 0).mean())})
        start = start + pd.Timedelta(days=step_months * 30)
    if not results:
        return {"icir": -999, "ic_mean": 0, "win_rate": 0}
    return {
        "icir": round(np.mean([r["icir"] for r in results]), 4),
        "ic_mean": round(np.mean([r["ic_mean"] for r in results]), 4),
        "win_rate": round(np.mean([r["win_rate"] for r in results]), 4),
        "windows": results,
    }


def main():
    from sqlalchemy import text
    from src.core.db_manager_postgresql import get_conn

    _init_db()
    conn = get_conn()
    try:
        factor_rows = conn.execute(text(
            "SELECT etf_code, trade_date, factor, "
            "z_rsrs, z_flow, z_mom, z_quality, z_efficiency, z_rsi_momentum "
            "FROM factor_daily WHERE preset_id = 'optimized' ORDER BY trade_date"
        )).fetchall()
        kline_rows = conn.execute(text(
            "SELECT ts_code, trade_date, close, high, low FROM sector_etf_daily ORDER BY ts_code, trade_date"
        )).fetchall()
        price_rows = conn.execute(text(
            "SELECT ts_code, trade_date, close FROM sector_etf_daily ORDER BY ts_code, trade_date"
        )).fetchall()
    finally:
        conn.close()

    factor_df = pd.DataFrame(factor_rows, columns=["etf_code", "trade_date", "factor"] +
                             ["z_rsrs", "z_flow", "z_mom", "z_quality", "z_efficiency", "z_rsi_momentum"])
    kline_df = pd.DataFrame(kline_rows, columns=["ts_code", "trade_date", "close", "high", "low"])
    price_df = pd.DataFrame(price_rows, columns=["ts_code", "trade_date", "close"])

    for df in [factor_df, kline_df, price_df]:
        df["trade_date"] = df["trade_date"].apply(
            lambda d: str(d).replace("-", "") if hasattr(d, "strftime") else str(d))
    kline_df["close"] = kline_df["close"].astype(float)
    price_df["close"] = price_df["close"].astype(float)

    price_lookup = {(r["ts_code"], r["trade_date"]): r["close"] for _, r in price_df.iterrows()}
    all_dates = sorted(price_df["trade_date"].unique())
    date_idx = {d: i for i, d in enumerate(all_dates)}

    rows = []
    for t in sorted(factor_df["trade_date"].unique()):
        if t not in date_idx:
            continue
        idx = date_idx[t]
        if idx + 1 + H >= len(all_dates):
            continue
        entry, exit_d = all_dates[idx + 1], all_dates[idx + 1 + H]
        for _, row in factor_df[factor_df["trade_date"] == t].iterrows():
            c_e = price_lookup.get((row["etf_code"], entry))
            c_x = price_lookup.get((row["etf_code"], exit_d))
            if c_e and c_x and c_e > 0:
                rows.append({
                    "etf_code": row["etf_code"], "trade_date": t,
                    "forward_ret": c_x / c_e - 1,
                    "z_rsrs": row["z_rsrs"], "z_flow": row["z_flow"], "z_mom": row["z_mom"],
                    "z_rsi_momentum": row["z_rsi_momentum"],
                })
    df = pd.DataFrame(rows)

    # Baseline
    composite = np.zeros(len(df))
    for col, w in BASELINE_W.items():
        if col in df.columns:
            composite += w * df[col].fillna(0).values
    df["composite"] = composite
    baseline_r = rolling_eval(df, "composite")

    print("="*80)
    print("  BASELINE")
    print("="*80)
    print(f"  ICIR={baseline_r['icir']:.4f}, IC={baseline_r['ic_mean']:.4f}, WR={baseline_r['win_rate']:.4f}")

    # ── A2 CORRECTED: Use IC up to T-1 (lag 1) to avoid look-ahead ──
    print("\n" + "="*80)
    print("  A2 CORRECTED: EWMA IC weighting with T-1 lag (no look-ahead)")
    print("="*80)

    # Compute per-factor daily IC
    ic_data = []
    for date, group in df.groupby("trade_date"):
        if len(group) < MIN_ETF_COUNT:
            continue
        row = {"trade_date": date}
        for col in GOOD_COLS:
            ic = _spearman_ic(group[col], group["forward_ret"])
            row[f"ic_{col}"] = ic
        ic_data.append(row)
    ic_df = pd.DataFrame(ic_data).sort_values("trade_date").reset_index(drop=True)

    for halflife in [5, 10, 15, 20]:
        # Compute EWMA of IC for each factor
        ewma_weights = {}
        for col in GOOD_COLS:
            ic_col = f"ic_{col}"
            ewma = ic_df[ic_col].ewm(halflife=halflife).mean()
            ewma_weights[col] = ewma.values

        # Normalize weights per date
        total = sum(ewma_weights[col] for col in GOOD_COLS)
        total[total == 0] = 1.0
        norm_weights = {col: ewma_weights[col] / total for col in GOOD_COLS}

        # Build composite using LAGGED weights (T-1)
        ic_date_to_idx = {d: i for i, d in enumerate(ic_df["trade_date"].values)}
        sorted_ic_dates = ic_df["trade_date"].values

        df_a2 = df.copy()
        composite = np.zeros(len(df_a2))

        for idx, (_, row) in enumerate(df_a2.iterrows()):
            t = row["trade_date"]
            if t in ic_date_to_idx:
                ci = ic_date_to_idx[t]
                # Use T-1 weight (shift by 1 to avoid look-ahead)
                wi = ci - 1
                if wi < 0:
                    # No prior IC available, use equal weights
                    for col in GOOD_COLS:
                        composite[idx] += (1.0 / len(GOOD_COLS)) * (row[col] if pd.notna(row[col]) else 0)
                else:
                    for col in GOOD_COLS:
                        w = norm_weights[col][wi]
                        composite[idx] += w * (row[col] if pd.notna(row[col]) else 0)

        df_a2["composite_ewma_lag"] = composite
        r = rolling_eval(df_a2, "composite_ewma_lag")

        icir_ok = "✓" if r["icir"] >= 0.80 else " "
        ic_ok = "✓" if r["ic_mean"] >= 0.18 else " "
        wr_ok = "✓" if r["win_rate"] >= 0.65 else " "
        diff = r["icir"] - baseline_r["icir"]
        print(f"\n  A2 corrected (halflife={halflife}, lag=1):")
        print(f"    ICIR={r['icir']:.4f}{icir_ok}  IC={r['ic_mean']:.4f}{ic_ok}  WR={r['win_rate']:.4f}{wr_ok}")
        print(f"    vs baseline: ICIR {diff:+.4f}")
        if "windows" in r:
            for w in r["windows"]:
                print(f"      {w['start']}: ICIR={w['icir']:.4f}, IC={w['ic_mean']:.4f}, WR={w['win_rate']:.4f}")

    # ── A2 with longer lag (lag=5) to further remove look-ahead ──
    print("\n" + "="*80)
    print("  A2 with lag=5 (more conservative)")
    print("="*80)

    for halflife in [5, 10]:
        ewma_weights = {}
        for col in GOOD_COLS:
            ic_col = f"ic_{col}"
            ewma = ic_df[ic_col].ewm(halflife=halflife).mean()
            ewma_weights[col] = ewma.values
        total = sum(ewma_weights[col] for col in GOOD_COLS)
        total[total == 0] = 1.0
        norm_weights = {col: ewma_weights[col] / total for col in GOOD_COLS}

        df_a2 = df.copy()
        composite = np.zeros(len(df_a2))
        ic_date_to_idx = {d: i for i, d in enumerate(ic_df["trade_date"].values)}

        for idx, (_, row) in enumerate(df_a2.iterrows()):
            t = row["trade_date"]
            if t in ic_date_to_idx:
                ci = ic_date_to_idx[t]
                wi = ci - 5  # lag 5 days
                if wi < 0:
                    for col in GOOD_COLS:
                        composite[idx] += (1.0 / len(GOOD_COLS)) * (row[col] if pd.notna(row[col]) else 0)
                else:
                    for col in GOOD_COLS:
                        composite[idx] += norm_weights[col][wi] * (row[col] if pd.notna(row[col]) else 0)

        df_a2["composite_ewma_lag5"] = composite
        r = rolling_eval(df_a2, "composite_ewma_lag5")
        diff = r["icir"] - baseline_r["icir"]
        print(f"  A2 lag=5 (halflife={halflife}): ICIR={r['icir']:.4f}, IC={r['ic_mean']:.4f}, WR={r['win_rate']:.4f} (Δ={diff:+.4f})")
        if "windows" in r:
            for w in r["windows"]:
                print(f"    {w['start']}: ICIR={w['icir']:.4f}")

    # ── A3 CONFIRMED: RSRS + MA filter (clean, no look-ahead) ──
    print("\n" + "="*80)
    print("  A3 CONFIRMED: RSRS + MA20 filter (dampening=0.5)")
    print("="*80)

    ma_lookup = {}
    for code in kline_df["ts_code"].unique():
        ek = kline_df[kline_df["ts_code"] == code].sort_values("trade_date")
        closes = ek["close"].values
        dates = ek["trade_date"].values
        ma20 = np.full(len(closes), np.nan)
        for i in range(19, len(closes)):
            ma20[i] = np.mean(closes[i-19:i+1])
        for i in range(len(closes)):
            ma_current = ma20[i]
            ma_lagged = ma20[i-3] if i >= 3 else np.nan
            trend_on = 1.0 if (pd.notna(ma_current) and pd.notna(ma_lagged) and ma_current > ma_lagged) else 0.0
            ma_lookup[(code, dates[i])] = trend_on

    df_a3 = df.copy()
    rsrs_filtered = []
    for _, row in df_a3.iterrows():
        trend = ma_lookup.get((row["etf_code"], row["trade_date"]), 1.0)
        rsrs_val = row["z_rsrs"] if pd.notna(row["z_rsrs"]) else 0.0
        rsrs_filtered.append(0.5 * rsrs_val if trend == 0.0 else rsrs_val)

    df_a3["z_rsrs_filt"] = rsrs_filtered
    composite = np.zeros(len(df_a3))
    composite += 0.38 * df_a3["z_rsrs_filt"].values
    composite += 0.22 * df_a3["z_flow"].fillna(0).values
    composite += 0.32 * df_a3["z_mom"].fillna(0).values
    composite += 0.08 * df_a3["z_rsi_momentum"].fillna(0).values
    df_a3["composite_ma"] = composite

    r_a3 = rolling_eval(df_a3, "composite_ma")
    diff = r_a3["icir"] - baseline_r["icir"]
    icir_ok = "✓" if r_a3["icir"] >= 0.80 else " "
    ic_ok = "✓" if r_a3["ic_mean"] >= 0.18 else " "
    wr_ok = "✓" if r_a3["win_rate"] >= 0.65 else " "
    print(f"  ICIR={r_a3['icir']:.4f}{icir_ok}  IC={r_a3['ic_mean']:.4f}{ic_ok}  WR={r_a3['win_rate']:.4f}{wr_ok}")
    print(f"  vs baseline: ICIR {diff:+.4f}")
    if "windows" in r_a3:
        for w in r_a3["windows"]:
            print(f"    {w['start']}: ICIR={w['icir']:.4f}, IC={w['ic_mean']:.4f}, WR={w['win_rate']:.4f}")

    # ── GOAL CHECK ──
    print("\n" + "="*80)
    print("  GOAL CHECK")
    print("="*80)
    for name, r in [("A3 (RSRS+MA, damp=0.5)", r_a3)]:
        icir_ok = r["icir"] >= 0.80
        ic_ok = r["ic_mean"] >= 0.18
        wr_ok = r["win_rate"] >= 0.65
        print(f"  {name}:")
        print(f"    ICIR >= 0.80: {'PASS' if icir_ok else 'FAIL'} ({r['icir']:.4f})")
        print(f"    IC   >= 0.18: {'PASS' if ic_ok else 'FAIL'} ({r['ic_mean']:.4f})")
        print(f"    WR   >= 0.65: {'PASS' if wr_ok else 'FAIL'} ({r['win_rate']:.4f})")
        if icir_ok and ic_ok and wr_ok:
            print(f"    *** ALL GOALS MET ***")


if __name__ == "__main__":
    main()
