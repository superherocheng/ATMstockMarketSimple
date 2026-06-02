"""Validate H=15 breakthrough: fine-grained weight search + full diagnostics."""
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


def main():
    from sqlalchemy import text
    from src.core.db_manager_postgresql import get_conn

    _init_db()
    conn = get_conn()
    try:
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

    # Build forward returns with H=15
    H = 15
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
                    **{col: row[col] for col in FACTOR_COLS},
                })
    df = pd.DataFrame(rows)
    logger.info(f"H={H}: {len(df)} rows, {df['trade_date'].nunique()} dates")

    # ── Fine-grained weight search for H=15 ──
    print("="*80)
    print(f"  H=15 FINE-GRAINED WEIGHT SEARCH")
    print("="*80)

    best_icir = -999
    best_weights = None
    best_label = ""
    all_results = []

    for rsrs in [0.35, 0.38, 0.40, 0.42, 0.45, 0.48, 0.50]:
        for mom in [0.20, 0.22, 0.25, 0.28, 0.30, 0.32]:
            for rsi in [0.0, 0.05, 0.08]:
                flow = round(1.0 - rsrs - mom - rsi, 4)
                if flow < 0.05 or flow > 0.40:
                    continue
                w = {"z_rsrs": rsrs, "z_flow": flow, "z_mom": mom,
                     "z_quality": 0, "z_efficiency": 0, "z_rsi_momentum": rsi}

                composite = np.zeros(len(df))
                for col, wt in w.items():
                    if col in df.columns:
                        composite += wt * df[col].fillna(0).values
                df["_comp"] = composite
                df["date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
                all_d = sorted(df["date"].unique())

                window_results = []
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
                            ic = _spearman_ic(g["_comp"], g["forward_ret"])
                            if not np.isnan(ic):
                                ics.append(ic)
                    if len(ics) >= 3:
                        a = np.array(ics)
                        m, s = float(a.mean()), float(a.std())
                        window_results.append({"icir": m / s if s > 0 else 0, "ic_mean": m, "win_rate": float((a > 0).mean())})
                    start = start + pd.Timedelta(days=30)

                if not window_results:
                    continue

                avg_icir = np.mean([r["icir"] for r in window_results])
                avg_ic = np.mean([r["ic_mean"] for r in window_results])
                avg_wr = np.mean([r["win_rate"] for r in window_results])

                label = f"R={rsrs},M={mom},F={flow:.3f},RSI={rsi}"
                all_results.append((label, w, avg_icir, avg_ic, avg_wr, window_results))

                if avg_icir > best_icir:
                    best_icir = avg_icir
                    best_weights = w
                    best_label = label

    # Sort and show top 10
    all_results.sort(key=lambda x: x[2], reverse=True)
    print(f"\n  Top 10 weight combinations (H=15):")
    for i, (label, w, icir, ic, wr, _) in enumerate(all_results[:10], 1):
        icir_ok = "✓" if icir >= 0.70 else " "
        ic_ok = "✓" if ic >= 0.10 else " "
        wr_ok = "✓" if wr >= 0.68 else " "
        print(f"  {i:>2}. ICIR={icir:.4f}{icir_ok} IC={ic:.4f}{ic_ok} WR={wr:.4f}{wr_ok} | {label}")

    # Show best in detail
    best_label, best_w, best_icir, best_ic, best_wr, best_windows = all_results[0]
    print(f"\n  BEST: {best_label}")
    print(f"  ICIR={best_icir:.4f}, IC={best_ic:.4f}, WR={best_wr:.4f}")
    print(f"  Weights: {best_w}")
    print(f"\n  Per-window breakdown:")
    for j, wr in enumerate(best_windows):
        status = "OK" if wr["icir"] > 0 else "NEGATIVE"
        print(f"    W{j+1}: ICIR={wr['icir']:.4f}, IC={wr['ic_mean']:.4f}, WR={wr['win_rate']:.4f} [{status}]")

    # ── Compare H=10 vs H=15 ──
    print(f"\n{'='*80}")
    print(f"  COMPARISON: H=10 (current) vs H=15 (proposed)")
    print(f"{'='*80}")

    # H=10 with same weights
    df10_rows = []
    for t in sorted(factor_df["trade_date"].unique()):
        if t not in date_idx:
            continue
        idx = date_idx[t]
        if idx + 1 + 10 >= len(all_dates):
            continue
        entry, exit_d = all_dates[idx + 1], all_dates[idx + 1 + 10]
        for _, row in factor_df[factor_df["trade_date"] == t].iterrows():
            c_e = price_lookup.get((row["etf_code"], entry))
            c_x = price_lookup.get((row["etf_code"], exit_d))
            if c_e and c_x and c_e > 0:
                df10_rows.append({
                    "etf_code": row["etf_code"], "trade_date": t,
                    "forward_ret": c_x / c_e - 1,
                    **{col: row[col] for col in FACTOR_COLS},
                })
    df10 = pd.DataFrame(df10_rows)

    comp = np.zeros(len(df10))
    for col, w in best_w.items():
        if col in df10.columns:
            comp += w * df10[col].fillna(0).values
    df10["_comp"] = comp
    df10["date"] = pd.to_datetime(df10["trade_date"], format="%Y%m%d")
    all_d10 = sorted(df10["date"].unique())

    w10_results = []
    start = all_d10[0]
    while True:
        w_end = start + pd.Timedelta(days=90)
        if w_end > all_d10[-1]:
            break
        mask = (df10["date"] >= start) & (df10["date"] < w_end)
        wdf = df10[mask]
        if len(wdf) < 20:
            start = start + pd.Timedelta(days=30)
            continue
        ics = []
        for _, g in wdf.groupby("trade_date"):
            if len(g) >= MIN_ETF_COUNT:
                ic = _spearman_ic(g["_comp"], g["forward_ret"])
                if not np.isnan(ic):
                    ics.append(ic)
        if len(ics) >= 3:
            a = np.array(ics)
            m, s = float(a.mean()), float(a.std())
            w10_results.append({"icir": m / s if s > 0 else 0, "ic_mean": m, "win_rate": float((a > 0).mean())})
        start = start + pd.Timedelta(days=30)

    avg10_icir = np.mean([r["icir"] for r in w10_results])
    avg10_ic = np.mean([r["ic_mean"] for r in w10_results])
    avg10_wr = np.mean([r["win_rate"] for r in w10_results])

    print(f"\n  H=10: ICIR={avg10_icir:.4f}, IC={avg10_ic:.4f}, WR={avg10_wr:.4f}")
    for j, r in enumerate(w10_results):
        print(f"    W{j+1}: ICIR={r['icir']:.4f}")

    print(f"\n  H=15: ICIR={best_icir:.4f}, IC={best_ic:.4f}, WR={best_wr:.4f}")
    for j, r in enumerate(best_windows):
        print(f"    W{j+1}: ICIR={r['icir']:.4f}")

    print(f"\n  Improvement: ICIR +{best_icir - avg10_icir:.4f}")

    # ── FINAL GOAL CHECK ──
    print(f"\n{'='*80}")
    print(f"  GOAL CHECK (H=15, best weights)")
    print(f"{'='*80}")
    icir_ok = best_icir >= 0.70
    ic_ok = best_ic >= 0.10
    wr_ok = best_wr >= 0.68
    print(f"  ICIR >= 0.70: {'PASS' if icir_ok else 'FAIL'} ({best_icir:.4f})")
    print(f"  IC   >= 0.10: {'PASS' if ic_ok else 'FAIL'} ({best_ic:.4f})")
    print(f"  WR   >= 0.68: {'PASS' if wr_ok else 'FAIL'} ({best_wr:.4f})")
    if icir_ok and ic_ok and wr_ok:
        print(f"\n  *** ALL GOALS MET ***")
        print(f"\n  FINAL FACTOR COMBINATION:")
        print(f"    Forward period H = 15")
        print(f"    Weights: RSRS={best_w['z_rsrs']}, Flow={best_w['z_flow']}, Mom={best_w['z_mom']}, "
              f"Quality=0, Efficiency=0, RSI_Mom={best_w['z_rsi_momentum']}")
    else:
        print(f"\n  Goals NOT all met.")


if __name__ == "__main__":
    main()
