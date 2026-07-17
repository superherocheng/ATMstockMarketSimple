"""Transform DB query results into ECharts-ready JSON for chart types.

Each function takes raw data and returns a dict that can be directly
used as the ECharts `option` object.
"""
import logging

import numpy as np
import pandas as pd
from sqlalchemy import text

from src.analysis.presets import get_preset

logger = logging.getLogger(__name__)


def _get_conn():
    from src.core.db_manager_postgresql import get_conn
    return get_conn()


def _safe_dict(d):
    from src.core.db_manager_postgresql import safe_dict
    return safe_dict(d)


def _get_forward_days(preset_id):
    """Get the single forward period for a preset."""
    return get_preset(preset_id)["forward_periods"][0]


def _get_latest_date(preset_id: str, min_etf_ratio: float = 0.6) -> str:
    """Get the latest date with sufficient configured SECTOR_ETF coverage.

    Finds the most recent trading date where at least `min_etf_ratio` of the
    currently configured SECTOR_ETFs have factor data. This prevents showing
    a date with only partial data (e.g. when share data for some ETFs lags).

    Falls back to the simple MAX(trade_date) if no date meets the threshold.
    """
    from config.config import SECTOR_ETF
    from src.core.db_manager_postgresql import bind_inlist
    conn = _get_conn()
    try:
        total_configured = len(SECTOR_ETF)
        placeholders, code_params = bind_inlist(list(SECTOR_ETF.keys()), prefix="c")
        params = {
            "pid": preset_id,
            "min_cnt": max(3, int(total_configured * min_etf_ratio)),
            **code_params,
        }

        sql = text("""
            SELECT f.trade_date, COUNT(DISTINCT f.etf_code) as etf_cnt
            FROM factor_daily f
            INNER JOIN (SELECT DISTINCT trade_date FROM factor_daily
                        WHERE preset_id = :pid) td
                   ON f.trade_date = td.trade_date
            WHERE f.preset_id = :pid
              AND f.etf_code IN ({})
            GROUP BY f.trade_date
            HAVING COUNT(DISTINCT f.etf_code) >= :min_cnt
            ORDER BY f.trade_date DESC
            LIMIT 1
        """.format(placeholders))

        row = conn.execute(sql, params).fetchone()
        if row:
            return row[0]
    except Exception:
        pass
    finally:
        conn.close()

    # Fallback: simple MAX (use new connection in case prior close() failed)
    conn2 = _get_conn()
    try:
        row = conn2.execute(text(
            "SELECT MAX(trade_date) FROM factor_daily WHERE preset_id = :pid"
        ), {"pid": preset_id}).fetchone()
        return row[0] if row else None
    finally:
        conn2.close()


def build_factor_distribution(preset_id: str) -> dict:
    """Chart 1: Factor distribution histogram for the latest date."""
    latest_date = _get_latest_date(preset_id)
    if not latest_date:
        return {"error": "no_data"}

    conn = _get_conn()
    try:
        rows = conn.execute(text(
            "SELECT factor FROM factor_daily WHERE preset_id = :pid AND trade_date = :d"
        ), {"pid": preset_id, "d": latest_date}).fetchall()
    finally:
        conn.close()

    if not rows:
        return {"error": "no_data"}

    values = [float(r[0]) for r in rows if r[0] is not None]
    bins = np.linspace(min(values) - 0.1, max(values) + 0.1, 11)
    counts, edges = np.histogram(values, bins=bins)
    labels = [f"{edges[i]:.2f}~{edges[i+1]:.2f}" for i in range(len(counts))]

    return _safe_dict({
        "date": str(latest_date),
        "chart": {
            "xAxis": {"type": "category", "data": labels, "axisLabel": {"rotate": 30, "fontSize": 10}},
            "yAxis": {"type": "value", "name": "ETF数量"},
            "series": [{"type": "bar", "data": [int(c) for c in counts],
                        "itemStyle": {"color": "#5a6f5a"}}],
            "tooltip": {"trigger": "axis"},
        }
    })


