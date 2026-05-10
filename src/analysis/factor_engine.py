"""Factor computation engine for sector ETF four-quadrant analysis.

Computes Flow (share trend), Momentum, cross-sectional Z-scores,
interaction factor, and quadrant classification.
"""
import logging

import numpy as np
import pandas as pd

from src.analysis.presets import get_preset, all_preset_ids

logger = logging.getLogger(__name__)


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


def _cross_sectional_zscore(values: pd.Series) -> pd.Series:
    """Compute cross-sectional Z-scores. Returns zeros if std is 0."""
    std = values.std()
    if std == 0 or pd.isna(std):
        return pd.Series(0.0, index=values.index)
    return (values - values.mean()) / std


def _classify_quadrant(z_flow: float, z_mom: float) -> int:
    """Classify ETF into one of four quadrants.

    Q1: z_flow >= 0, z_mom >= 0 → 强势 (strong)
    Q2: z_flow >= 0, z_mom < 0 → 潜伏 (lurk)
    Q3: z_flow < 0, z_mom < 0 → 逃顶 (exit)
    Q4: z_flow < 0, z_mom >= 0 → 风险 (risk)
    """
    if z_flow >= 0 and z_mom >= 0:
        return 1
    elif z_flow >= 0 and z_mom < 0:
        return 2
    elif z_flow < 0 and z_mom < 0:
        return 3
    else:
        return 4


def compute_factors_for_date(
    kline_df: pd.DataFrame,
    share_df: pd.DataFrame,
    target_date,
    preset: dict,
) -> pd.DataFrame:
    """Compute factor values for all ETFs on a single date.

    Args:
        kline_df: DataFrame with columns [ts_code, trade_date, close, pct_chg]
        share_df: DataFrame with columns [ts_code, trade_date, fd_share]
        target_date: The date to compute factors for
        preset: Preset config dict with flow_lookback, mom_lookback

    Returns:
        DataFrame with columns [etf_code, trade_date, flow, mom, z_flow, z_mom, factor, quadrant]
    """
    flow_lb = preset["flow_lookback"]
    mom_lb = preset["mom_lookback"]
    lookback_needed = max(flow_lb, mom_lb) + 1

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

        flow = _compute_flow(etf_shares["fd_share"], flow_lb)
        mom = _compute_mom(etf_kline["close"], mom_lb)

        if pd.isna(flow) or pd.isna(mom):
            continue

        rows.append({
            "etf_code": code,
            "trade_date": target_date,
            "flow": flow,
            "mom": mom,
        })

    if len(rows) < 2:
        return pd.DataFrame(columns=["etf_code", "trade_date", "flow", "mom",
                                      "z_flow", "z_mom", "factor", "quadrant"])

    result = pd.DataFrame(rows)
    result["z_flow"] = _cross_sectional_zscore(result["flow"]).values
    result["z_mom"] = _cross_sectional_zscore(result["mom"]).values
    result["factor"] = result["z_flow"] * result["z_mom"]
    result["quadrant"] = result.apply(
        lambda r: _classify_quadrant(r["z_flow"], r["z_mom"]), axis=1
    )

    return result


def compute_all_factors(preset_id: str = None) -> int:
    """Compute factors for all trading dates for the given preset.

    Fetches sector ETF price + share data from DB, computes factors
    for each trading date, and upserts to factor_daily table.

    Returns the number of rows upserted.
    """
    from sqlalchemy import text
    from src.core.db_manager_postgresql import get_conn

    preset_ids = [preset_id] if preset_id else all_preset_ids()
    total_upserted = 0

    for pid in preset_ids:
        preset = get_preset(pid)
        flow_lb = preset["flow_lookback"]
        mom_lb = preset["mom_lookback"]
        lookback_needed = max(flow_lb, mom_lb) + 1

        conn = get_conn()
        try:
            # Fetch all sector ETF price data
            kline_rows = conn.execute(text(
                "SELECT ts_code, trade_date, close, pct_chg FROM sector_etf_daily "
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

        kline_df = pd.DataFrame(kline_rows, columns=["ts_code", "trade_date", "close", "pct_chg"])
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

        # Compute factors for new dates
        batch_rows = []
        for d in new_dates:
            day_result = compute_factors_for_date(kline_df, share_df, d, preset)
            for _, row in day_result.iterrows():
                batch_rows.append({
                    "etf_code": row["etf_code"],
                    "trade_date": row["trade_date"],
                    "preset_id": pid,
                    "flow": float(row["flow"]),
                    "mom": float(row["mom"]),
                    "z_flow": float(row["z_flow"]),
                    "z_mom": float(row["z_mom"]),
                    "factor": float(row["factor"]),
                    "quadrant": int(row["quadrant"]),
                })

        if batch_rows:
            from src.core.db_manager_postgresql import get_db_manager
            db = get_db_manager()
            df = pd.DataFrame(batch_rows)
            db.upsert_dataframe(df, "factor_daily", ["etf_code", "trade_date", "preset_id"])
            total_upserted += len(batch_rows)
            logger.info(f"Computed {len(batch_rows)} factor rows for preset={pid}")

    return total_upserted
