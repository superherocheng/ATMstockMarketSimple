"""Transform DB query results into ECharts-ready JSON for the 7 chart types.

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


def build_factor_distribution(preset_id: str) -> dict:
    """Chart 1: Factor distribution histogram for the latest date."""
    conn = _get_conn()
    try:
        row = conn.execute(text(
            "SELECT MAX(trade_date) FROM factor_daily WHERE preset_id = :pid"
        ), {"pid": preset_id}).fetchone()
        if not row or not row[0]:
            return {"error": "no_data"}
        latest_date = row[0]

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


def build_ic_series(preset_id: str, forward_days: int = 5) -> dict:
    """Chart 2: IC time series with mean line and +/-2 std band."""
    conn = _get_conn()
    try:
        rows = conn.execute(text(
            "SELECT trade_date, ic_value FROM ic_daily "
            "WHERE preset_id = :pid AND forward_days = :h ORDER BY trade_date"
        ), {"pid": preset_id, "h": forward_days}).fetchall()

        summary_row = conn.execute(text(
            "SELECT ic_mean, ic_std FROM ic_summary "
            "WHERE preset_id = :pid AND forward_days = :h"
        ), {"pid": preset_id, "h": forward_days}).fetchone()
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
                 "itemStyle": {"color": "#5a6f5a"}, "symbol": "none"},
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


def build_ic_decay(preset_id: str) -> dict:
    """Chart 3: IC mean vs forward period (decay curve)."""
    conn = _get_conn()
    try:
        rows = conn.execute(text(
            "SELECT forward_days, ic_mean FROM ic_summary "
            "WHERE preset_id = :pid ORDER BY forward_days"
        ), {"pid": preset_id}).fetchall()
    finally:
        conn.close()

    if not rows:
        return {"error": "no_data"}

    periods = [f"{r[0]}D" for r in rows]
    means = [round(float(r[1]), 4) if r[1] is not None else 0 for r in rows]

    return _safe_dict({
        "chart": {
            "xAxis": {"type": "category", "data": periods, "name": "持有期"},
            "yAxis": {"type": "value", "name": "IC均值"},
            "series": [{"type": "line", "data": means, "smooth": True,
                        "lineStyle": {"width": 2.5, "color": "#5a6f5a"},
                        "itemStyle": {"color": "#5a6f5a"}, "symbolSize": 8}],
            "tooltip": {"trigger": "axis"},
        }
    })


def build_quadrant_heatmap(preset_id: str, forward_days: int = None) -> dict:
    """Chart 4: Quadrant return heatmap."""
    preset = get_preset(preset_id)
    if forward_days is None:
        forward_days = preset["forward_periods"][0]

    conn = _get_conn()
    try:
        row = conn.execute(text(
            "SELECT MAX(trade_date) FROM quadrant_perf "
            "WHERE preset_id = :pid AND forward_days = :h"
        ), {"pid": preset_id, "h": forward_days}).fetchone()

        if not row or not row[0]:
            return {"error": "no_data"}
        latest_date = row[0]

        rows = conn.execute(text(
            "SELECT quadrant, avg_forward_ret FROM quadrant_perf "
            "WHERE preset_id = :pid AND forward_days = :h AND trade_date = :d"
        ), {"pid": preset_id, "h": forward_days, "d": latest_date}).fetchall()
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


def build_group_returns(preset_id: str, forward_days: int = None) -> dict:
    """Chart 5: Cumulative return curves per quadrant over time."""
    preset = get_preset(preset_id)
    if forward_days is None:
        forward_days = preset["forward_periods"][0]

    conn = _get_conn()
    try:
        rows = conn.execute(text(
            "SELECT trade_date, quadrant, avg_forward_ret FROM quadrant_perf "
            "WHERE preset_id = :pid AND forward_days = :h ORDER BY trade_date"
        ), {"pid": preset_id, "h": forward_days}).fetchall()
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


def build_rolling_icir(preset_id: str, forward_days: int = 5, window: int = 60) -> dict:
    """Chart 6: Rolling ICIR time series."""
    conn = _get_conn()
    try:
        rows = conn.execute(text(
            "SELECT trade_date, ic_value FROM ic_daily "
            "WHERE preset_id = :pid AND forward_days = :h ORDER BY trade_date"
        ), {"pid": preset_id, "h": forward_days}).fetchall()
    finally:
        conn.close()

    if not rows:
        return {"error": "no_data"}

    # Auto-reduce window if not enough data points
    if len(rows) < window:
        window = max(20, len(rows) // 2)
    if len(rows) < 20:
        return {"error": "no_data"}

    dates_all = [str(r[0]) for r in rows]
    ics = pd.Series([float(r[1]) if r[1] is not None else np.nan for r in rows])

    rolling_mean = ics.rolling(window).mean()
    rolling_std = ics.rolling(window).std()
    rolling_icir = (rolling_mean / rolling_std).fillna(0)

    valid_idx = list(range(window - 1, len(dates_all)))
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


def build_weight_recommendation(preset_id: str) -> dict:
    """Chart 7: Allocation weight recommendation based on latest factor values."""
    conn = _get_conn()
    try:
        row = conn.execute(text(
            "SELECT MAX(trade_date) FROM factor_daily WHERE preset_id = :pid"
        ), {"pid": preset_id}).fetchone()
        if not row or not row[0]:
            return {"error": "no_data"}
        latest_date = row[0]

        rows = conn.execute(text(
            "SELECT etf_code, factor, quadrant FROM factor_daily "
            "WHERE preset_id = :pid AND trade_date = :d ORDER BY factor DESC"
        ), {"pid": preset_id, "d": latest_date}).fetchall()
    finally:
        conn.close()

    if not rows:
        return {"error": "no_data"}

    from config.config import SECTOR_ETF

    recommended = []
    for r in rows:
        code, factor, quadrant = r[0], float(r[1]) if r[1] else 0, int(r[2])
        if quadrant in [1, 2]:
            name = SECTOR_ETF.get(code, code)
            recommended.append({"name": name, "factor": round(factor, 3),
                                "quadrant": quadrant, "code": code})

    if not recommended:
        return _safe_dict({"chart": {"xAxis": {"type": "category", "data": []},
                                      "yAxis": {"type": "value"}, "series": []}})

    pos_factors = [abs(r["factor"]) for r in recommended]
    total = sum(pos_factors)
    weights = [f / total for f in pos_factors] if total > 0 else [1.0 / len(recommended)] * len(recommended)

    for i, r in enumerate(recommended):
        r["weight"] = round(weights[i] * 100, 1)

    colors_map = {1: "#4a7c4a", 2: "#8fbc8f"}

    return _safe_dict({
        "date": str(latest_date),
        "chart": {
            "xAxis": {"type": "category",
                      "data": [f"{r['name']}(Q{r['quadrant']})" for r in recommended]},
            "yAxis": {"type": "value", "name": "建议权重(%)", "max": max(w * 100 for w in weights) * 1.2 if weights else 100},
            "series": [{"type": "bar",
                        "data": [{"value": r["weight"],
                                  "itemStyle": {"color": colors_map[r["quadrant"]]}}
                                 for r in recommended],
                        "barMaxWidth": 40}],
            "tooltip": {"trigger": "axis"},
        }
    })


def build_summary(preset_id: str) -> dict:
    """Text summary with factor validity, quadrant verification, and recommendations."""
    conn = _get_conn()
    try:
        summary_rows = conn.execute(text(
            "SELECT forward_days, ic_mean, icir, ic_win_rate, sample_count "
            "FROM ic_summary WHERE preset_id = :pid ORDER BY forward_days"
        ), {"pid": preset_id}).fetchall()

        latest_row = conn.execute(text(
            "SELECT MAX(trade_date) FROM factor_daily WHERE preset_id = :pid"
        ), {"pid": preset_id}).fetchone()
        latest_date = latest_row[0] if latest_row else None

        latest_factors = []
        if latest_date:
            rows = conn.execute(text(
                "SELECT etf_code, factor, quadrant FROM factor_daily "
                "WHERE preset_id = :pid AND trade_date = :d ORDER BY factor DESC"
            ), {"pid": preset_id, "d": latest_date}).fetchall()
            from config.config import SECTOR_ETF
            for r in rows:
                latest_factors.append({
                    "code": r[0], "name": SECTOR_ETF.get(r[0], r[0]),
                    "factor": round(float(r[1]), 3) if r[1] else 0, "quadrant": int(r[2]),
                })
    finally:
        conn.close()

    factor_validity = ""
    decay_period = "未知"
    if summary_rows:
        first_h = summary_rows[0]
        ic_mean = first_h[1]
        icir = first_h[2]
        if ic_mean is not None:
            direction = "正" if ic_mean > 0 else "负"
            strength = "显著" if abs(ic_mean) > 0.03 else "较弱"
            factor_validity = f"IC均值{ic_mean:.3f}({direction}向{strength})"
        if icir is not None:
            stability = "稳定" if abs(icir) > 0.5 else "不稳定"
            factor_validity += f", ICIR {icir:.2f}({stability})"

        for sr in summary_rows:
            if sr[1] is not None and abs(sr[1]) < 0.02:
                decay_period = f"{sr[0]}日"
                break
        else:
            if summary_rows:
                decay_period = f">{summary_rows[-1][0]}日"

    # Top-level KPI values from the first forward period
    first_summary = summary_rows[0] if summary_rows else None
    top_ic_mean = float(first_summary[1]) if first_summary and first_summary[1] is not None else None
    top_icir = float(first_summary[2]) if first_summary and first_summary[2] is not None else None
    top_ic_win = float(first_summary[3]) if first_summary and first_summary[3] is not None else None

    q1_etfs = [f for f in latest_factors if f["quadrant"] == 1]
    q2_etfs = [f for f in latest_factors if f["quadrant"] == 2]
    strong_buy = "、".join([e["name"] for e in q1_etfs[:5]]) or "无"
    contrarian = "、".join([e["name"] for e in q2_etfs[:5]]) or "无"

    return _safe_dict({
        "date": str(latest_date) if latest_date else None,
        "ic_mean": top_ic_mean,
        "icir": top_icir,
        "ic_win_rate": top_ic_win,
        "factor_validity": factor_validity,
        "decay_period": decay_period,
        "strong_buy": strong_buy,
        "contrarian": contrarian,
        "q1_count": len(q1_etfs),
        "q2_count": len(q2_etfs),
        "summary_rows": [{"forward_days": r[0], "ic_mean": r[1], "icir": r[2],
                          "ic_win_rate": r[3], "sample_count": r[4]}
                         for r in summary_rows],
    })
