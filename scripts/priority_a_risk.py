"""Priority A: Dynamic risk management for optimized model.

Baseline: ICIR=0.789, IC=0.162, WR=0.704 (optimized preset, H=15)
Target: ICIR≥0.80, IC≥0.18, WR≥65%

Tests A1-A4 sequentially, each as a single change on top of optimized preset.
"""
import sys
import os
import logging
import warnings
import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

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


def fetch_data():
    from sqlalchemy import text
    from src.core.db_manager_postgresql import get_conn

    conn = get_conn()
    try:
        factor_rows = conn.execute(text(
            "SELECT etf_code, trade_date, factor, "
            "z_rsrs, z_flow, z_mom, z_quality, z_efficiency, z_rsi_momentum "
            "FROM factor_daily WHERE preset_id = 'optimized' ORDER BY trade_date"
        )).fetchall()

        kline_rows = conn.execute(text(
            "SELECT ts_code, trade_date, open, high, low, close, pct_chg, vol "
            "FROM sector_etf_daily ORDER BY ts_code, trade_date"
        )).fetchall()

        share_rows = conn.execute(text(
            "SELECT ts_code, trade_date, fd_share FROM etf_share ORDER BY ts_code, trade_date"
        )).fetchall()

        price_rows = conn.execute(text(
            "SELECT ts_code, trade_date, close FROM sector_etf_daily ORDER BY ts_code, trade_date"
        )).fetchall()
    finally:
        conn.close()

    factor_df = pd.DataFrame(factor_rows, columns=["etf_code", "trade_date", "factor"] +
                             ["z_rsrs", "z_flow", "z_mom", "z_quality", "z_efficiency", "z_rsi_momentum"])
    kline_df = pd.DataFrame(kline_rows, columns=["ts_code", "trade_date", "open", "high", "low", "close", "pct_chg", "vol"])
    share_df = pd.DataFrame(share_rows, columns=["ts_code", "trade_date", "fd_share"])
    price_df = pd.DataFrame(price_rows, columns=["ts_code", "trade_date", "close"])

    for df in [factor_df, kline_df, share_df, price_df]:
        df["trade_date"] = df["trade_date"].apply(
            lambda d: str(d).replace("-", "") if hasattr(d, "strftime") else str(d))

    for col in ["close", "high", "low", "pct_chg"]:
        kline_df[col] = kline_df[col].astype(float)
    kline_df["vol"] = pd.to_numeric(kline_df["vol"], errors="coerce")
    price_df["close"] = price_df["close"].astype(float)

    price_lookup = {(r["ts_code"], r["trade_date"]): r["close"] for _, r in price_df.iterrows()}
    all_dates = sorted(price_df["trade_date"].unique())
    date_idx = {d: i for i, d in enumerate(all_dates)}

    return factor_df, kline_df, share_df, price_lookup, all_dates, date_idx


def build_base_df(factor_df, price_lookup, all_dates, date_idx):
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
                    "z_quality": row["z_quality"], "z_efficiency": row["z_efficiency"],
                    "z_rsi_momentum": row["z_rsi_momentum"],
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
            if len(g) >= MIN_ETF_COUNT:
                ic = _spearman_ic(g[composite_col], g["forward_ret"])
                if not np.isnan(ic):
                    ics.append(ic)
        if len(ics) >= 3:
            a = np.array(ics)
            m, s = float(a.mean()), float(a.std())
            results.append({"start": start.strftime("%Y-%m-%d"), "icir": m / s if s > 0 else 0,
                           "ic_mean": m, "win_rate": float((a > 0).mean()), "n": len(ics)})
        start = start + pd.Timedelta(days=step_months * 30)
    if not results:
        return {"icir": -999, "ic_mean": 0, "win_rate": 0}
    return {
        "icir": round(np.mean([r["icir"] for r in results]), 4),
        "ic_mean": round(np.mean([r["ic_mean"] for r in results]), 4),
        "win_rate": round(np.mean([r["win_rate"] for r in results]), 4),
        "n_windows": len(results), "windows": results,
    }


