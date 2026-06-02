"""Final attempt: test different H, presets, and cross-preset blending."""
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


def eval_weights_on_df(df, weights, composite_col="composite", window_months=3, step_months=1):
    composite = np.zeros(len(df))
    for col, w in weights.items():
        if col in df.columns:
            composite += w * df[col].fillna(0).values
    df = df.copy()
    df[composite_col] = composite
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
            results.append({
                "start": start.strftime("%Y-%m-%d"),
                "icir": m / s if s > 0 else 0,
                "ic_mean": m, "win_rate": float((a > 0).mean()), "n": len(ics),
            })
        start = start + pd.Timedelta(days=step_months * 30)
    if not results:
        return {"icir": -999, "ic_mean": 0, "win_rate": 0}
    return {
        "icir": round(np.mean([r["icir"] for r in results]), 4),
        "ic_mean": round(np.mean([r["ic_mean"] for r in results]), 4),
        "win_rate": round(np.mean([r["win_rate"] for r in results]), 4),
        "windows": results,
    }


def fetch_and_build(preset_id, h=None):
    from sqlalchemy import text
    from src.core.db_manager_postgresql import get_conn

    conn = get_conn()
    try:
        if h is None:
            h_row = conn.execute(text(
                "SELECT forward_days FROM ic_summary WHERE preset_id = :pid LIMIT 1"
            ), {"pid": preset_id}).fetchone()
            h = int(h_row[0]) if h_row else 10

        factor_rows = conn.execute(text(
            "SELECT etf_code, trade_date, factor, "
            "z_rsrs, z_flow, z_mom, z_quality, z_efficiency, z_rsi_momentum "
            "FROM factor_daily WHERE preset_id = :pid ORDER BY trade_date"
        ), {"pid": preset_id}).fetchall()

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

    # Build forward returns with custom H
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
    return pd.DataFrame(rows), h


