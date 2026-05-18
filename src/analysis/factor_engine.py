"""Factor computation engine for sector ETF four-quadrant analysis.

Computes RSRS (resistance support), Flow (share trend), Momentum (vol-adj),
cross-sectional Z-scores, three-factor composite, and quadrant classification.
"""
import logging

import numpy as np
import pandas as pd

from src.analysis.presets import get_preset, all_preset_ids

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
#  RSRS: 阻力支撑相对强度 (Resistance Support Relative Strength)
# ════════════════════════════════════════════════════════════
def _compute_rsrs(highs: pd.Series, lows: pd.Series, lookback: int) -> float:
    """Compute RSRS = beta * R² from OLS regression: high ~ low.

    RSRS measures the strength of the support/resistance relationship.
    Higher RSRS = stronger uptrend support structure.

    beta = slope of low → high regression (resistance relative to support)
    R²   = goodness of fit (stability of the support/resistance relationship)
    RSRS = beta × R²  (resistance-to-support ratio, adjusted for stability)

    Returns NaN if insufficient data or degenerate input.
    """
    if len(highs) < lookback or len(lows) < lookback:
        return np.nan

    h = highs.iloc[-lookback:].astype(float).values
    l = lows.iloc[-lookback:].astype(float).values

    std_l = np.std(l, ddof=0)
    std_h = np.std(h, ddof=0)
    if std_l < 1e-12 or std_h < 1e-12:
        return np.nan

    # cov(l, h) = 1/n * Σ((l_i - l̄)(h_i - h̄))
    cov = np.cov(l, h, ddof=0)[0, 1]
    beta = cov / (std_l * std_l)   # = cov(l,h)/var(l)
    r2 = (cov / (std_l * std_h)) ** 2   # = corr²

    return float(beta * r2)


# ════════════════════════════════════════════════════════════
#  Flow: 资金流向 (份额变化趋势)
# ════════════════════════════════════════════════════════════
def _compute_flow(shares: pd.Series, lookback: int) -> float:
    """Compute normalized share trend via OLS slope.

    Flow = OLS_slope(recent N days) / mean(recent N days)
    Positive = inflow, Negative = outflow.
    Returns NaN if insufficient data.
    """
    if len(shares) < lookback:
        return np.nan
    recent = shares.iloc[-lookback:].astype(float).values
    if len(recent) < 2:
        return np.nan
    mean_val = recent.mean()
    if mean_val == 0:
        return np.nan
    x = np.arange(len(recent), dtype=float)
    slope = np.polyfit(x, recent, 1)[0]
    return float(slope / mean_val)


def _compute_flow_ewma(shares: pd.Series, lookback: int, halflife: int = 3) -> float:
    """Compute share trend via EWMA-weighted slope — recent days matter more.

    Uses exponentially decaying weights (halflife=N days) and compresses
    the resulting slope to [-1, 1] via tanh. More sensitive to recent
    share changes than plain OLS.

    Returns NaN if insufficient data.
    """
    if len(shares) < lookback + 1:
        return np.nan
    recent = shares.iloc[-lookback:].astype(float).values
    if len(recent) < 2:
        return np.nan

    x = np.arange(len(recent), dtype=float)
    y = recent / recent.mean()  # normalize to remove scale
    if np.isnan(y).any():
        return np.nan

    # EWMA weights — most recent gets highest weight
    #   weight_i = exp(-ln2 * (N-1-i) / halflife)
    weights = np.exp(-np.log(2) * (len(recent) - 1 - x) / halflife)
    weights /= weights.sum()

    # Weighted least-squares slope
    x_w = x - (x * weights).sum()
    y_w = y - (y * weights).sum()
    slope = (weights * x_w * y_w).sum() / (weights * x_w * x_w).sum()

    # Compress to [-1, 1]
    return float(np.tanh(slope * 3))


# ════════════════════════════════════════════════════════════
#  Mom: 波动率调整动量
# ════════════════════════════════════════════════════════════
def _compute_mom(closes: pd.Series, lookback: int, vol_window: int = 60) -> float:
    """Compute volatility-adjusted momentum.

    Mom = close_today / close_{M days ago} - 1
    Mom_adj = Mom / std(daily_returns, 60 days)
    Falls back to unadjusted Mom if insufficient volatility data.
    """
    if len(closes) < lookback + 1:
        return np.nan
    close_today = float(closes.iloc[-1])
    close_past = float(closes.iloc[-(lookback + 1)])
    if close_past == 0:
        return np.nan
    mom = close_today / close_past - 1

    # Volatility adjustment
    if len(closes) >= vol_window + 1:
        daily_ret = closes.astype(float).pct_change().dropna().tail(vol_window)
        if len(daily_ret) >= 30:
            vol = daily_ret.std()
            if vol > 0:
                return float(mom / vol)

    return float(mom)