def print_result(label, r, baseline_r):
    icir_diff = r["icir"] - baseline_r["icir"]
    ic_diff = r["ic_mean"] - baseline_r["ic_mean"]
    wr_diff = r["win_rate"] - baseline_r["win_rate"]
    icir_ok = "✓" if r["icir"] >= 0.80 else " "
    ic_ok = "✓" if r["ic_mean"] >= 0.18 else " "
    wr_ok = "✓" if r["win_rate"] >= 0.65 else " "
    print(f"\n  {label}")
    print(f"    ICIR={r['icir']:.4f}{icir_ok}  IC={r['ic_mean']:.4f}{ic_ok}  WR={r['win_rate']:.4f}{wr_ok}")
    print(f"    vs baseline: ICIR {icir_diff:+.4f}, IC {ic_diff:+.4f}, WR {wr_diff:+.4f}")
    if "windows" in r:
        for w in r["windows"]:
            print(f"      {w['start']}: ICIR={w['icir']:.4f}, IC={w['ic_mean']:.4f}, WR={w['win_rate']:.4f}")
    improved = icir_diff >= 0.05
    print(f"    单步改进有效: {'是' if improved else '否'} (ICIR提升 {icir_diff:+.4f}, 需≥0.05)")
    return r


# ═══════════════════════════════════════════════════════════
#  A1: Inverse Volatility Weighting (portfolio level)
# ═══════════════════════════════════════════════════════════
def test_a1(df, kline_df, baseline_r):
    print("\n" + "="*80)
    print("  A1: INVERSE VOLATILITY WEIGHTING")
    print("="*80)

    # Compute per-ETF rolling 20d and 60d volatility
    vol_lookup = {}
    for code in kline_df["ts_code"].unique():
        ek = kline_df[kline_df["ts_code"] == code].sort_values("trade_date")
        closes = ek["close"].values
        dates = ek["trade_date"].values
        rets = np.diff(closes) / closes[:-1]
        for i in range(20, len(closes)):
            vol20 = np.std(rets[max(0, i-20):i], ddof=0)
            vol60 = np.std(rets[max(0, i-60):i], ddof=0) if i >= 60 else vol20
            vol_lookup[(code, dates[i])] = {"vol20": vol20, "vol60": vol60}

    # Test different vol weighting approaches
    for vol_col, method in [("vol20", "1/vol20"), ("vol60", "1/vol60")]:
        # For each date, weight each ETF's composite score by 1/vol
        df_a1 = df.copy()
        df_a1["composite"] = 0.0
        for col, w in BASELINE_W.items():
            df_a1["composite"] += w * df_a1[col].fillna(0).values

        # Apply inverse vol weight per (etf_code, trade_date)
        inv_vols = []
        for _, row in df_a1.iterrows():
            v = vol_lookup.get((row["etf_code"], row["trade_date"]), {}).get(vol_col, 1.0)
            inv_vols.append(1.0 / v if v > 1e-10 else 1.0)
        df_a1["inv_vol"] = inv_vols
        df_a1["composite_vol_wt"] = df_a1["composite"] * df_a1["inv_vol"]

        r = rolling_eval(df_a1, "composite_vol_wt")
        print_result(f"A1: {method} weighting", r, baseline_r)

    # Also test: vol-adjusted factor score (divide each Z-score by ETF vol before weighting)
    for vol_col in ["vol20", "vol60"]:
        df_a1b = df.copy()
        adj_cols = {}
        for fcol in GOOD_COLS:
            adj_vals = []
            for _, row in df_a1b.iterrows():
                v = vol_lookup.get((row["etf_code"], row["trade_date"]), {}).get(vol_col, 1.0)
                inv_v = 1.0 / v if v > 1e-10 else 1.0
                adj_vals.append(row[fcol] * inv_v if pd.notna(row[fcol]) else 0.0)
            # Re-Z-score the vol-adjusted factor per date
            series = pd.Series(adj_vals)
            df_a1b[f"adj_{fcol}"] = series

        # Cross-sectional Z-score the adjusted factors per date
        for fcol in GOOD_COLS:
            for date, group in df_a1b.groupby("trade_date"):
                vals = group[f"adj_{fcol}"]
                ranks = vals.rank()
                rs = ranks.std()
                if rs > 0 and not pd.isna(rs):
                    df_a1b.loc[group.index, f"zadj_{fcol}"] = (ranks - ranks.mean()) / rs
                else:
                    df_a1b.loc[group.index, f"zadj_{fcol}"] = 0.0

        composite = np.zeros(len(df_a1b))
        for fcol in GOOD_COLS:
            w = BASELINE_W.get(fcol, 0)
            composite += w * df_a1b[f"zadj_{fcol}"].fillna(0).values
        df_a1b["composite_vol_z"] = composite

        r = rolling_eval(df_a1b, "composite_vol_z")
        print_result(f"A1: Vol-adj Z-score ({vol_col})", r, baseline_r)

    return baseline_r