def build_ic_series(preset_id: str) -> dict:
    """Chart 2: IC time series with mean line and +/-2 std band."""
    h = _get_forward_days(preset_id)
    conn = _get_conn()
    try:
        rows = conn.execute(text(
            "SELECT trade_date, ic_value FROM ic_daily "
            "WHERE preset_id = :pid AND forward_days = :h ORDER BY trade_date"
        ), {"pid": preset_id, "h": h}).fetchall()

        summary_row = conn.execute(text(
            "SELECT ic_mean, ic_std FROM ic_summary "
            "WHERE preset_id = :pid AND forward_days = :h"
        ), {"pid": preset_id, "h": h}).fetchone()
    finally:
        conn.close()

    if not rows:
        return {"error": "no_data"}

    dates = [str(r[0]) for r in rows]
    ics = [float(r[1]) if r[1] is not None else None for r in rows]
    ic_mean = float(summary_row[0]) if summary_row and summary_row[0] else 0
    ic_std = float(summary_row[1]) if summary_row and summary_row[1] else 0

    return _safe_dict({
        "chart": {
            "xAxis": {"type": "category", "data": dates, "axisLabel": {"fontSize": 9, "rotate": 45}},
            "yAxis": {"type": "value", "name": "IC"},
            "series": [
                {"name": "IC", "type": "line", "data": ics, "lineStyle": {"width": 1.5},
                 "itemStyle": {"color": "#5a6f5a"}, "symbol": "none",
                 "markLine": {
                     "silent": True,
                     "symbol": "none",
                     "lineStyle": {"color": "#FF4D4F", "type": "dashed", "width": 1},
                     "data": [
                         {"yAxis": 0.03, "label": {"formatter": "+0.03 meaningful", "fontSize": 9}},
                         {"yAxis": -0.03, "label": {"formatter": "-0.03", "fontSize": 9}},
                     ],
                 }},
                {"name": "IC均值", "type": "line", "data": [round(ic_mean, 4)] * len(dates),
                 "lineStyle": {"width": 2, "color": "#8b4513", "type": "dashed"}, "symbol": "none"},
                {"name": "+2σ", "type": "line", "data": [round(ic_mean + 2 * ic_std, 4)] * len(dates),
                 "lineStyle": {"width": 1, "color": "#c4d4c4", "type": "dotted"}, "symbol": "none"},
                {"name": "-2σ", "type": "line", "data": [round(ic_mean - 2 * ic_std, 4)] * len(dates),
                 "lineStyle": {"width": 1, "color": "#c4d4c4", "type": "dotted"}, "symbol": "none"},
            ],
            "tooltip": {"trigger": "axis"},
            "legend": {"bottom": 0, "textStyle": {"fontSize": 10}},
        }
    })


def build_quadrant_heatmap(preset_id: str) -> dict:
    """Chart 3: Quadrant return heatmap."""
    h = _get_forward_days(preset_id)

    conn = _get_conn()
    try:
        # Use the latest date from factor_daily (with sufficient coverage)
        # rather than quadrant_perf, which may have dates with sparse data
        latest_date = _get_latest_date(preset_id)
        if not latest_date:
            return {"error": "no_data"}

        # Look up quadrant_perf for that date (may be slightly older, that's OK)
        rows = conn.execute(text(
            "SELECT quadrant, avg_forward_ret FROM quadrant_perf "
            "WHERE preset_id = :pid AND forward_days = :h AND trade_date = :d"
        ), {"pid": preset_id, "h": h, "d": latest_date}).fetchall()

        if not rows:
            # Fallback: try the latest quadrant_perf date
            row = conn.execute(text(
                "SELECT MAX(trade_date) FROM quadrant_perf "
                "WHERE preset_id = :pid AND forward_days = :h"
            ), {"pid": preset_id, "h": h}).fetchone()
            if row and row[0]:
                latest_date = row[0]
                rows = conn.execute(text(
                    "SELECT quadrant, avg_forward_ret FROM quadrant_perf "
                    "WHERE preset_id = :pid AND forward_days = :h AND trade_date = :d"
                ), {"pid": preset_id, "h": h, "d": latest_date}).fetchall()
    finally:
        conn.close()

    if not rows:
        return {"error": "no_data"}

    quad_map = {r[0]: float(r[1]) * 100 for r in rows if r[1] is not None}
    labels = {1: "Q1 强势", 2: "Q2 潜伏", 3: "Q3 撤离", 4: "Q4 风险"}

    quadrants = [
        {"name": labels[2], "value": round(quad_map.get(2, 0), 2),
         "itemStyle": {"color": "#c4d4c4"}},
        {"name": labels[1], "value": round(quad_map.get(1, 0), 2),
         "itemStyle": {"color": "#4a7c4a"}},
        {"name": labels[3], "value": round(quad_map.get(3, 0), 2),
         "itemStyle": {"color": "#d4c4b0"}},
        {"name": labels[4], "value": round(quad_map.get(4, 0), 2),
         "itemStyle": {"color": "#e8c8c0"}},
    ]

    return _safe_dict({
        "date": str(latest_date),
        "chart": {
            "quadrants": quadrants,
            "axis_labels": {"x": "Z_Mom (价格动量)", "y": "Z_Flow (资金流)"},
        }
    })


