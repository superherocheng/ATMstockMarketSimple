"""Multi-index market timing indicator with cross-sectional dispersion.

Computes a composite timing score by fusing signals from three indexes:
1. CSI 500  (510500.SH) — weight 0.5
2. CSI 300  (510300.SH) — weight 0.3
3. KCB 50   (588000.SH) — weight 0.2

Each index signal combines:
- RSI(14): oversold/overbought regime
- 20-day momentum: trend exhaustion signal
- Share flow (10d): smart money flow signal

A cross-sectional dispersion metric (std of all sector ETF daily returns)
is used to discount the composite score when the market is divergent.
"""
import logging
from datetime import datetime

import numpy as np
import pandas as pd
from sqlalchemy import text

logger = logging.getLogger(__name__)

# ── Constants ──
INDEX_CODES = {
    "csi500": "510500.SH",
    "csi300": "510300.SH",
    "kc50": "588000.SH",
}
INDEX_WEIGHTS = {"csi500": 0.5, "csi300": 0.3, "kc50": 0.2}
RSI_PERIOD = 14
MOM_PERIOD = 20
SHARE_FLOW_PERIOD = 10
MIN_HISTORY = 30


def _get_conn():
    from src.core.db_manager_postgresql import get_conn
    return get_conn()


def _compute_rsi(closes: np.ndarray, period: int = RSI_PERIOD) -> np.ndarray:
    """Compute RSI for a price series."""
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.convolve(gains, np.ones(period) / period, mode="valid")
    avg_loss = np.convolve(losses, np.ones(period) / period, mode="valid")
    rs = avg_gain / np.where(avg_loss == 0, 1e-10, avg_loss)
    rsi = 100 - 100 / (1 + rs)
    rsi_full = np.full(len(closes), 50.0)
    rsi_full[period:] = rsi
    return rsi_full


def _compute_index_signals(ts_code: str, conn) -> dict:
    """Compute RSI, momentum, and share flow signals for a single index ETF.

    Returns dict with keys: rsi, momentum_20d, share_flow_10d,
    rsi_score, mom_score, share_score, latest_date.
    Returns empty dict if insufficient data.
    """
    price_rows = conn.execute(text("""
        SELECT trade_date, close
        FROM index_etf_daily
        WHERE ts_code = :code
        ORDER BY trade_date
    """), {"code": ts_code}).fetchall()

    share_rows = conn.execute(text("""
        SELECT trade_date, fd_share
        FROM etf_share
        WHERE ts_code = :code
        ORDER BY trade_date
    """), {"code": ts_code}).fetchall()

    if not price_rows or len(price_rows) < MIN_HISTORY:
        logger.warning(f"Insufficient price data for {ts_code}")
        return {}

    dates = [str(r[0]) for r in price_rows]
    closes = np.array([float(r[1]) for r in price_rows])
    latest_date = dates[-1]

    # Staleness warning: alert if data is more than 5 trading days behind
    try:
        from datetime import timedelta
        from src.core.trading_calendar import get_latest_trading_date
        latest_td = get_latest_trading_date()
        if latest_td:
            # Compare as YYYYMMDD strings
            latest_date_dt = datetime.strptime(latest_date.replace("-", ""), "%Y%m%d").date() if "-" in latest_date else datetime.strptime(latest_date, "%Y%m%d").date()
            latest_td_dt = datetime.strptime(latest_td, "%Y%m%d").date()
            if (latest_td_dt - latest_date_dt).days > 5:
                logger.warning(
                    "Market timing data stale: latest=%s, expected>=%s",
                    latest_date, latest_td
                )
    except Exception:
        pass  # staleness check is non-critical, don't block computation

    share_map = {}
    for r in share_rows:
        d = str(r[0])
        v = float(r[1]) if r[1] else None
        if v and v > 0:
            share_map[d] = v

    # 1. RSI(14)
    rsi_vals = _compute_rsi(closes, RSI_PERIOD)
    current_rsi = float(rsi_vals[-1])

    # 2. 20-day momentum
    if len(closes) > MOM_PERIOD:
        current_mom = float(closes[-1] / closes[-(MOM_PERIOD + 1)] - 1)
    else:
        current_mom = 0.0

    # 3. Share flow (10-day pct change, using share data's own dates)
    current_share_flow = 0.0
    if latest_date in share_map:
        share_dates = sorted(share_map.keys())
        # Find the index of latest_date in share data
        try:
            latest_idx = share_dates.index(latest_date)
        except ValueError:
            latest_idx = -1
        idx_10 = max(0, latest_idx - SHARE_FLOW_PERIOD)
        if idx_10 < latest_idx:
            date_10 = share_dates[idx_10]
            if date_10 in share_map:
                s_now = share_map[latest_date]
                s_then = share_map[date_10]
                current_share_flow = float((s_now - s_then) / s_then * 100)

    # ── Score components (each contributes [-0.5, +0.5]) ──
    rsi_score = 0.0
    if current_rsi < 40:
        rsi_score = min(0.5, (40 - current_rsi) / 40 * 0.5)
    elif current_rsi > 75:
        rsi_score = -min(0.2, (current_rsi - 75) / 25 * 0.2)

    mom_score = 0.0
    if current_mom > 0.08:
        mom_score = -min(0.3, (current_mom - 0.08) / 0.10 * 0.3)
    elif current_mom < -0.08:
        mom_score = min(0.3, (abs(current_mom) - 0.08) / 0.10 * 0.3)

    share_score = 0.0
    if current_share_flow > 3:
        share_score = min(0.5, (current_share_flow - 3) / 10 * 0.5)
    elif current_share_flow < -3:
        share_score = -min(0.3, (abs(current_share_flow) - 3) / 10 * 0.3)

    return {
        "rsi": round(current_rsi, 1),
        "rsi_score": round(rsi_score, 4),
        "momentum_20d": round(current_mom, 4),
        "mom_score": round(mom_score, 4),
        "share_flow_10d": round(current_share_flow, 2),
        "share_score": round(share_score, 4),
        "latest_date": latest_date,
    }