# ═══════════════════════════════════════════════════════════
#  A2: Exponential Decay IC Weighting
# ═══════════════════════════════════════════════════════════
def test_a2(df, baseline_r):
    print("\n" + "="*80)
    print("  A2: EXPONENTIAL DECAY IC WEIGHTING")
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
    ic_df = pd.DataFrame(ic_data).sort_values("trade_date")

    for halflife in [5, 10, 15, 20]:
        # Compute EWMA of IC for each factor
        ic_weights = {}
        for col in GOOD_COLS:
            ic_col = f"ic_{col}"
            ewma = ic_df[ic_col].ewm(halflife=halflife).mean()
            # Weight proportional to sign(ewma) * |ewma|, floored at 0
            signal = ewma.apply(lambda x: max(x, 0))
            ic_weights[col] = signal.values

        # Normalize weights per date
        total = sum(ic_weights[col] for col in GOOD_COLS)
        total[total == 0] = 1.0
        norm_weights = {col: ic_weights[col] / total for col in GOOD_COLS}

        # Build composite with dynamic weights
        ic_df_indexed = ic_df.set_index("trade_date")
        df_a2 = df.copy()
        composite = np.zeros(len(df_a2))

        for idx, (_, row) in enumerate(df_a2.iterrows()):
            t = row["trade_date"]
            if t in ic_df_indexed.index:
                ic_idx = ic_df_indexed.index.get_loc(t)
                for col in GOOD_COLS:
                    w = norm_weights[col][ic_idx] if ic_idx < len(norm_weights[col]) else BASELINE_W.get(col, 0)
                    composite[idx] += w * (row[col] if pd.notna(row[col]) else 0)

        df_a2["composite_ewma"] = composite
        r = rolling_eval(df_a2, "composite_ewma")
        print_result(f"A2: EWMA IC weighting (halflife={halflife})", r, baseline_r)

    return baseline_r


# ═══════════════════════════════════════════════════════════
#  A3: RSRS + MA Filter
# ═══════════════════════════════════════════════════════════
def test_a3(df, kline_df, baseline_r):
    print("\n" + "="*80)
    print("  A3: RSRS + MOVING AVERAGE FILTER")
    print("="*80)

    # Compute MA20 per ETF and lagged MA20(3d)
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

    # Apply filter: zero out RSRS when trend is off
    for dampening in [0.0, 0.3, 0.5]:
        df_a3 = df.copy()
        rsrs_filtered = []
        for _, row in df_a3.iterrows():
            trend = ma_lookup.get((row["etf_code"], row["trade_date"]), 1.0)
            if trend == 1.0:
                rsrs_filtered.append(row["z_rsrs"] if pd.notna(row["z_rsrs"]) else 0.0)
            else:
                rsrs_filtered.append(dampening * (row["z_rsrs"] if pd.notna(row["z_rsrs"]) else 0.0))
        df_a3["z_rsrs_filt"] = rsrs_filtered

        composite = np.zeros(len(df_a3))
        composite += 0.38 * df_a3["z_rsrs_filt"].values
        composite += 0.22 * df_a3["z_flow"].fillna(0).values
        composite += 0.32 * df_a3["z_mom"].fillna(0).values
        composite += 0.08 * df_a3["z_rsi_momentum"].fillna(0).values
        df_a3["composite_ma"] = composite

        r = rolling_eval(df_a3, "composite_ma")
        print_result(f"A3: RSRS×MA20 filter (dampening={dampening})", r, baseline_r)

    return baseline_r


