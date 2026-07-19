"""Factor computation engine for sector ETF four-quadrant analysis.

Computes RSRS (resistance support), Flow (share trend), Momentum (vol-adj),
Financial Quality (F_Quality), Intraday Efficiency, RSI Momentum,
cross-sectional Z-scores, six-factor composite, and quadrant classification.

V4: Integrated Financial Quality Factor (F_Quality) as the 4th factor.
V5: Added Intraday Efficiency Factor (IntEff) as the 5th factor.
V6: Added RSI Momentum Factor as the 6th factor.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd

from src.analysis.presets import get_preset, all_preset_ids
from src.analysis.intraday_efficiency import compute_efficiency_for_etf
from src.analysis.rsi_factor import compute_rsi_momentum_for_etf
from config.config import COMMODITY_ETF_CODES
# BARRA neutralization available but disabled for small cross-section.
# See src/analysis/barra_neutralization.py and comments in _compute_preset_factors.

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
#  RSRS: 阻力支撑相对强度 — vectorized per-ETF series
# ════════════════════════════════════════════════════════════
def _compute_rsrs_series(highs, lows, lookback: int, zscore_window: int = 300) -> np.ndarray:
    """Compute RSRS for every valid index using a sliding OLS window.

    Returns an array of length n where entries 0..lookback-2 are NaN.
    RSRS = beta * R²  from  high ~ low  OLS regression.

    After raw RSRS computation, applies rolling Z-score standardization
    (time-series dimension, zscore_window=300 by default) so that each
    RSRS value is interpreted relative to its own recent history.
    Only outputs valid Z-scores when at least 20 non-NaN observations
    are available within the rolling window.
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

    # ── Rolling Z-score standardization (time-series dimension) ──
    # Use expanding window for early dates (before full zscore_window is available)
    # so that early RSRS values are comparable to later ones.
    min_valid = 20
    start_idx = lookback + zscore_window - 1
    if start_idx >= n:
        start_idx = lookback + min_valid - 1  # fallback with minimum valid window

    for i in range(lookback + min_valid - 1, n):
        if i < start_idx:
            # Expanding window: use all available data from lookback onwards
            window = result[lookback - 1 : i + 1]
        else:
            window = result[i - zscore_window + 1 : i + 1]
        valid = window[~np.isnan(window)]
        if len(valid) >= min_valid:
            mean = np.mean(valid)
            std = np.std(valid, ddof=0)
            if std > 1e-12:
                result[i] = (result[i] - mean) / std
            else:
                result[i] = 0.0

    # Entries before minimum valid history → NaN
    result[:lookback + min_valid - 1] = np.nan

    return result


# ════════════════════════════════════════════════════════════
#  Flow: 资金流向 (份额变化趋势) — vectorized per-ETF series
# ════════════════════════════════════════════════════════════
def _compute_flow_series(shares, lookback: int, halflife: int = 3) -> np.ndarray:
    """Compute EWMA-weighted share-flow slope for every valid index.

    Returns an array of length n where early entries are NaN.
    Flow = EWMA_slope(shares[-lookback:]) / mean(shares[-lookback:])
    (raw slope, no tanh — cross-sectional Z-score is applied later.)
    """
    n = len(shares)
    result = np.full(n, np.nan)
    if n < lookback + 1:
        return result

    vals = np.asarray(shares, dtype=float)

    for i in range(lookback, n):
        recent = vals[i - lookback + 1 : i + 1]
        mean_val = recent.mean()
        if abs(mean_val) < 1e-10 or np.isnan(mean_val):
            continue
        y = recent / mean_val  # normalize

        x = np.arange(len(recent), dtype=float)
        weights = np.exp(-np.log(2) * (len(recent) - 1 - x) / halflife)
        weights /= weights.sum()

        x_w = x - (x * weights).sum()
        y_w = y - (y * weights).sum()
        denom = (weights * x_w * x_w).sum()
        if denom == 0:
            continue
        slope = (weights * x_w * y_w).sum() / denom
        result[i] = float(slope)

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
            vol = np.std(daily_ret, ddof=0)
            if vol > 0:
                result[i] = mom / vol
                continue

        result[i] = mom

    return result


