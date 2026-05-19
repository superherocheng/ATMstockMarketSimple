"""
Intraday Price Efficiency Factor (IntEff)
===========================================

Measures the "directionality" of daily price movement:
- High efficiency: smooth, single-direction trend (high signal, low noise)
- Low efficiency: choppy, high noise (wide range, small net move)

Formula (OHLC proxy — uses daily Open/High/Low/Close):
  Efficiency_t = |Close_t - Close_{t-1}| / ((High_t - Low_t) + |Close_t - Open_t| + epsilon)

  Where denominator approximates total intraday path length.

Then:
  1. 5-day rolling average (Eff_5 = SMA 5)
  2. EWMA short(5) - EWMA long(20) → IntEff
  3. Cross-sectional Z-score

Note: True minute-level data would give exact path length.
This OHLC proxy is a widely-used approximation that captures the same
economic intuition — rewarding smooth trends, penalizing noisy reversals.

Upgrade path: Replace the OHLC proxy with minute-data summation
when Tushare fund_mins / AKShare becomes available (swap one function).
"""
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════
#  Constants
# ════════════════════════════════════════════════════════════
EPSILON = 1e-10        # prevent division by zero
SMA_WINDOW = 5         # rolling average window
EWMA_SHORT_HALFLIFE = 5   # short-term EWMA halflife (days)
EWMA_LONG_HALFLIFE = 20   # long-term EWMA halflife (days)
MIN_HISTORY = max(SMA_WINDOW, EWMA_LONG_HALFLIFE) + 5


# ════════════════════════════════════════════════════════════
#  Step 1: Daily Efficiency (OHLC proxy)
# ════════════════════════════════════════════════════════════
def _daily_efficiency_ohlc(opens, highs, lows, closes) -> np.ndarray:
    """Compute daily price efficiency from OHLC arrays.

    For each day t:
      numerator   = |Close_t - Close_{t-1}|
      denominator = (High_t - Low_t) + |Close_t - Open_t|
      Efficiency  = numerator / (denominator + EPSILON)

    First day returns NaN (no prior close).
    """
    n = len(closes)
    result = np.full(n, np.nan)
    if n < 2:
        return result

    o = np.asarray(opens, dtype=float)
    h = np.asarray(highs, dtype=float)
    l = np.asarray(lows, dtype=float)
    c = np.asarray(closes, dtype=float)

    numerator = np.abs(c[1:] - c[:-1])
    denominator = (h[1:] - l[1:]) + np.abs(c[1:] - o[1:])
    denominator = np.maximum(denominator, EPSILON)

    eff = numerator / denominator
    # Clip extreme values from thin trading days
    eff = np.clip(eff, 0.0, 1.0)

    result[1:] = eff
    return result


# ════════════════════════════════════════════════════════════
#  Step 2: 5-day Simple Moving Average
# ════════════════════════════════════════════════════════════
def _smooth_5(efficiency: np.ndarray) -> np.ndarray:
    """Apply 5-day rolling average to efficiency series.

    Early entries (< 5 valid) are NaN.
    """
    n = len(efficiency)
    result = np.full(n, np.nan)
    if n < SMA_WINDOW:
        return result

    eff_series = pd.Series(efficiency)
    smoothed = eff_series.rolling(window=SMA_WINDOW, min_periods=SMA_WINDOW).mean()
    return smoothed.values


# ════════════════════════════════════════════════════════════
#  Step 3: EWMA Difference (short - long)
# ════════════════════════════════════════════════════════════
def _ewma_halflife(series: np.ndarray, halflife: float) -> np.ndarray:
    """Compute EWMA with given halflife (days).

    Uses pandas ewm with alpha = 1 - exp(-ln2 / halflife).
    """
    if len(series) == 0:
        return series
    alpha = 1.0 - np.exp(-np.log(2) / max(halflife, 1))
    s = pd.Series(series)
    ewma = s.ewm(alpha=alpha, adjust=False).mean()
    return ewma.values


def _compute_intraday_efficiency_series(opens, highs, lows, closes) -> np.ndarray:
    """Compute Intraday Efficiency factor series for one ETF.

    Pipeline:
      1. Daily efficiency (OHLC proxy)
      2. 5-day SMA smoothing
      3. EWMA_short(5) - EWMA_long(20) → IntEff

    Returns:
        Array of length n (same as input).
        Early entries are NaN where insufficient history.
    """
    n = len(closes)
    if n < MIN_HISTORY:
        return np.full(n, np.nan)

    # Step 1: daily efficiency
    eff = _daily_efficiency_ohlc(opens, highs, lows, closes)

    # Step 2: 5-day SMA
    eff_sma5 = _smooth_5(eff)

    # Step 3: EWMA difference
    ewma_short = _ewma_halflife(eff_sma5, halflife=EWMA_SHORT_HALFLIFE)
    ewma_long = _ewma_halflife(eff_sma5, halflife=EWMA_LONG_HALFLIFE)

    int_eff = ewma_short - ewma_long

    return int_eff


# ════════════════════════════════════════════════════════════
#  Batch interface (called by factor_engine)
# ════════════════════════════════════════════════════════════
def compute_efficiency_for_etf(etf_df: pd.DataFrame) -> pd.Series:
    """Compute Intraday Efficiency for one ETF's kline DataFrame.

    Args:
        etf_df: DataFrame with columns ['open','high','low','close']
                sorted by trade_date ascending.

    Returns:
        pd.Series of IntEff values, index matching etf_df.index.
    """
    opens = etf_df["open"].values
    highs = etf_df["high"].values
    lows = etf_df["low"].values
    closes = etf_df["close"].values

    int_eff = _compute_intraday_efficiency_series(opens, highs, lows, closes)
    return pd.Series(int_eff, index=etf_df.index)


if __name__ == "__main__":
    # Quick test
    import numpy as np
    n = 100
    np.random.seed(42)
    # Simulate a trending ETF (high efficiency)
    trend_prices = 10.0 + np.cumsum(np.random.randn(n) * 0.1)
    o = trend_prices + np.random.randn(n) * 0.05
    h = np.maximum(trend_prices, o) + np.abs(np.random.randn(n)) * 0.1
    l = np.minimum(trend_prices, o) - np.abs(np.random.randn(n)) * 0.1

    result = _compute_intraday_efficiency_series(o, h, l, trend_prices)
    print(f"Trending series: last 10 IntEff values: {np.round(result[-10:], 4)}")
    print(f"  Mean (valid): {np.nanmean(result):.4f}")

    # Simulate a choppy ETF (low efficiency)
    choppy_prices = 10.0 + np.random.randn(n) * 0.5  # high noise
    o2 = choppy_prices + np.random.randn(n) * 0.5
    h2 = np.maximum(choppy_prices, o2) + np.abs(np.random.randn(n)) * 0.5
    l2 = np.minimum(choppy_prices, o2) - np.abs(np.random.randn(n)) * 0.5

    result2 = _compute_intraday_efficiency_series(o2, h2, l2, choppy_prices)
    print(f"Choppy series:  last 10 IntEff values: {np.round(result2[-10:], 4)}")
    print(f"  Mean (valid): {np.nanmean(result2):.4f}")