def _compute_cross_sectional_dispersion(conn, latest_date: str) -> float:
    """Compute cross-sectional std ratio of all sector ETF returns.

    The ratio measures how dispersed sector returns are on the *latest_date*
    relative to the historical median.  A high ratio (>1.5) signals
    market divergence, which reduces confidence in macro timing signals.

    Returns the dispersion ratio (current_std / historical_median_std).
    Defaults to 1.0 (neutral) on failure.
    """
    try:
        rows = conn.execute(text("""
            WITH max_date AS (
                SELECT MAX(trade_date) AS md FROM sector_etf_daily
            ),
            date_range AS (
                SELECT md - INTERVAL '60 days' AS start_dt FROM max_date
            )
            SELECT trade_date, pct_chg
            FROM sector_etf_daily, date_range
            WHERE trade_date >= date_range.start_dt
              AND pct_chg IS NOT NULL
            ORDER BY trade_date
        """)).fetchall()

        if not rows:
            return 1.0

        df = pd.DataFrame(rows, columns=["trade_date", "pct_chg"])
        # Convert to string YYYYMMDD for groupby
        df["trade_date"] = df["trade_date"].apply(
            lambda d: d.strftime("%Y%m%d") if hasattr(d, "strftime") else str(d).replace("-", "")
        )

        daily_std = df.groupby("trade_date")["pct_chg"].std()

        if latest_date not in daily_std.index:
            return 1.0

        current_std = daily_std[latest_date]
        historical_median = float(daily_std.median())

        if historical_median == 0 or pd.isna(historical_median):
            return 1.0

        ratio = float(current_std) / historical_median
        return round(ratio, 4)
    except Exception as exc:
        logger.warning(f"Failed to compute cross-sectional dispersion: {exc}")
        return 1.0