# ════════════════════════════════════════════════════════════
#  Cross-sectional helpers
# ════════════════════════════════════════════════════════════
def _cross_sectional_zscore(values: pd.Series) -> pd.Series:
    """Rank-based normalization robust to small cross-section (N < 30).

    Converts values to standardized ranks (mean ≈ 0, std ≈ 1).
    More robust than Winsorize+Z-score when only 17–22 ETFs are available:
    avoids the distortion of clipping 1–2 samples in each tail.
    """
    ranks = values.rank()
    rank_std = ranks.std()
    if rank_std == 0 or pd.isna(rank_std):
        return pd.Series(0.0, index=values.index)
    return (ranks - ranks.mean()) / rank_std


def _share_val_for_date(code: str, date: str, share_lookup: dict) -> float:
    """Look up fd_share for an ETF on a given date."""
    return share_lookup.get((code, date), np.nan)


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
#  Shared data helper
# ════════════════════════════════════════════════════════════
def _fetch_factor_base_data():
    """Fetch kline + share data from DB and normalise dates.

    Also detects whether ``factor_daily`` has the ``rsrs`` / ``z_rsrs`` columns.

    Returns (kline_df, share_df, has_rsrs).
    Returns (None, None, False) if no data available.
    """
    from sqlalchemy import text
    from src.core.db_manager_postgresql import get_conn

    conn = get_conn()
    try:
        kline_rows = conn.execute(text(
            "SELECT ts_code, trade_date, open, high, low, close, pct_chg FROM sector_etf_daily "
            "WHERE trade_date >= (SELECT MAX(trade_date) - INTERVAL '365 days' FROM sector_etf_daily) "
            "ORDER BY ts_code, trade_date"
        )).fetchall()
        share_rows = conn.execute(text(
            "SELECT ts_code, trade_date, fd_share FROM etf_share "
            "WHERE trade_date >= (SELECT MAX(trade_date) - INTERVAL '365 days' FROM etf_share) "
            "ORDER BY ts_code, trade_date"
        )).fetchall()
        has_rsrs = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='factor_daily' AND column_name='rsrs'"
        )).fetchone() is not None
    finally:
        conn.close()

    if not kline_rows or not share_rows:
        return None, None, False

    kline_df = pd.DataFrame(kline_rows,
                            columns=["ts_code", "trade_date", "open", "high", "low", "close", "pct_chg"])
    share_df = pd.DataFrame(share_rows, columns=["ts_code", "trade_date", "fd_share"])

    # Normalise dates to string (once, shared by all presets)
    for col in ["trade_date"]:
        kline_df[col] = kline_df[col].apply(
            lambda d: str(d).replace("-", "") if hasattr(d, "strftime") else str(d))
        share_df[col] = share_df[col].apply(
            lambda d: str(d).replace("-", "") if hasattr(d, "strftime") else str(d))

    return kline_df, share_df, has_rsrs


def _get_latest_financial_factors() -> dict:
    """Quality factor removed (2026-07-01 simplification).

    Returns {} so the downstream weight-0 / dead-factor-redistribution path
    no-ops: factor assembly still writes f_quality/z_quality = 0, then the
    dead-factor path drops them from the composite. Kept as a stub rather than
    excising every Quality reference in the assembly loop — lower risk, same
    end state (Quality already had weight 0 in the optimized preset).
    """
    return {}


def _get_adjusted_weights(base_weights: dict) -> dict:
    """Adjust quality factor weight based on market regime.

    NOTE: Quality factor removed (2026-07-01 simplification). The optimized preset
    has quality=0.0 and _get_latest_financial_factors() returns {}. This function
    is effectively dead code — kept for reference should quality data be re-enabled.
    It still runs compute_market_timing() (a db query) but produces no effect.

    Returns adjusted weights dict with keys rsrs/flow/mom/quality summing to 1.0.
    """
    base_q = base_weights.get("quality", 0.0)
    if base_q <= 0:
        return dict(base_weights)

    try:
        from src.analysis.market_timing import compute_market_timing
        timing = compute_market_timing()
        score = timing.get("score", 0.0)
    except Exception:
        return dict(base_weights)

    # Determine target quality weight
    if score < -0.3:
        # Overheated/caution — strong momentum trend → reduce quality reliance
        target_q = min(0.10, base_q)
    elif score > 0.3:
        # Oversold/recovery — weak momentum → increase quality reliance
        target_q = 0.40
    else:
        target_q = base_q

    if abs(target_q - base_q) < 0.01:
        return dict(base_weights)

    # Distribute the delta proportionally among other factors
    other_keys = ["rsrs", "flow", "mom", "efficiency", "rsi_momentum"]
    other_total = sum(base_weights.get(k, 0.0) for k in other_keys)
    if other_total <= 0:
        return dict(base_weights)

    adjusted = dict(base_weights)
    remaining = 1.0 - target_q
    for k in other_keys:
        adjusted[k] = round(base_weights.get(k, 0.0) / other_total * remaining, 6)
    adjusted["quality"] = target_q

    logger.info(f"Weight adjustment: quality {base_q}->{target_q} "
                f"(market_score={score:.3f}, regime={timing.get('regime_cn', '?')})")
    return adjusted