def _compute_mom_rank(closes: pd.Series, lookback: int) -> float:
    """Compute rank-standardized momentum.

    Steps:
    1. Raw momentum = close_today / close_{M ago} - 1
    2. Using the last 120 days as reference distribution, compute rolling
       lookback-day returns and find the percentile rank of today's value.
    3. Map percentile rank from [0, 1] to [-1, 1] (centered).

    This eliminates the volatility-adjustment noise and produces a
    stable cross-sectional rank signal.
    """
    if len(closes) < lookback + 1:
        return np.nan

    close_today = float(closes.iloc[-1])
    close_past = float(closes.iloc[-(lookback + 1)])
    if close_past == 0:
        return np.nan
    raw_mom = close_today / close_past - 1

    # Use up to 120 days as reference distribution
    ref_window = min(120, len(closes) - lookback)
    if ref_window >= 40:
        hist_closes = closes.iloc[-(lookback + ref_window):].astype(float)
        hist_rets = (hist_closes / hist_closes.shift(lookback) - 1).dropna()
        if len(hist_rets) >= 20:
            rank = (hist_rets < raw_mom).sum() / len(hist_rets)
            return float(2 * rank - 1)  # [0,1] -> [-1,1]

    # Fallback: tanh compression
    return float(np.tanh(raw_mom * 5))


# ════════════════════════════════════════════════════════════
#  Cross-sectional helpers
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
#  Compute factors for a single date
# ════════════════════════════════════════════════════════════
def compute_factors_for_date(
    kline_df: pd.DataFrame,
    share_df: pd.DataFrame,
    target_date,
    preset: dict,
) -> pd.DataFrame:
    """Compute factor values for all ETFs on a single date.

    Args:
        kline_df: DataFrame with columns [ts_code, trade_date, high, low, close, pct_chg]
        share_df: DataFrame with columns [ts_code, trade_date, fd_share]
        target_date: The date to compute factors for
        preset: Preset config dict with rsrs_lookback, flow_lookback, mom_lookback, factor_weights

    Returns:
        DataFrame with columns [etf_code, trade_date, rsrs, flow, mom,
                                 z_rsrs, z_flow, z_mom, factor, quadrant]
    """
    rsrs_lb = preset.get("rsrs_lookback", 20)
    flow_lb = preset["flow_lookback"]
    mom_lb = preset["mom_lookback"]
    weights = preset.get("factor_weights", {"rsrs": 0.4, "flow": 0.2, "mom": 0.4})
    lookback_needed = max(rsrs_lb, flow_lb, mom_lb) + 1

    etf_codes = kline_df["ts_code"].unique()
    rows = []

    for code in etf_codes:
        etf_kline = kline_df[kline_df["ts_code"] == code].sort_values("trade_date")
        etf_shares = share_df[share_df["ts_code"] == code].sort_values("trade_date")

        # Filter to data up to target_date
        etf_kline = etf_kline[etf_kline["trade_date"] <= target_date]
        etf_shares = etf_shares[etf_shares["trade_date"] <= target_date]

        if len(etf_kline) < lookback_needed or len(etf_shares) < flow_lb:
            continue

        rsrs = _compute_rsrs(etf_kline["high"], etf_kline["low"], rsrs_lb)
        flow = _compute_flow_ewma(etf_shares["fd_share"], flow_lb, halflife=3)
        mom = _compute_mom(etf_kline["close"], mom_lb)

        if pd.isna(rsrs) or pd.isna(flow) or pd.isna(mom):
            continue

        rows.append({
            "etf_code": code,
            "trade_date": target_date,
            "rsrs": rsrs,
            "flow": flow,
            "mom": mom,
        })

    if len(rows) < 2:
        return pd.DataFrame(columns=["etf_code", "trade_date", "rsrs", "flow", "mom",
                                      "z_rsrs", "z_flow", "z_mom", "factor", "quadrant"])

    result = pd.DataFrame(rows)
    result["z_rsrs"] = _cross_sectional_zscore(result["rsrs"]).values
    result["z_flow"] = _cross_sectional_zscore(result["flow"]).values
    result["z_mom"] = _cross_sectional_zscore(result["mom"]).values

    # Three-factor combination
    w_rsrs = weights.get("rsrs", 0.4)
    w_flow = weights.get("flow", 0.2)
    w_mom = weights.get("mom", 0.4)
    result["factor"] = w_rsrs * result["z_rsrs"] + w_flow * result["z_flow"] + w_mom * result["z_mom"]

    # Quadrant classification: uses z_flow + z_mom (Flow + Mom dimensions)
    # RSRS is incorporated into the factor score but quadrant uses flow+mom
    # for compatibility with existing analysis
    result["quadrant"] = result.apply(
        lambda r: _classify_quadrant(r["z_flow"], r["z_mom"]), axis=1
    )

    return result


