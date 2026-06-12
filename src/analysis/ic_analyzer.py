"""IC (Information Coefficient) analyzer for factor validation.

Computes Spearman Rank IC, ICIR, IC win rate, and rolling ICIR
from factor values and forward returns.

IMPORTANT: Uses T-1 day's factor to predict T to T+H returns (no look-ahead).
Factor on date T requires T's close price and share data (available after close),
so the earliest actionable signal is at T+1 open.

Optimized: parallel preset computation.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

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


def _fetch_ic_price_data():
    """Fetch and normalise price data for IC computation (shared across presets).

    Returns a (price_df, all_dates, date_idx) tuple, or (None, [], {}) on failure.
    """
    from src.core.db_manager_postgresql import get_conn

    conn = get_conn()
    try:
        price_rows = conn.execute(text(
            "SELECT ts_code, trade_date, close FROM sector_etf_daily "
            "ORDER BY ts_code, trade_date"
        )).fetchall()
    finally:
        conn.close()

    if not price_rows:
        return None, [], {}

    price_df = pd.DataFrame(price_rows, columns=["ts_code", "trade_date", "close"])
    price_df["trade_date"] = price_df["trade_date"].apply(
        lambda d: str(d).replace("-", "") if hasattr(d, "strftime") else str(d))
    price_df["close"] = price_df["close"].astype(float)

    all_dates = sorted(price_df["trade_date"].unique())
    date_idx = {d: i for i, d in enumerate(all_dates)}

    return price_df, all_dates, date_idx


def _compute_preset_ic(pid: str, *,
                       price_df: pd.DataFrame = None,
                       all_dates: list = None,
                       date_idx: dict = None,
                       log_func: callable = None) -> int:
    """Compute IC analysis for a single preset.

    When called from ``compute_all_ic`` (multi‑preset path), the caller
    passes the pre‑fetched price data so parallel threads share the same
    ``sector_etf_daily`` scan.

    When called directly (single‑preset path), fetches its own data.

    Returns total rows upserted.
    """
    from src.core.db_manager_postgresql import get_conn, get_db_manager

    preset = get_preset(pid)
    forward_periods = preset["forward_periods"]

    # ── Fetch price data if caller didn't provide it ──
    if price_df is None:
        price_df, all_dates, date_idx = _fetch_ic_price_data()
        if price_df is None:
            logger.warning(f"No price data for IC computation (preset={pid})")
            return 0

    conn = get_conn()
    try:
        factor_rows = conn.execute(text(
            "SELECT etf_code, trade_date, factor, z_flow, z_mom, quadrant "
            "FROM factor_daily WHERE preset_id = :pid ORDER BY trade_date"
        ), {"pid": pid}).fetchall()
    finally:
        conn.close()

    if not factor_rows:
        logger.warning(f"No factor data for IC computation (preset={pid})")
        return 0

    factor_df = pd.DataFrame(factor_rows,
                             columns=["etf_code", "trade_date", "factor", "z_flow", "z_mom", "quadrant"])

    # Normalize factor dates to strings
    factor_df["trade_date"] = factor_df["trade_date"].apply(
        lambda d: str(d).replace("-", "") if hasattr(d, "strftime") else str(d))

    # Build price lookup: (code, date) → close
    price_df["close"] = price_df["close"].astype(float)
    price_lookup = {}
    for _, row in price_df.iterrows():
        price_lookup[(row["ts_code"], row["trade_date"])] = row["close"]

    # Build date index if caller didn't provide it (only recompute when necessary)
    if all_dates is None or date_idx is None:
        all_dates = sorted(price_df["trade_date"].unique())
        date_idx = {d: i for i, d in enumerate(all_dates)}
    factor_dates = sorted(factor_df["trade_date"].unique())

    total_upserted = 0
    total_dates = len(factor_dates)
    log_interval = max(1, total_dates // 10)  # 每 10% 日志一次

    for h in forward_periods:
        ic_rows = []
        quadrant_rows = []
        msg = f"IC preset={pid}, H={h}: starting with {total_dates} trade dates"
        logger.info(msg)
        if log_func:
            log_func(msg)

        for i, t in enumerate(factor_dates):
            if i > 0 and i % log_interval == 0:
                msg = f"IC preset={pid}, H={h}: {i}/{total_dates} dates processed ({len(ic_rows)} IC values so far)"
                logger.info(msg)
                if log_func:
                    log_func(msg)
            if t not in date_idx:
                continue
            idx = date_idx[t]
            if idx + 1 + h >= len(all_dates):
                continue

            entry_date = all_dates[idx + 1]
            exit_date = all_dates[idx + 1 + h]

            day_factors = factor_df[factor_df["trade_date"] == t]

            fwd_rets = {}
            for _, row in day_factors.iterrows():
                code = row["etf_code"]
                close_entry = price_lookup.get((code, entry_date))
                close_exit = price_lookup.get((code, exit_date))
                if close_entry and close_exit and close_entry > 0:
                    fwd_rets[code] = (close_exit / close_entry - 1, row["factor"], row["quadrant"])

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
                pd.DataFrame([summary]).to_sql(
                    "ic_summary", conn, if_exists="append", index=False,
                    method="multi", chunksize=10000,
                )
                conn.commit()
            finally:
                conn.close()
            total_upserted += 1

        h_msg = f"IC preset={pid}, H={h}: done ({len(ic_rows)} IC values)"
        logger.info(h_msg)
        if log_func:
            log_func(h_msg)

    return total_upserted


def compute_all_ic(preset_id: str = None, log_func: callable = None) -> int:
    """Compute IC analysis for all presets, running them in parallel.

    If *preset_id* is given, computes only that preset (standalone DB
    fetch).  Otherwise fetches the underlying price data *once* and runs
    all presets in parallel — each thread receives the shared price
    DataFrames so the full‑table scan is not repeated.

    Returns total rows upserted.
    """
    preset_ids = [preset_id] if preset_id else all_preset_ids()

    if len(preset_ids) == 1:
        return _compute_preset_ic(preset_ids[0], log_func=log_func)

    # ── Fetch price data once for all presets ──
    price_df, all_dates, date_idx = _fetch_ic_price_data()
    if price_df is None:
        logger.warning("No price data for IC computation")
        return 0

    # ── Parallel execution with shared price data ──
    total = 0
    with ThreadPoolExecutor(max_workers=min(len(preset_ids), 4)) as pool:
        futures = {
            pool.submit(_compute_preset_ic, pid,
                        price_df=price_df, all_dates=all_dates, date_idx=date_idx,
                        log_func=log_func): pid
            for pid in preset_ids
        }
        for fut in as_completed(futures):
            pid = futures[fut]
            try:
                n = fut.result()
                total += n
                logger.info(f"IC preset {pid} done: {n} rows")
            except Exception as e:
                logger.error(f"IC preset {pid} failed: {e}", exc_info=True)
    return total