# ════════════════════════════════════════════════════════════
#  Batch compute all dates — vectorized
# ════════════════════════════════════════════════════════════
def _compute_preset_factors(pid: str, *,
                            kline_df: pd.DataFrame = None,
                            share_df: pd.DataFrame = None,
                            has_rsrs: bool = False) -> int:
    """Compute factors for one preset using vectorized per-ETF series.

    (Quality factor removed 2026-07-01; the model is now RSRS/Flow/Mom +
    Efficiency + RSI_Mom. _get_latest_financial_factors() returns {} and the
    dead-factor path drops the weight-0 quality column.)

    When called from ``compute_all_factors`` (multi‑preset path), the
    caller passes pre‑fetched *kline_df*, *share_df* and *has_rsrs* so
    the four parallel threads don't repeat the same full‑table scans.

    When called directly (single‑preset path), the function fetches its
    own data via ``_fetch_factor_base_data``.

    Returns number of rows upserted.
    """
    from sqlalchemy import text
    from src.core.db_manager_postgresql import get_conn, get_db_manager

    # Task 4.1: Exception isolation guard
    try:
        preset = get_preset(pid)
    except Exception as e:
        logger.error(f"Failed to load preset {pid}: {e}", exc_info=True)
        return 0
    rsrs_lb = preset.get("rsrs_lookback", 20)
    flow_lb = preset["flow_lookback"]
    mom_lb = preset["mom_lookback"]
    weights = preset.get("factor_weights", {"rsrs": 0.25, "flow": 0.25, "mom": 0.25, "quality": 0.25})
    # S1: Dynamic quality weight based on market regime (base weights for historical dates)
    weights = dict(weights) if isinstance(weights, dict) else dict(preset.get("factor_weights", {"rsrs": 0.25, "flow": 0.25, "mom": 0.25, "quality": 0.25}))
    lookback_needed = max(rsrs_lb, flow_lb, mom_lb) + 1

    # ── Fetch data if caller didn't provide it (standalone path) ──
    if kline_df is None:
        kline_df, share_df, has_rsrs = _fetch_factor_base_data()
        if kline_df is None:
            logger.warning(f"No data for factor computation (preset={pid})")
            return 0

    all_dates = sorted(kline_df["trade_date"].unique())
    date_idx_map = {d: i for i, d in enumerate(all_dates)}

    # Pre-group kline by ts_code for O(1) lookups instead of repeated filtering
    kline_groups = {code: group.sort_values("trade_date") for code, group in kline_df.groupby("ts_code")}

    # V7: Pre-compute MA20 trend filter per (ETF_code, date_index)
    rsrs_ma_damp = preset.get("rsrs_ma_dampening", 0.0)
    _ma_trend_lookup = {}
    if rsrs_ma_damp > 0:
        for code, ek in kline_groups.items():
            closes = ek["close"].values.astype(float)
            ek_dates = ek["trade_date"].values
            ma20 = np.full(len(closes), np.nan)
            for mi in range(19, len(closes)):
                ma20[mi] = np.mean(closes[mi - 19:mi + 1])
            for mi in range(len(ek_dates)):
                if ek_dates[mi] in date_idx_map:
                    ti = date_idx_map[ek_dates[mi]]
                    ma_cur = ma20[mi]
                    ma_lag = ma20[mi - 3] if mi >= 3 else np.nan
                    trend = 1.0 if (pd.notna(ma_cur) and pd.notna(ma_lag) and ma_cur > ma_lag) else 0.0
                    _ma_trend_lookup[(code, ti)] = trend

    # ── Step 1: pre-compute raw factor series per ETF ──
    raw_dfs = []
    for code, ek in kline_groups.items():
        ek = ek.copy()
        es = share_df[share_df["ts_code"] == code].sort_values("trade_date").copy()

        if len(ek) < lookback_needed:
            continue

        rsrs_arr = _compute_rsrs_series(ek["high"], ek["low"], rsrs_lb)
        mom_arr = _compute_mom_series(ek["close"], mom_lb)

        # Reversal series (short-lookback, negated) for weak-market mode
        rev_lb = preset.get("reversal_lookback", 5)
        rev_arr = -_compute_mom_series(ek["close"], rev_lb)

        flow_arr = _compute_flow_series(es["fd_share"], flow_lb, halflife=3)

        # V5: Intraday Efficiency Factor (from OHLC proxy)
        eff_sma = preset.get("eff_sma_window", 0)
        eff_arr = compute_efficiency_for_etf(ek, sma_window=eff_sma)

        # V6: RSI Momentum Factor (RSI(5)-RSI(20), size-neutralized later)
        rsi_arr = compute_rsi_momentum_for_etf(ek["close"], es["fd_share"])

        # Build a DataFrame with all factor series per (etf_code, trade_date)
        df = ek[["ts_code", "trade_date"]].copy()
        df["rsrs"] = rsrs_arr
        df["mom"] = mom_arr
        df["mom_rev"] = rev_arr
        df["efficiency"] = eff_arr.values if hasattr(eff_arr, 'values') else eff_arr
        df["rsi_momentum"] = rsi_arr.values if hasattr(rsi_arr, 'values') else rsi_arr

        # Merge flow from share data (join on trade_date)
        flow_df = pd.DataFrame({"trade_date": es["trade_date"].values,
                                "flow": flow_arr})
        df = df.merge(flow_df, on="trade_date", how="left")
        df["flow"] = df["flow"].ffill()

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

    # ── Step 3: check what's already computed per preset ──
    # Handle partial dates: a date is "fully computed" only when ALL ETF codes
    # have factor data.  Dates with partial data (e.g. only 4 of 18 ETFs) need
    # full recomputation so that newly fetched tickers are not silently skipped.
    conn = get_conn()
    try:
        existing_counts = conn.execute(text(
            "SELECT trade_date, COUNT(DISTINCT etf_code) AS cnt "
            "FROM factor_daily WHERE preset_id = :pid "
            "GROUP BY trade_date"
        ), {"pid": pid}).fetchall()
    finally:
        conn.close()

    total_codes = len(kline_df["ts_code"].unique())
    fully_computed_dates = set()
    for r in existing_counts:
        d = str(r[0]).replace("-", "")
        cnt = int(r[1])
        if cnt >= total_codes:
            fully_computed_dates.add(d)
        else:
            logger.info(
                f"Partial date {r[0]} for preset={pid}: "
                f"{cnt}/{total_codes} ETFs computed, will recompute"
            )

    new_dates = [d for d in computable_dates if d not in fully_computed_dates]
    if not new_dates:
        logger.info(f"All factor data already computed for preset={pid}")
        return 0

    # ── Step 4: load latest financial quality factors ──
    quality_factors = _get_latest_financial_factors()
    has_quality = bool(quality_factors)

    # ── Step 4b: build share lookup for RSI size neutralization ──
    share_lookup = {}
    for _, row in share_df.iterrows():
        share_lookup[(row["ts_code"], row["trade_date"])] = float(row["fd_share"]) if pd.notna(row["fd_share"]) else np.nan

    # ── Step 5: compute cross-sectional stats per date ──
    # Filter raw_all to dates we care about (speeds up lookups)
    raw_new = raw_all[raw_all["trade_date"].isin(new_dates)].copy()

    # Fetch market regime once for weight adjustment + reversal mode detection.
    # INV-014 fix: market-timing adjustments are only applied to the latest date
    # to avoid look-ahead bias on historical factor computation.
    try:
        from src.analysis.market_timing import compute_market_timing
        _timing = compute_market_timing()
        _market_score = _timing.get("score", 0.0)
    except Exception:
        _market_score = 0.0
    _latest_date = new_dates[-1] if new_dates else None
    _latest_weights = _get_adjusted_weights(weights)

    batch_rows = []
    for d in new_dates:
        day_raw = raw_new[raw_new["trade_date"] == d].copy()
        if len(day_raw) < 2:
            continue

        # Softer NaN handling: fill missing factors with 0 instead of dropping entire rows.
        # Weight redistribution (below) will detect columns that are all-zero and
        # redistribute their weight to active factors.
        for _col in ["rsrs", "flow", "mom", "efficiency", "rsi_momentum"]:
            if _col in day_raw.columns:
                day_raw[_col] = day_raw[_col].fillna(0.0)
        # Only drop rows where ALL core factors are missing (no signal at all)
        day_raw = day_raw.dropna(subset=["rsrs", "flow", "mom", "efficiency", "rsi_momentum"], how="all")

        if len(day_raw) < 2:
            continue

        # ── Weak-market reversal mode (latest date only) ──
        # In bearish/overheated regime, replace trend momentum with short-term reversal.
        # This flips the mom sign: stocks that fell recently get positive reversal scores,
        # making the quadrant model capture mean-reversion opportunities.
        # INV-014 fix: only apply to the latest date to avoid look-ahead bias.
        _is_latest = (d == _latest_date)
        if _is_latest and _market_score < -0.3 and "mom_rev" in day_raw.columns:
            day_raw["mom"] = day_raw["mom_rev"]

        # Cross-sectional Z-scores for RSRS/Flow/Mom/Efficiency
        day_raw["z_rsrs"] = _cross_sectional_zscore(day_raw["rsrs"]).values
        day_raw["z_flow"] = _cross_sectional_zscore(day_raw["flow"]).values
        day_raw["z_mom"] = _cross_sectional_zscore(day_raw["mom"]).values
        day_raw["z_efficiency"] = _cross_sectional_zscore(day_raw["efficiency"]).values

        # V7: RSRS MA trend filter — dampen z_rsrs when MA20 trend is bearish
        # (rsrs_ma_damp already read from preset at L365)
        if rsrs_ma_damp > 0:
            for idx_r, row_r in day_raw.iterrows():
                code = row_r["ts_code"]
                t = d
                if t in date_idx_map:
                    ti = date_idx_map[t]
                    # Check MA20 trend from pre-computed lookup
                    trend = _ma_trend_lookup.get((code, ti), 1.0)
                    if trend < 0.5:
                        day_raw.loc[idx_r, "z_rsrs"] *= rsrs_ma_damp

        # ── V6: RSI Momentum with size neutralization ──
        # rank(RSI_diff) - 0.5 * rank(fd_share), then Z-score
        rsi_rank = day_raw["rsi_momentum"].rank()
        # Build size rank from fd_share via share_lookup
        size_vals = day_raw["ts_code"].map(
            lambda c: _share_val_for_date(c, d, share_lookup)
        )
        size_rank = size_vals.rank() if size_vals.notna().sum() >= 2 else pd.Series(0.0, index=day_raw.index)
        rsi_combined = rsi_rank - 0.5 * size_rank
        day_raw["z_rsi_momentum"] = _cross_sectional_zscore(rsi_combined).values

        # ── V4: Merge Financial Quality Factor ──
        if has_quality:
            # Map F_Quality values to each ETF in the cross-section
            day_raw["f_quality"] = day_raw["ts_code"].map(
                lambda code: quality_factors.get(code, np.nan)
            )
            # Z-score only valid (non-NaN) values to avoid distribution bias
            quality_series = day_raw["f_quality"].copy()
            valid_mask = quality_series.notna()
            day_raw["z_quality"] = 0.0
            if valid_mask.sum() >= 2:
                z_scored = _cross_sectional_zscore(quality_series[valid_mask])
                day_raw.loc[valid_mask, "z_quality"] = z_scored.values
            # Fill raw f_quality NaN with 0 AFTER Z-scoring
            day_raw["f_quality"] = day_raw["f_quality"].fillna(0.0)
        else:
            day_raw["f_quality"] = 0.0
            day_raw["z_quality"] = 0.0

        # ── BARRA neutralization (disabled for small cross-section N≈22) ──
        # With only 17-22 ETFs, 3 risk factors (VOL/BETA/SIZE) consume too many
        # degrees of freedom, causing overfitting. Testing showed IC dropped from
        # 0.104→0.044 and ICIR from 0.41→0.21 after BARRA.
        # Re-enable when cross-section grows to 50+ ETFs.
        # See src/analysis/barra_neutralization.py for implementation.
        pass

        # ── Composite factor with weight redistribution ──
        # Detect which factors are actually contributing (have non-zero Z-scores
        # in the current cross-section). Dead factors get their weight
        # redistributed proportionally to the remaining active factors.
        # INV-014 fix: use market-timing-adjusted weights only for the latest date.
        _w = _latest_weights if _is_latest else weights
        w_rsrs = _w.get("rsrs", 0.20)
        w_flow = _w.get("flow", 0.20)
        w_mom = _w.get("mom", 0.20)
        w_quality = _w.get("quality", 0.20)
        w_efficiency = _w.get("efficiency", 0.20)
        w_rsi = _w.get("rsi_momentum", 0.08)

        quality_active = (
            has_quality
            and (day_raw["z_quality"].abs() > 1e-10).any()
        )
        eff_active = (day_raw["z_efficiency"].abs() > 1e-10).any()
        rsi_active = (day_raw["z_rsi_momentum"].abs() > 1e-10).any()

        dead_factors = []
        if not quality_active:
            dead_factors.append("quality")
        if not eff_active:
            dead_factors.append("efficiency")
        if not rsi_active:
            dead_factors.append("rsi_momentum")

        if dead_factors:
            dead_weight = 0.0
            if "quality" in dead_factors:
                dead_weight += w_quality
                w_quality = 0.0
            if "efficiency" in dead_factors:
                dead_weight += w_efficiency
                w_efficiency = 0.0
            if "rsi_momentum" in dead_factors:
                dead_weight += w_rsi
                w_rsi = 0.0
            # Proportionally redistribute to ALL active factors (not just RSRS/Flow/Mom)
            # Bug fix: previously only redistributed to RSRS/Flow/Mom, ignoring
            # active Efficiency and RSI_Momentum factors.
            active_weight = w_rsrs + w_flow + w_mom + w_efficiency + w_rsi
            if active_weight > 0:
                scale = (active_weight + dead_weight) / active_weight
                w_rsrs *= scale
                w_flow *= scale
                w_mom *= scale
                w_efficiency *= scale
                w_rsi *= scale
            logger.info(
                f"  Weight redistribution: {','.join(dead_factors)} inactive, "
                f"redistributed {dead_weight:.2f} weight to all active factors"
            )

        day_raw["factor"] = (w_rsrs * day_raw["z_rsrs"]
                             + w_flow * day_raw["z_flow"]
                             + w_mom * day_raw["z_mom"]
                             + w_quality * day_raw["z_quality"]
                             + w_efficiency * day_raw["z_efficiency"]
                             + w_rsi * day_raw["z_rsi_momentum"])

        # Commodity ETF: redistribute quality weight to technical factors.
        # 商品ETF：将 quality 权重等比例分摊到其余技术面因子
        commodity_mask = day_raw["ts_code"].isin(COMMODITY_ETF_CODES)
        if commodity_mask.any():
            technical_weight = 1.0 - w_quality
            if technical_weight > 0:
                day_raw.loc[commodity_mask, "factor"] = (
                    w_rsrs * day_raw.loc[commodity_mask, "z_rsrs"]
                    + w_flow * day_raw.loc[commodity_mask, "z_flow"]
                    + w_mom * day_raw.loc[commodity_mask, "z_mom"]
                    + w_efficiency * day_raw.loc[commodity_mask, "z_efficiency"]
                    + w_rsi * day_raw.loc[commodity_mask, "z_rsi_momentum"]
                ) / technical_weight

        # Quadrant (unchanged: still based on flow + mom only)
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
                "f_quality": float(row["f_quality"]),
                "z_quality": float(row["z_quality"]),
                "intraday_eff": float(row["efficiency"]),
                "z_efficiency": float(row["z_efficiency"]),
                "rsi_momentum": float(row["rsi_momentum"]),
                "z_rsi_momentum": float(row["z_rsi_momentum"]),
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

    If *preset_id* is given, computes only that preset (standalone DB
    fetch).  Otherwise fetches the underlying data *once* and runs all
    presets in parallel — each thread receives the shared DataFrames so
    the full‑table scans are not repeated.

    Returns the total number of rows upserted.
    """
    preset_ids = [preset_id] if preset_id else all_preset_ids()

    if len(preset_ids) == 1:
        return _compute_preset_factors(preset_ids[0])

    # ── Fetch data once for all presets ──
    kline_df, share_df, has_rsrs = _fetch_factor_base_data()
    if kline_df is None or share_df is None:
        logger.warning("No data for factor computation")
        return 0

    # ── Parallel execution with shared data ──
    total = 0
    with ThreadPoolExecutor(max_workers=min(len(preset_ids), 4)) as pool:
        futures = {
            pool.submit(_compute_preset_factors, pid,
                        kline_df=kline_df, share_df=share_df,
                        has_rsrs=has_rsrs): pid
            for pid in preset_ids
        }
        for fut in as_completed(futures):
            pid = futures[fut]
            try:
                n = fut.result()
                total += n
                logger.info(f"Preset {pid} done: {n} rows")
            except Exception as e:
                logger.error(f"Preset {pid} failed: {e}", exc_info=True)
    return total