def compute_market_timing() -> dict:
    """Compute multi-index market timing signal with cross-sectional dispersion.

    Fuses signals from CSI 500, CSI 300, and KCB 50 with weights
    0.5/0.3/0.2, then adjusts the composite score downward when
    cross-sectional dispersion is elevated.

    Returns:
        dict with keys:
        - date: str (latest available date across all indexes)
        - score: float [-1.0, +1.0] overall timing score (+ = bullish)
        - regime: str description of current regime
        - regime_cn: str Chinese description of current regime
        - adjustment: float [-0.3, +0.3] recommended position adjustment
        - signals: dict of per-index signal dicts + composite
        - dispersion: float cross-sectional dispersion ratio
        - narrative: str human-readable market assessment
        - error: str if computation failed
    """
    conn = _get_conn()
    try:
        # ── Compute signals for each index ──
        index_signals = {}
        for idx_key, ts_code in INDEX_CODES.items():
            sig = _compute_index_signals(ts_code, conn)
            if sig:
                index_signals[idx_key] = sig

        # ── Cross-sectional dispersion ──
        all_dates = [s["latest_date"] for s in index_signals.values()]
        latest_date = max(all_dates) if all_dates else None

        dispersion = (
            _compute_cross_sectional_dispersion(conn, latest_date)
            if latest_date else 1.0
        )
    finally:
        conn.close()

    if not index_signals:
        return {"error": "Insufficient data across all indexes", "score": 0.0, "adjustment": 0.0}

    # ── Weighted composite score ──
    total_weight = 0.0
    weighted_rsi_score = 0.0
    weighted_mom_score = 0.0
    weighted_share_score = 0.0

    for idx_key, weight in INDEX_WEIGHTS.items():
        if idx_key in index_signals:
            sig = index_signals[idx_key]
            weighted_rsi_score += weight * sig["rsi_score"]
            weighted_mom_score += weight * sig["mom_score"]
            weighted_share_score += weight * sig["share_score"]
            total_weight += weight

    if total_weight == 0:
        return {"error": "No index signals available", "score": 0.0, "adjustment": 0.0}

    # Normalise weights when not all indexes have data
    if total_weight < 1.0:
        scale = 1.0 / total_weight
        weighted_rsi_score *= scale
        weighted_mom_score *= scale
        weighted_share_score *= scale

    raw_score = weighted_rsi_score + weighted_mom_score + weighted_share_score

    # Apply dispersion discount: higher dispersion → lower confidence
    # dispersion=1.0 → full score; dispersion=2.0 → half score
    dispersion_factor = 1.0 / max(1.0, dispersion)
    overall_score = max(-1.0, min(1.0, raw_score * dispersion_factor))

    # Position adjustment [-0.3, +0.3]
    adjustment = overall_score * 0.3

    # ── Regime classification ──
    if overall_score > 0.3:
        regime = "oversold_recovery"
        regime_cn = "Oversold Recovery"
    elif overall_score > 0.1:
        regime = "slightly_bullish"
        regime_cn = "Slightly Bullish"
    elif overall_score < -0.2:
        regime = "overheated_caution"
        regime_cn = "Overheated Caution"
    else:
        regime = "neutral"
        regime_cn = "Neutral"

    # ── Narrative ──
    parts = []
    for idx_key, display_name in [("csi500", "CSI500"), ("csi300", "CSI300"), ("kc50", "KCB50")]:
        if idx_key in index_signals:
            sig = index_signals[idx_key]
            rsi_val = sig["rsi"]
            if rsi_val < 40:
                parts.append(f"{display_name} RSI={rsi_val:.0f} oversold")
            elif rsi_val > 70:
                parts.append(f"{display_name} RSI={rsi_val:.0f} elevated")
            mom_val = sig["momentum_20d"]
            if abs(mom_val) > 0.05:
                parts.append(f"{display_name} 20d={mom_val*100:.1f}%")

    if dispersion > 1.5:
        parts.append(f"high cross-sectional dispersion ({dispersion:.2f}x)")

    narrative = "; ".join(parts) if parts else "Market in neutral state, no significant signals"

    # ── Build per-index signals ──
    signals = {}
    for idx_key in ["csi500", "csi300", "kc50"]:
        if idx_key in index_signals:
            sig = index_signals[idx_key]
            signals[idx_key] = {
                "rsi": sig["rsi"],
                "rsi_score": sig["rsi_score"],
                "momentum_20d": sig["momentum_20d"],
                "mom_score": sig["mom_score"],
                "share_flow_10d": sig["share_flow_10d"],
                "share_score": sig["share_score"],
            }

    return {
        "date": latest_date,
        "score": round(overall_score, 4),
        "regime": regime,
        "regime_cn": regime_cn,
        "adjustment": round(adjustment, 4),
        "signals": signals,
        "dispersion": dispersion,
        "narrative": narrative,
    }