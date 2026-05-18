"""Factor computation engine for sector ETF four-quadrant analysis.

Computes RSRS (resistance support), Flow (share trend), Momentum (vol-adj),
cross-sectional Z-scores, three-factor composite, and quadrant classification.

Optimized: vectorized rolling-window per ETF, parallel preset computation.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd

from src.analysis.presets import get_preset, all_preset_ids

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
#  RSRS: 阻力支撑相对强度 — vectorized per-ETF series
# ════════════════════════════════════════════════════════════
def _compute_rsrs_series(highs, lows, lookback: int) -> np.ndarray:
    """Compute RSRS for every valid index using a sliding OLS window.

    Returns an array of length n where entries 0..lookback-2 are NaN.
    RSRS = beta * R²  from  high ~ low  OLS regression.
    """
    n = len(highs)
    result = np.full(n, np.nan)
    if n < lookback:
        return result

    h = np.asarray(highs, dtype=float)
    l = np.asarray(lows, dtype=float)

    for i in range(lookback - 1, n):
        hi = h[i - lookback + 1 : i + 1]
        lo = l[i - lookback + 1 : i + 1]

        std_lo = np.std(lo, ddof=0)
        std_hi = np.std(hi, ddof=0)
        if std_lo < 1e-12 or std_hi < 1e-12:
            continue

        cov = np.cov(lo, hi, ddof=0)[0, 1]
        beta = cov / (std_lo * std_lo)
        r2 = (cov / (std_lo * std_hi)) ** 2
        result[i] = beta * r2

    return result


# ════════════════════════════════════════════════════════════
#  Flow: 资金流向 (份额变化趋势) — vectorized per-ETF series
# ════════════════════════════════════════════════════════════
def _compute_flow_series(shares, lookback: int, halflife: int = 3) -> np.ndarray:
    """Compute EWMA-weighted share-flow slope for every valid index.

    Returns an array of length n where early entries are NaN.
    Flow = tanh(EWMA_slope(shares[-lookback:]) / mean(shares[-lookback:]) * 3)
    """
    n = len(shares)
    result = np.full(n, np.nan)
    if n < lookback + 1:
        return result

    vals = np.asarray(shares, dtype=float)

    for i in range(lookback, n):
        recent = vals[i - lookback + 1 : i + 1]
        mean_val = recent.mean()
        if mean_val == 0 or np.isnan(mean_val):
            continue
        y = recent / mean_val  # normalize

        x = np.arange(len(recent), dtype=float)
        weights = np.exp(-np.log(2) * (len(recent) - 1 - x) / halflife)
        weights /= weights.sum()

        x_w = x - (x * weights).sum()
        y_w = y - (y * weights).sum()
        slope = (weights * x_w * y_w).sum() / (weights * x_w * x_w).sum()
        result[i] = float(np.tanh(slope * 3))

    return result


# ════════════════════════════════════════════════════════════
#  Mom: 波动率调整动量 — vectorized per-ETF series
# ════════════════════════════════════════════════════════════
def _compute_mom_series(closes, lookback: int, vol_window: int = 60) -> np.ndarray:
    """Compute volatility-adjusted momentum for every valid index.

    Mom = return over `lookback` days / std(daily_returns, vol_window)
    Falls back to raw return if insufficient volatility data.
    """
    n = len(closes)
    result = np.full(n, np.nan)
    if n < lookback + 1:
        return result

    vals = np.asarray(closes, dtype=float)

    for i in range(lookback, n):
        mom = vals[i] / vals[i - lookback] - 1

        # Volatility adjustment
        if i >= vol_window + 1:
            daily_ret = np.diff(vals[i - vol_window : i + 1]) / vals[i - vol_window : i]
            if len(daily_ret) >= 30:
                vol = np.std(daily_ret, ddof=0)
                if vol > 0:
                    result[i] = mom / vol
                    continue

        result[i] = mom

    return result


# ════════════════════════════════════════════════════════════
#  Cross-sectional helpers (unchanged)
# ════════════════════════════════════════════════════════════
def _cross_sectional_zscore(values: pd.Series) -> pd.Series:
    """Compute cross-sectional Z-scores after Winsorizing extreme values.

    Winsorization clips the top/bottom 10% to reduce the impact of outliers
    on the small cross-section (22 ETFs). This consistently improves ICIR.
    """
    p10 = values.quantile(0.10)
    p90 = values.quantile(0.90)
    clipped = values.clip(p10, p90)
    std = clipped.std()
    if std == 0 or pd.isna(std):
        return pd.Series(0.0, index=values.index)
    return (clipped - clipped.mean()) / std


def _classify_quadrant(z_flow: float, z_mom: float) -> int:
    """Classify ETF into one of four quadrants.

    Q1: z_flow >= 0, z_mom >= 0 -> 强势 (strong)
    Q2: z_flow >= 0, z_mom < 0 -> 潜伏 (lurk)
    Q3: z_flow < 0, z_mom < 0 -> 撤离 (exit)
    Q4: z_flow < 0, z_mom >= 0 -> 风险 (risk)
    """
    if z_flow >= 0 and z_mom >= 0:
        return 1
    elif z_flow >= 0 and z_mom < 0:
        return 2
    elif z_flow < 0 and z_mom < 0:
        return 3
    else:
        return 4


# ════════════════════════════════════════════════════════════
#  Batch compute all dates — vectorized
# ════════════════════════════════════════════════════════════
def _compute_preset_factors(pid: str) -> int:
    """Compute factors for one preset using vectorized per-ETF series.

    Returns number of rows upserted.
    """
    from sqlalchemy import text
    from src.core.db_manager_postgresql import get_conn, get_db_manager

    preset = get_preset(pid)
    rsrs_lb = preset.get("rsrs_lookback", 20)
    flow_lb = preset["flow_lookback"]
    mom_lb = preset["mom_lookback"]
    weights = preset.get("factor_weights", {"rsrs": 0.4, "flow": 0.2, "mom": 0.4})
    lookback_needed = max(rsrs_lb, flow_lb, mom_lb) + 1

    conn = get_conn()
    try:
        kline_rows = conn.execute(text(
            "SELECT ts_code, trade_date, high, low, close, pct_chg FROM sector_etf_daily "
            "ORDER BY ts_code, trade_date"
        )).fetchall()

        share_rows = conn.execute(text(
            "SELECT ts_code, trade_date, fd_share FROM etf_share "
            "ORDER BY ts_code, trade_date"
        )).fetchall()
    finally:
        conn.close()

    if not kline_rows or not share_rows:
        logger.warning(f"No data for factor computation (preset={pid})")
        return 0

    kline_df = pd.DataFrame(kline_rows,
                            columns=["ts_code", "trade_date", "high", "low", "close", "pct_chg"])
    share_df = pd.DataFrame(share_rows, columns=["ts_code", "trade_date", "fd_share"])

    # Normalise dates to string
    kline_df["trade_date"] = kline_df["trade_date"].apply(
        lambda d: str(d).replace("-", "") if hasattr(d, "strftime") else str(d))
    share_df["trade_date"] = share_df["trade_date"].apply(
        lambda d: str(d).replace("-", "") if hasattr(d, "strftime") else str(d))

    all_dates = sorted(kline_df["trade_date"].unique())

    # ── Step 1: pre-compute raw factor series per ETF ──
    raw_dfs = []
    for code in kline_df["ts_code"].unique():
        ek = kline_df[kline_df["ts_code"] == code].sort_values("trade_date").copy()
        es = share_df[share_df["ts_code"] == code].sort_values("trade_date").copy()

        if len(ek) < lookback_needed:
            continue

        rsrs_arr = _compute_rsrs_series(ek["high"], ek["low"], rsrs_lb)
        mom_arr = _compute_mom_series(ek["close"], mom_lb)

        flow_arr = _compute_flow_series(es["fd_share"], flow_lb, halflife=3)

        # Align: keep only kline dates that also have valid flow
        # Build a DataFrame with all three raw factors per (etf_code, trade_date)
        df = ek[["ts_code", "trade_date"]].copy()
        df["rsrs"] = rsrs_arr
        df["mom"] = mom_arr

        # Merge flow from share data (join on trade_date)
        flow_df = pd.DataFrame({"trade_date": es["trade_date"].values,
                                "flow": flow_arr})
        df = df.merge(flow_df, on="trade_date", how="left")

        raw_dfs.append(df)

    if not raw_dfs:
        return 0

    raw_all = pd.concat(raw_dfs, ignore_index=True)

    # ── Step 2: filter out only computable dates ──
    computable_dates = []
    for d in all_dates:
        mask = kline_df[kline_df["trade_date"] <= d]
        max_len = mask.groupby("ts_code").size().max() if len(mask) > 0 else 0
        if max_len >= lookback_needed:
            computable_dates.append(d)

    if not computable_dates:
        return 0

    # ── Step 3: check what's already computed ──
    conn = get_conn()
    try:
        existing = conn.execute(text(
            "SELECT DISTINCT trade_date FROM factor_daily WHERE preset_id = :pid"
        ), {"pid": pid}).fetchall()
        existing_dates = {str(r[0]).replace("-", "") for r in existing}
    finally:
        conn.close()

    new_dates = [d for d in computable_dates if d not in existing_dates]
    if not new_dates:
        logger.info(f"All factor data already computed for preset={pid}")
        return 0

    # Check if rsrs columns exist in factor_daily
    conn = get_conn()
    try:
        has_rsrs = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='factor_daily' AND column_name='rsrs'"
        )).fetchone() is not None
    finally:
        conn.close()

    # ── Step 4: compute cross-sectional stats per date ──
    # Filter raw_all to dates we care about (speeds up lookups)
    raw_new = raw_all[raw_all["trade_date"].isin(new_dates)].copy()

    batch_rows = []
    for d in new_dates:
        day_raw = raw_new[raw_new["trade_date"] == d].copy()
        if len(day_raw) < 2:
            continue

        # Drop rows with any NaN factor
        day_raw = day_raw.dropna(subset=["rsrs", "flow", "mom"])

        if len(day_raw) < 2:
            continue

        # Cross-sectional Z-scores
        day_raw["z_rsrs"] = _cross_sectional_zscore(day_raw["rsrs"]).values
        day_raw["z_flow"] = _cross_sectional_zscore(day_raw["flow"]).values
        day_raw["z_mom"] = _cross_sectional_zscore(day_raw["mom"]).values

        # Composite factor
        w_rsrs = weights.get("rsrs", 0.4)
        w_flow = weights.get("flow", 0.2)
        w_mom = weights.get("mom", 0.4)
        day_raw["factor"] = (w_rsrs * day_raw["z_rsrs"]
                             + w_flow * day_raw["z_flow"]
                             + w_mom * day_raw["z_mom"])

        # Quadrant
        day_raw["quadrant"] = day_raw.apply(
            lambda r: _classify_quadrant(r["z_flow"], r["z_mom"]), axis=1
        )

        for _, row in day_raw.iterrows():
            item = {
                "etf_code": row["ts_code"],
                "trade_date": row["trade_date"],
                "preset_id": pid,
                "flow": float(row["flow"]),
                "mom": float(row["mom"]),
                "z_flow": float(row["z_flow"]),
                "z_mom": float(row["z_mom"]),
                "factor": float(row["factor"]),
                "quadrant": int(row["quadrant"]),
            }
            if has_rsrs:
                item["rsrs"] = float(row["rsrs"])
                item["z_rsrs"] = float(row["z_rsrs"])
            batch_rows.append(item)

    if not batch_rows:
        return 0

    db = get_db_manager()
    df_out = pd.DataFrame(batch_rows)
    db.upsert_dataframe(df_out, "factor_daily", ["etf_code", "trade_date", "preset_id"])
    logger.info(f"Computed {len(batch_rows)} factor rows for preset={pid}")
    return len(batch_rows)


def compute_all_factors(preset_id: str = None) -> int:
    """Compute factors for all trading dates.

    If preset_id is given, computes only that preset.
    Otherwise computes all presets in parallel for speed.

    Returns the total number of rows upserted.
    """
    preset_ids = [preset_id] if preset_id else all_preset_ids()

    if len(preset_ids) == 1:
        return _compute_preset_factors(preset_ids[0])

    # Parallel execution across presets
    total = 0
    with ThreadPoolExecutor(max_workers=min(len(preset_ids), 4)) as pool:
        futures = {pool.submit(_compute_preset_factors, pid): pid for pid in preset_ids}
        for fut in as_completed(futures):
            pid = futures[fut]
            try:
                n = fut.result()
                total += n
                logger.info(f"Preset {pid} done: {n} rows")
            except Exception as e:
                logger.error(f"Preset {pid} failed: {e}", exc_info=True)
    return total
