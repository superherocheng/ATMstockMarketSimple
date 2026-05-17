"""CSI 500 market timing indicator.

Computes a composite timing score from:
- RSI(14): oversold/overbought regime
- 20-day momentum: trend exhaustion signal
- Share flow (10d): smart money flow signal

The timing score is used to adjust the overall position sizing
in the investment recommendation engine.
"""
import logging

import numpy as np
import pandas as pd
from sqlalchemy import text

logger = logging.getLogger(__name__)

# ── Constants ──
CSI500_CODE = "510500.SH"
RSI_PERIOD = 14
MOM_PERIOD = 20
SHARE_FLOW_PERIOD = 10
MIN_HISTORY = 30  # minimum data points for computing


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


def compute_market_timing() -> dict:
    """Compute CSI 500 market timing signal.

    Returns:
        dict with keys:
        - date: str (latest available date)
        - score: float [-1.0, +1.0] overall timing score (+ = bullish)
        - regime: str description of current regime
        - signals: dict of individual signal values
        - adjustment: float [-0.3, +0.3] recommended position adjustment
        - narrative: str human-readable market assessment
        - error: str if computation failed
    """
    conn = _get_conn()
    try:
        # Fetch CSI 500 daily prices
        price_rows = conn.execute(text("""
            SELECT trade_date, close
            FROM index_etf_daily
            WHERE ts_code = :code
            ORDER BY trade_date
        """), {"code": CSI500_CODE}).fetchall()

        # Fetch CSI 500 share data
        share_rows = conn.execute(text("""
            SELECT trade_date, fd_share
            FROM etf_share
            WHERE ts_code = :code
            ORDER BY trade_date
        """), {"code": CSI500_CODE}).fetchall()

        # Latest sector ETF avg return for cross-check (optional)
        latest_sector = conn.execute(text("""
            SELECT MAX(trade_date) FROM sector_etf_daily
        """)).fetchone()

    finally:
        conn.close()

    if not price_rows or len(price_rows) < MIN_HISTORY:
        return {"error": "中证500数据不足", "score": 0.0, "adjustment": 0.0}

    # ── Build price series ──
    dates = [str(r[0]) for r in price_rows]
    closes = np.array([float(r[1]) for r in price_rows])

    latest_date = dates[-1]

    # Build share map
    share_map = {}
    for r in share_rows:
        d = str(r[0])
        v = float(r[1]) if r[1] else None
        if v and v > 0:
            share_map[d] = v

    # ── Compute signals ──

    # 1. RSI(14)
    rsi_vals = _compute_rsi(closes, RSI_PERIOD)
    current_rsi = float(rsi_vals[-1])

    # 2. 20-day momentum
    if len(closes) > MOM_PERIOD:
        current_mom = float(closes[-1] / closes[-(MOM_PERIOD + 1)] - 1)
    else:
        current_mom = 0.0

    # 3. Share flow (10-day pct change)
    current_share_flow = 0.0
    if latest_date in share_map:
        # Find date ~10 trading days ago
        idx_10 = max(0, len(dates) - SHARE_FLOW_PERIOD - 1)
        date_10 = dates[idx_10]
        if date_10 in share_map:
            s_now = share_map[latest_date]
            s_then = share_map[date_10]
            current_share_flow = float((s_now - s_then) / s_then * 100)

    # ── Compute timing score ──
    # Score components: each contributes [-0.5, +0.5], summed → [-1, +1]

    rsi_score = 0.0
    if current_rsi < 40:
        # Oversold → bullish (up to +0.5 when RSI=20)
        rsi_score = min(0.5, (40 - current_rsi) / 40 * 0.5)
    elif current_rsi > 75:
        # Extremely overbought → slightly bearish (A-shares trend strong)
        rsi_score = -min(0.2, (current_rsi - 75) / 25 * 0.2)
    else:
        # Neutral: RSI 40-75
        rsi_score = 0.0

    mom_score = 0.0
    if current_mom > 0.08:
        # Very strong momentum → caution on mean reversion
        mom_score = -min(0.3, (current_mom - 0.08) / 0.10 * 0.3)
    elif current_mom < -0.08:
        # Very weak momentum → potential reversal
        mom_score = min(0.3, (abs(current_mom) - 0.08) / 0.10 * 0.3)
    else:
        mom_score = 0.0

    share_score = 0.0
    if current_share_flow > 3:
        # Strong inflow → bullish smart money
        share_score = min(0.5, (current_share_flow - 3) / 10 * 0.5)
    elif current_share_flow < -3:
        # Strong outflow → bearish
        share_score = -min(0.3, (abs(current_share_flow) - 3) / 10 * 0.3)

    raw_score = rsi_score + mom_score + share_score
    overall_score = max(-1.0, min(1.0, raw_score))

    # Position adjustment [-0.3, +0.3]
    adjustment = overall_score * 0.3

    # ── Regime classification ──
    if overall_score > 0.3:
        regime = "oversold_recovery"  # 超卖修复期
        regime_cn = "超卖修复"
    elif overall_score > 0.1:
        regime = "slightly_bullish"
        regime_cn = "温和看多"
    elif overall_score < -0.2:
        regime = "overheated_caution"
        regime_cn = "过热谨慎"
    else:
        regime = "neutral"
        regime_cn = "中性"

    # ── Narrative ──
    parts = []
    if current_rsi < 40:
        parts.append(f"RSI={current_rsi:.0f} 处于超卖区域, 超跌反弹概率大")
    elif current_rsi > 70:
        parts.append(f"RSI={current_rsi:.0f} 偏高, 注意短期过热风险")

    if current_mom > 0.05:
        parts.append(f"近20日涨幅{current_mom*100:.1f}%")
    elif current_mom < -0.05:
        parts.append(f"近20日跌幅{abs(current_mom)*100:.1f}%")

    if current_share_flow > 5:
        parts.append(f"中证500ETF份额近10日增长{current_share_flow:.1f}%, 资金流入显著")
    elif current_share_flow < -3:
        parts.append(f"中证500ETF份额近10日缩减{abs(current_share_flow):.1f}%")

    narrative = "；".join(parts) if parts else "市场处于中性状态，无显著信号"

    return {
        "date": latest_date,
        "score": round(overall_score, 4),
        "regime": regime,
        "regime_cn": regime_cn,
        "adjustment": round(adjustment, 4),
        "signals": {
            "rsi": round(current_rsi, 1),
            "rsi_score": round(rsi_score, 4),
            "momentum_20d": round(current_mom, 4),
            "mom_score": round(mom_score, 4),
            "share_flow_10d": round(current_share_flow, 2),
            "share_score": round(share_score, 4),
        },
        "narrative": narrative,
    }