def build_group_returns(preset_id: str) -> dict:
    """Chart 4: Cumulative return curves per quadrant over time."""
    h = _get_forward_days(preset_id)

    conn = _get_conn()
    try:
        rows = conn.execute(text(
            "SELECT trade_date, quadrant, avg_forward_ret FROM quadrant_perf "
            "WHERE preset_id = :pid AND forward_days = :h ORDER BY trade_date"
        ), {"pid": preset_id, "h": h}).fetchall()
    finally:
        conn.close()

    if not rows:
        return {"error": "no_data"}

    df = pd.DataFrame(rows, columns=["trade_date", "quadrant", "avg_forward_ret"])
    dates = sorted(df["trade_date"].unique())

    colors = {1: "#4a7c4a", 2: "#8fbc8f", 3: "#cd853f", 4: "#cd5c5c"}
    names = {1: "Q1强势", 2: "Q2潜伏", 3: "Q3撤离", 4: "Q4风险"}
    series = []

    for q in [1, 2, 3, 4]:
        q_df = df[df["quadrant"] == q].sort_values("trade_date")
        cumulative = (1 + q_df["avg_forward_ret"].astype(float)).cumprod() - 1
        series.append({
            "name": names[q],
            "type": "line",
            "data": [round(float(v) * 100, 2) for v in cumulative],
            "lineStyle": {"width": 2 if q in [1, 3] else 1.5,
                          "type": "solid" if q in [1, 3] else "dashed",
                          "color": colors[q]},
            "itemStyle": {"color": colors[q]},
            "symbol": "none",
        })

    return _safe_dict({
        "chart": {
            "xAxis": {"type": "category", "data": [str(d) for d in dates],
                      "axisLabel": {"fontSize": 9, "rotate": 45}},
            "yAxis": {"type": "value", "name": "累计收益(%)"},
            "series": series,
            "tooltip": {"trigger": "axis"},
            "legend": {"bottom": 0, "textStyle": {"fontSize": 10}},
        }
    })