def main():
    _init_db()
    best_w = {
        "z_rsrs": 0.45, "z_flow": 0.22, "z_mom": 0.25,
        "z_quality": 0, "z_efficiency": 0, "z_rsi_momentum": 0.08,
    }

    print("="*80)
    print("  FINAL ATTEMPT: Multi-dimensional exploration")
    print("="*80)

    # 1. Test different H values on short preset
    print("\n  --- Test 1: Different forward periods (H) on short preset ---")
    for h in [5, 10, 15, 20]:
        df, actual_h = fetch_and_build("short", h=h)
        if df.empty:
            print(f"    H={h}: No data")
            continue
        r = eval_weights_on_df(df, best_w)
        print(f"    H={h}: ICIR={r['icir']:.4f}, IC={r['ic_mean']:.4f}, WR={r['win_rate']:.4f}, n={df['trade_date'].nunique()} dates")
        if "windows" in r:
            for w in r["windows"]:
                print(f"         {w['start']}: ICIR={w['icir']:.4f}")

    # 2. Test medium/long presets with their native weights
    print("\n  --- Test 2: Medium/Long presets ---")
    for pid in ["medium", "long"]:
        df, h = fetch_and_build(pid)
        if df.empty:
            print(f"    {pid}: No data")
            continue
        preset_w = {
            "short": {"z_rsrs": 0.258, "z_flow": 0.129, "z_mom": 0.258, "z_quality": 0.184, "z_efficiency": 0.092, "z_rsi_momentum": 0.08},
            "medium": {"z_rsrs": 0.193, "z_flow": 0.193, "z_mom": 0.258, "z_quality": 0.184, "z_efficiency": 0.092, "z_rsi_momentum": 0.08},
            "long": {"z_rsrs": 0.161, "z_flow": 0.161, "z_mom": 0.322, "z_quality": 0.184, "z_efficiency": 0.092, "z_rsi_momentum": 0.08},
        }

        # With original weights
        r = eval_weights_on_df(df, preset_w[pid])
        print(f"\n    {pid} (native weights, H={h}): ICIR={r['icir']:.4f}, IC={r['ic_mean']:.4f}, WR={r['win_rate']:.4f}")
        if "windows" in r:
            for w in r["windows"]:
                print(f"      {w['start']}: ICIR={w['icir']:.4f}")

        # With optimized weights (zero quality/efficiency)
        opt_w = {"z_rsrs": 0.45, "z_flow": 0.22, "z_mom": 0.25, "z_quality": 0, "z_efficiency": 0, "z_rsi_momentum": 0.08}
        r = eval_weights_on_df(df, opt_w)
        print(f"\n    {pid} (opt weights, H={h}): ICIR={r['icir']:.4f}, IC={r['ic_mean']:.4f}, WR={r['win_rate']:.4f}")
        if "windows" in r:
            for w in r["windows"]:
                print(f"      {w['start']}: ICIR={w['icir']:.4f}")

    # 3. Cross-preset blend: average short and medium factor scores
    print("\n  --- Test 3: Cross-preset blending ---")
    df_short, h_s = fetch_and_build("short")
    df_med, h_m = fetch_and_build("medium")
    if not df_med.empty:
        # Use short forward returns but medium factor Z-scores
        short_fwd = df_short[["etf_code", "trade_date", "forward_ret"]].copy()
        med_z = df_med[["etf_code", "trade_date"] + [c for c in FACTOR_COLS]].copy()
        med_z.columns = ["etf_code", "trade_date"] + [f"med_{c}" for c in FACTOR_COLS]

        blend = short_fwd.merge(med_z, on=["etf_code", "trade_date"], how="inner")
        blend = blend.dropna(subset=["forward_ret"])

        if len(blend) > 50:
            # Blend short and medium Z-scores (50/50)
            blend_w = {}
            for col in FACTOR_COLS:
                blend[col] = (df_short.set_index(["etf_code", "trade_date"])[col].reindex(
                    blend.set_index(["etf_code", "trade_date"]).index).values * 0.5
                    + blend[f"med_{col}"].values * 0.5)

            r = eval_weights_on_df(blend, best_w)
            print(f"    Short+Medium blend (50/50): ICIR={r['icir']:.4f}, IC={r['ic_mean']:.4f}, WR={r['win_rate']:.4f}")

    # 4. Per-window best-weight analysis (theoretical upper bound)
    print("\n  --- Test 4: Theoretical upper bound (per-window optimal weights) ---")
    df_short, _ = fetch_and_build("short")
    df_short["date"] = pd.to_datetime(df_short["trade_date"], format="%Y%m%d")
    all_d = sorted(df_short["date"].unique())

    for start_idx, start in enumerate(all_d[::22]):  # monthly
        w_end = start + pd.Timedelta(days=90)
        if w_end > all_d[-1]:
            break
        mask = (df_short["date"] >= start) & (df_short["date"] < w_end)
        wdf = df_short[mask]
        if len(wdf) < 20:
            continue

        # Try a grid of weights to find per-window optimal
        best_window_icir = -999
        for rsrs in [0.3, 0.4, 0.5, 0.6]:
            for mom in [0.2, 0.3, 0.4]:
                flow = 1.0 - rsrs - mom
                if flow < 0.05 or flow > 0.5:
                    continue
                w = {"z_rsrs": rsrs, "z_flow": flow, "z_mom": mom, "z_quality": 0, "z_efficiency": 0, "z_rsi_momentum": 0}
                comp = np.zeros(len(wdf))
                for col, wt in w.items():
                    if col in wdf.columns:
                        comp += wt * wdf[col].fillna(0).values
                wdf = wdf.copy()
                wdf["_comp"] = comp
                ics = []
                for _, g in wdf.groupby("trade_date"):
                    if len(g) >= MIN_ETF_COUNT:
                        ic = _spearman_ic(g["_comp"], g["forward_ret"])
                        if not np.isnan(ic):
                            ics.append(ic)
                if len(ics) >= 3:
                    a = np.array(ics)
                    m, s = float(a.mean()), float(a.std())
                    icir = m / s if s > 0 else 0
                    if icir > best_window_icir:
                        best_window_icir = icir

        print(f"    {start.strftime('%Y-%m-%d')}: Optimal ICIR={best_window_icir:.4f}")

    print("\n" + "="*80)
    print("  FINAL SUMMARY")
    print("="*80)


if __name__ == "__main__":
    main()