# ═══════════════════════════════════════════════════════════
#  A4: FFT Low-Pass Filter on RSRS
# ═══════════════════════════════════════════════════════════
def test_a4(df, kline_df, baseline_r):
    print("\n" + "="*80)
    print("  A4: FFT LOW-PASS FILTER ON RSRS")
    print("="*80)

    # Compute RSRS series per ETF, then apply FFT low-pass
    from src.analysis.factor_engine import _compute_rsrs_series

    fft_rsrs_lookup = {}
    for code in kline_df["ts_code"].unique():
        ek = kline_df[kline_df["ts_code"] == code].sort_values("trade_date")
        closes = ek["close"].values
        highs = ek["high"].values
        lows = ek["low"].values
        dates = ek["trade_date"].values

        rsrs_raw = _compute_rsrs_series(highs, lows, 20)

        # Apply FFT low-pass filter (remove frequencies > 1/5 days)
        for cutoff_period in [5, 10, 15]:
            rsrs_filtered = np.full(len(rsrs_raw), np.nan)
            valid_mask = ~np.isnan(rsrs_raw)
            if valid_mask.sum() < 30:
                continue

            valid_vals = rsrs_raw[valid_mask].copy()
            n = len(valid_vals)

            # FFT
            fft_vals = np.fft.fft(valid_vals)
            freqs = np.fft.fftfreq(n)

            # Low-pass: zero out frequencies with period < cutoff_period
            cutoff_freq = 1.0 / cutoff_period
            fft_filtered = fft_vals.copy()
            fft_filtered[np.abs(freqs) > cutoff_freq] = 0

            # Inverse FFT
            filtered = np.real(np.fft.ifft(fft_filtered))

            # Map back to original indices
            valid_indices = np.where(valid_mask)[0]
            for j, idx in enumerate(valid_indices):
                rsrs_filtered[idx] = filtered[j]

            # Store in lookup
            for i in range(len(dates)):
                key = (code, dates[i], cutoff_period)
                fft_rsrs_lookup[key] = rsrs_filtered[i] if not np.isnan(rsrs_filtered[i]) else 0.0

    # Test each cutoff
    for cutoff_period in [5, 10, 15]:
        df_a4 = df.copy()
        fft_rsrs = []
        for _, row in df_a4.iterrows():
            val = fft_rsrs_lookup.get((row["etf_code"], row["trade_date"], cutoff_period), 0.0)
            fft_rsrs.append(val)
        df_a4["rsrs_fft"] = fft_rsrs

        # Z-score per date
        for date, group in df_a4.groupby("trade_date"):
            vals = group["rsrs_fft"]
            ranks = vals.rank()
            rs = ranks.std()
            if rs > 0 and not pd.isna(rs):
                df_a4.loc[group.index, "z_rsrs_fft"] = (ranks - ranks.mean()) / rs
            else:
                df_a4.loc[group.index, "z_rsrs_fft"] = 0.0

        # Correlation with original RSRS
        corr = df_a4["z_rsrs"].astype(float).corr(df_a4["z_rsrs_fft"].astype(float))
        print(f"\n  FFT cutoff={cutoff_period}d: Correlation with original RSRS = {corr:.4f}")

        composite = np.zeros(len(df_a4))
        composite += 0.38 * df_a4["z_rsrs_fft"].fillna(0).values
        composite += 0.22 * df_a4["z_flow"].fillna(0).values
        composite += 0.32 * df_a4["z_mom"].fillna(0).values
        composite += 0.08 * df_a4["z_rsi_momentum"].fillna(0).values
        df_a4["composite_fft"] = composite

        r = rolling_eval(df_a4, "composite_fft")
        print_result(f"A4: FFT low-pass RSRS (cutoff={cutoff_period}d)", r, baseline_r)

    return baseline_r


def main():
    _init_db()
    logger.info("Fetching data...")
    factor_df, kline_df, share_df, price_lookup, all_dates, date_idx = fetch_data()
    df = build_base_df(factor_df, price_lookup, all_dates, date_idx)
    logger.info(f"Merged: {len(df)} rows, {df['trade_date'].nunique()} dates")

    # ── BASELINE ──
    composite = np.zeros(len(df))
    for col, w in BASELINE_W.items():
        if col in df.columns:
            composite += w * df[col].fillna(0).values
    df["composite"] = composite

    baseline_r = rolling_eval(df, "composite")
    print("\n" + "="*80)
    print(f"  BASELINE (optimized preset, H={H})")
    print("="*80)
    print(f"    ICIR={baseline_r['icir']:.4f}, IC={baseline_r['ic_mean']:.4f}, WR={baseline_r['win_rate']:.4f}")
    if "windows" in baseline_r:
        for w in baseline_r["windows"]:
            print(f"      {w['start']}: ICIR={w['icir']:.4f}, IC={w['ic_mean']:.4f}, WR={w['win_rate']:.4f}")

    # ── Run all A tests ──
    test_a1(df, kline_df, baseline_r)
    test_a2(df, baseline_r)
    test_a3(df, kline_df, baseline_r)
    test_a4(df, kline_df, baseline_r)

    print("\n" + "="*80)
    print("  SUMMARY: All approaches compared to baseline")
    print("="*80)
    print(f"  Baseline: ICIR={baseline_r['icir']:.4f}, IC={baseline_r['ic_mean']:.4f}, WR={baseline_r['win_rate']:.4f}")


if __name__ == "__main__":
    main()