def build_rolling_icir(preset_id: str, window: int = 60) -> dict:
    """Chart 5: Rolling ICIR time series."""
    h = _get_forward_days(preset_id)

    conn = _get_conn()
    try:
        rows = conn.execute(text(
            "SELECT trade_date, ic_value FROM ic_daily "
            "WHERE preset_id = :pid AND forward_days = :h ORDER BY trade_date"
        ), {"pid": preset_id, "h": h}).fetchall()
    finally:
        conn.close()

    if not rows:
        return {"error": "no_data"}

    n = len(rows)
    if n < 10:
        return {"error": "no_data"}

    # Auto-adapt window: use requested window if enough data, otherwise smaller
    actual_window = min(window, max(10, n // 2))

    dates_all = [str(r[0]) for r in rows]
    ics = pd.Series([float(r[1]) if r[1] is not None else np.nan for r in rows])

    rolling_mean = ics.rolling(actual_window).mean()
    rolling_std = ics.rolling(actual_window).std()
    rolling_icir = (rolling_mean / rolling_std).fillna(0)

    valid_idx = list(range(actual_window - 1, n))
    valid_dates = [dates_all[i] for i in valid_idx]
    valid_icir = [round(float(rolling_icir.iloc[i]), 4) for i in valid_idx]

    return _safe_dict({
        "chart": {
            "xAxis": {"type": "category", "data": valid_dates,
                      "axisLabel": {"fontSize": 9, "rotate": 45}},
            "yAxis": {"type": "value", "name": "Rolling ICIR"},
            "series": [{"type": "line", "data": valid_icir,
                        "lineStyle": {"width": 1.5, "color": "#8b4513"},
                        "itemStyle": {"color": "#8b4513"}, "symbol": "none",
                        "areaStyle": {"color": "rgba(139,69,19,0.05)"}}],
            "tooltip": {"trigger": "axis"},
        }
    })


def build_summary(preset_id: str) -> dict:
    """Text summary with factor validity and recommendations."""
    h = _get_forward_days(preset_id)
    latest_date = _get_latest_date(preset_id)

    conn = _get_conn()
    try:
        summary_row = conn.execute(text(
            "SELECT ic_mean, icir, ic_win_rate, sample_count "
            "FROM ic_summary WHERE preset_id = :pid AND forward_days = :h"
        ), {"pid": preset_id, "h": h}).fetchone()

        latest_factors = []
        if latest_date:
            rows = conn.execute(text(
                "SELECT etf_code, factor, quadrant FROM factor_daily "
                "WHERE preset_id = :pid AND trade_date = :d ORDER BY factor DESC"
            ), {"pid": preset_id, "d": latest_date}).fetchall()
            from config.config import SECTOR_ETF
            for r in rows:
                code = r[0]
                # Skip ETFs no longer in current config
                if code not in SECTOR_ETF:
                    continue
                factor = round(float(r[1]), 3) if r[1] else 0
                quadrant = int(r[2])
                latest_factors.append({
                    "code": code, "name": SECTOR_ETF[code],
                    "factor": factor, "quadrant": quadrant,
                })

            # Compute suggested weight for Q1/Q2 (same logic as recommendation engine)
            q12 = [f for f in latest_factors if f["quadrant"] in (1, 2)]
            pos_scores = [max(0, f["factor"]) for f in q12]
            total_pos = sum(pos_scores)
            for f in latest_factors:
                if f["quadrant"] in (1, 2) and total_pos > 0:
                    f["weight"] = round(max(0, f["factor"]) / total_pos * 100, 1)
                else:
                    f["weight"] = 0.0
    finally:
        conn.close()

    ic_mean = float(summary_row[0]) if summary_row and summary_row[0] else None
    icir = float(summary_row[1]) if summary_row and summary_row[1] else None
    ic_win_rate = float(summary_row[2]) if summary_row and summary_row[2] else None
    sample_count = int(summary_row[3]) if summary_row and summary_row[3] else 0

    factor_validity = ""
    if ic_mean is not None:
        direction = "正" if ic_mean > 0 else "负"
        strength = "显著" if abs(ic_mean) > 0.03 else "较弱"
        factor_validity = f"IC均值{ic_mean:.3f}({direction}向{strength})"
    if icir is not None:
        stability = "稳定" if abs(icir) > 0.5 else "不稳定"
        factor_validity += f", ICIR {icir:.2f}({stability})"

    q1_etfs = [f for f in latest_factors if f["quadrant"] == 1]
    q2_etfs = [f for f in latest_factors if f["quadrant"] == 2]
    strong_buy = "、".join([e["name"] for e in q1_etfs[:5]]) or "无"
    contrarian = "、".join([e["name"] for e in q2_etfs[:5]]) or "无"

    return _safe_dict({
        "date": str(latest_date) if latest_date else None,
        "ic_mean": ic_mean,
        "icir": icir,
        "ic_win_rate": ic_win_rate,
        "sample_count": sample_count,
        "factor_validity": factor_validity,
        "strong_buy": strong_buy,
        "contrarian": contrarian,
        "q1_count": len(q1_etfs),
        "q2_count": len(q2_etfs),
        "latest_factors": latest_factors,
    })
