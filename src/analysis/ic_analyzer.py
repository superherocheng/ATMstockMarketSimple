"""IC (Information Coefficient) analyzer for factor validation.

Computes Spearman Rank IC, ICIR, IC win rate, IC decay,
and rolling ICIR from factor values and forward returns.
"""
import logging

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
from sqlalchemy import text

from src.analysis.presets import get_preset, all_preset_ids

logger = logging.getLogger(__name__)

MIN_ETF_COUNT = 8  # Minimum ETFs for meaningful IC


def _compute_ic_for_date(factors: pd.Series, forward_returns: pd.Series) -> float:
    """Compute Spearman Rank IC for a single cross-section.

    Returns NaN if insufficient data (< MIN_ETF_COUNT valid pairs).
    """
    valid = factors.notna() & forward_returns.notna()
    f = factors[valid]
    r = forward_returns[valid]

    if len(f) < MIN_ETF_COUNT:
        return np.nan

    corr, _ = scipy_stats.spearmanr(f, r)
    return float(corr) if not np.isnan(corr) else np.nan


def _compute_ic_summary(ic_series: pd.Series) -> dict:
    """Compute aggregate IC statistics from an IC time series."""
    valid = ic_series.dropna()
    n = len(valid)
    if n == 0:
        return {"ic_mean": None, "ic_std": None, "icir": None, "ic_win_rate": None, "sample_count": 0}

    ic_mean = float(valid.mean())
    ic_std = float(valid.std())
    icir = ic_mean / ic_std if ic_std > 0 else None
    ic_win_rate = float((valid > 0).sum() / n)

    return {
        "ic_mean": round(ic_mean, 6),
        "ic_std": round(ic_std, 6),
        "icir": round(icir, 6) if icir is not None else None,
        "ic_win_rate": round(ic_win_rate, 4),
        "sample_count": n,
    }


def compute_all_ic(preset_id: str = None) -> int:
    """Compute IC analysis for all presets and store to DB.

    For each preset:
    1. Compute daily IC for each forward period H
    2. Compute aggregate IC summary
    3. Compute quadrant performance (avg forward return per quadrant)
    4. Upsert results to ic_daily, ic_summary, quadrant_perf tables

    Returns total rows upserted.
    """
    from src.core.db_manager_postgresql import get_conn, get_db_manager

    preset_ids = [preset_id] if preset_id else all_preset_ids()
    total_upserted = 0

    for pid in preset_ids:
        preset = get_preset(pid)
        forward_periods = preset["forward_periods"]

        conn = get_conn()
        try:
            # Get factor data for this preset
            factor_rows = conn.execute(text(
                "SELECT etf_code, trade_date, factor, z_flow, z_mom, quadrant "
                "FROM factor_daily WHERE preset_id = :pid ORDER BY trade_date"
            ), {"pid": pid}).fetchall()

            # Get sector ETF price data for forward returns
            price_rows = conn.execute(text(
                "SELECT ts_code, trade_date, close FROM sector_etf_daily "
                "ORDER BY ts_code, trade_date"
            )).fetchall()
        finally:
            conn.close()

        if not factor_rows or not price_rows:
            logger.warning(f"No data for IC computation (preset={pid})")
            continue

        factor_df = pd.DataFrame(factor_rows,
                                 columns=["etf_code", "trade_date", "factor", "z_flow", "z_mom", "quadrant"])
        price_df = pd.DataFrame(price_rows, columns=["ts_code", "trade_date", "close"])

        # Normalize dates to strings (factor_daily returns datetime.date,
        # sector_etf_daily returns int YYYYMMDD from Tushare)
        factor_df["trade_date"] = factor_df["trade_date"].apply(
            lambda d: str(d).replace("-", "") if hasattr(d, "strftime") else str(d))
        price_df["trade_date"] = price_df["trade_date"].apply(
            lambda d: str(d).replace("-", "") if hasattr(d, "strftime") else str(d))

        # Build price lookup: (code, date) → close
        price_df["close"] = price_df["close"].astype(float)
        price_lookup = {}
        for _, row in price_df.iterrows():
            price_lookup[(row["ts_code"], row["trade_date"])] = row["close"]

        # Get sorted unique dates for forward return computation
        all_dates = sorted(price_df["trade_date"].unique())
        date_idx = {d: i for i, d in enumerate(all_dates)}

        # Get trading dates present in factor data
        factor_dates = sorted(factor_df["trade_date"].unique())

        for h in forward_periods:
            ic_rows = []
            quadrant_rows = []

            for t in factor_dates:
                day_factors = factor_df[factor_df["trade_date"] == t]

                fwd_rets = {}
                for _, row in day_factors.iterrows():
                    code = row["etf_code"]
                    close_t = price_lookup.get((code, t))
                    if t not in date_idx:
                        continue
                    idx = date_idx[t]
                    if idx + h >= len(all_dates):
                        continue
                    fwd_date = all_dates[idx + h]
                    close_fwd = price_lookup.get((code, fwd_date))
                    if close_t and close_fwd and close_t > 0:
                        fwd_rets[code] = (close_fwd / close_t - 1, row["factor"], row["quadrant"])

                if len(fwd_rets) < MIN_ETF_COUNT:
                    continue

                codes = list(fwd_rets.keys())
                ret_vals = pd.Series([fwd_rets[c][0] for c in codes])
                fac_vals = pd.Series([fwd_rets[c][1] for c in codes])

                ic = _compute_ic_for_date(fac_vals, ret_vals)

                if not np.isnan(ic):
                    ic_rows.append({
                        "trade_date": t,
                        "preset_id": pid,
                        "forward_days": h,
                        "ic_value": float(ic),
                        "forward_ret_mean": float(ret_vals.mean()),
                    })

                for q in [1, 2, 3, 4]:
                    q_codes = [c for c in codes if fwd_rets[c][2] == q]
                    if q_codes:
                        q_rets = [fwd_rets[c][0] for c in q_codes]
                        quadrant_rows.append({
                            "trade_date": t,
                            "preset_id": pid,
                            "forward_days": h,
                            "quadrant": q,
                            "avg_forward_ret": float(np.mean(q_rets)),
                            "etf_count": len(q_codes),
                        })

            # Upsert ic_daily
            if ic_rows:
                db = get_db_manager()
                db.upsert_dataframe(pd.DataFrame(ic_rows), "ic_daily",
                                    ["trade_date", "preset_id", "forward_days"])
                total_upserted += len(ic_rows)

            # Upsert quadrant_perf
            if quadrant_rows:
                db = get_db_manager()
                db.upsert_dataframe(pd.DataFrame(quadrant_rows), "quadrant_perf",
                                    ["trade_date", "preset_id", "forward_days", "quadrant"])
                total_upserted += len(quadrant_rows)

            # Compute and upsert ic_summary
            if ic_rows:
                ic_series = pd.Series([r["ic_value"] for r in ic_rows])
                summary = _compute_ic_summary(ic_series)
                summary["preset_id"] = pid
                summary["forward_days"] = h

                conn = get_conn()
                try:
                    conn.execute(text(
                        "DELETE FROM ic_summary WHERE preset_id = :pid AND forward_days = :h"
                    ), {"pid": pid, "h": h})
                    conn.commit()
                finally:
                    conn.close()

                db = get_db_manager()
                db.insert_dataframe(pd.DataFrame([summary]), "ic_summary", if_exists="append")
                total_upserted += 1

            logger.info(f"IC analysis done for preset={pid}, H={h}: {len(ic_rows)} IC values")

    return total_upserted