# ════════════════════════════════════════════════════════════
#  Batch compute all dates
# ════════════════════════════════════════════════════════════
def compute_all_factors(preset_id: str = None) -> int:
    """Compute factors for all trading dates for the given preset.

    Fetches sector ETF price (incl. high, low for RSRS) + share data from DB,
    computes factors for each trading date, and upserts to factor_daily table.

    Returns the number of rows upserted.
    """
    from sqlalchemy import text
    from src.core.db_manager_postgresql import get_conn

    preset_ids = [preset_id] if preset_id else all_preset_ids()
    total_upserted = 0

    for pid in preset_ids:
        preset = get_preset(pid)
        rsrs_lb = preset.get("rsrs_lookback", 20)
        flow_lb = preset["flow_lookback"]
        mom_lb = preset["mom_lookback"]
        lookback_needed = max(rsrs_lb, flow_lb, mom_lb) + 1

        conn = get_conn()
        try:
            # Fetch all sector ETF price data (need high/low for RSRS)
            kline_rows = conn.execute(text(
                "SELECT ts_code, trade_date, high, low, close, pct_chg FROM sector_etf_daily "
                "ORDER BY ts_code, trade_date"
            )).fetchall()

            # Fetch all ETF share data
            share_rows = conn.execute(text(
                "SELECT ts_code, trade_date, fd_share FROM etf_share "
                "ORDER BY ts_code, trade_date"
            )).fetchall()
        finally:
            conn.close()

        if not kline_rows or not share_rows:
            logger.warning(f"No data for factor computation (preset={pid})")
            continue

        kline_df = pd.DataFrame(kline_rows,
                                columns=["ts_code", "trade_date", "high", "low", "close", "pct_chg"])
        share_df = pd.DataFrame(share_rows, columns=["ts_code", "trade_date", "fd_share"])

        # Get unique trading dates, skip dates that don't have enough history
        all_dates = sorted(kline_df["trade_date"].unique())
        computable_dates = []
        for d in all_dates:
            history = kline_df[kline_df["trade_date"] <= d]
            max_len = history.groupby("ts_code").size().max() if len(history) > 0 else 0
            if max_len >= lookback_needed:
                computable_dates.append(d)

        if not computable_dates:
            continue

        # Check what's already computed
        conn = get_conn()
        try:
            existing = conn.execute(text(
                "SELECT DISTINCT trade_date FROM factor_daily WHERE preset_id = :pid"
            ), {"pid": pid}).fetchall()
            existing_dates = {r[0] for r in existing}
        finally:
            conn.close()

        new_dates = [d for d in computable_dates if d not in existing_dates]
        if not new_dates:
            logger.info(f"All factor data already computed for preset={pid}")
            continue

        # Check if rsrs columns exist in factor_daily
        conn = get_conn()
        try:
            has_rsrs = conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='factor_daily' AND column_name='rsrs'"
            )).fetchone() is not None
        finally:
            conn.close()

        # Compute factors for new dates
        batch_rows = []
        for d in new_dates:
            day_result = compute_factors_for_date(kline_df, share_df, d, preset)
            for _, row in day_result.iterrows():
                item = {
                    "etf_code": row["etf_code"],
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

        if batch_rows:
            from src.core.db_manager_postgresql import get_db_manager
            db = get_db_manager()
            df = pd.DataFrame(batch_rows)
            db.upsert_dataframe(df, "factor_daily", ["etf_code", "trade_date", "preset_id"])
            total_upserted += len(batch_rows)
            logger.info(f"Computed {len(batch_rows)} factor rows for preset={pid}")

    return total_upserted
