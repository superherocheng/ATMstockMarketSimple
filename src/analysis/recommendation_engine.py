"""Investment recommendation engine.

Generates structured investment recommendations by combining:
- Multi-factor model scores (from factor_daily)
- IC statistics (factor validity assessment)
- Market timing (CSI 500 regime signal)
- Cross-ETF correlation penalty
- Risk budgeting position sizing

Every recommendation includes confidence level, rationale, and risk warnings.
"""
import logging
from datetime import datetime

import numpy as np
import pandas as pd
from sqlalchemy import text

logger = logging.getLogger(__name__)


def _get_conn():
    from src.core.db_manager_postgresql import get_conn
    return get_conn()


def _safe_dict(d):
    from src.core.db_manager_postgresql import safe_dict
    return safe_dict(d)


def build_investment_recommendation(preset_id: str = "short") -> dict:
    """Generate a professional investment recommendation report.

    Args:
        preset_id: Factor preset to use ("short", "medium", "long")

    Returns:
        dict matching the investment_recommendation.html frontend schema.
    """
    from src.analysis.presets import get_preset
    from src.analysis.market_timing import compute_market_timing
    from config.config import SECTOR_ETF

    preset = get_preset(preset_id)
    conn = _get_conn()
    try:
        # ── 1. Get latest factor date ──
        date_row = conn.execute(text("""
            SELECT MAX(trade_date) FROM factor_daily WHERE preset_id = :pid
        """), {"pid": preset_id}).fetchone()
        if not date_row or not date_row[0]:
            return {"error": "暂无因子数据，请先运行因子计算", "recommendations": []}
        latest_date = date_row[0]

        # ── 2. Get all ETFs' latest factor values ──
        # Check if rsrs columns exist (may not if migration hasn't run)
        has_rsrs = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='factor_daily' AND column_name='rsrs'"
        )).fetchone() is not None

        if has_rsrs:
            factor_rows = conn.execute(text("""
                SELECT etf_code, z_flow, z_mom, factor, quadrant, flow, mom,
                       rsrs, z_rsrs
                FROM factor_daily
                WHERE preset_id = :pid AND trade_date = :d
                ORDER BY factor DESC
            """), {"pid": preset_id, "d": latest_date}).fetchall()
        else:
            factor_rows = conn.execute(text("""
                SELECT etf_code, z_flow, z_mom, factor, quadrant, flow, mom
                FROM factor_daily
                WHERE preset_id = :pid AND trade_date = :d
                ORDER BY factor DESC
            """), {"pid": preset_id, "d": latest_date}).fetchall()

        # ── 3. Get IC summary statistics ──
        ic_rows = conn.execute(text("""
            SELECT forward_days, ic_mean, ic_std, icir, ic_win_rate, sample_count
            FROM ic_summary
            WHERE preset_id = :pid
            ORDER BY forward_days
        """), {"pid": preset_id}).fetchall()

        # ── 4. Get best forward period (highest ICIR) for display ──
        best_fwd = preset["forward_periods"][0]  # default
        best_icir = -999
        for r in ic_rows:
            if r[3] is not None and float(r[3]) > best_icir:
                best_icir = float(r[3])
                best_fwd = r[0]
        optimal_h = best_fwd

        # Get quadrant performance at optimal H
        qp_rows = conn.execute(text("""
            SELECT quadrant, AVG(avg_forward_ret) as avg_ret,
                   COUNT(*) as samples,
                   SUM(CASE WHEN avg_forward_ret > 0 THEN 1 ELSE 0 END) as wins
            FROM quadrant_perf
            WHERE preset_id = :pid AND forward_days = :h
            GROUP BY quadrant
        """), {"pid": preset_id, "h": optimal_h}).fetchall()

        # ── 5. Get ETF close prices for correlation computation ──
        close_rows = conn.execute(text("""
            SELECT ts_code, trade_date, close
            FROM sector_etf_daily
            WHERE ts_code IN (SELECT etf_code FROM factor_daily
                              WHERE preset_id = :pid AND trade_date = :d)
            ORDER BY ts_code, trade_date
        """), {"pid": preset_id, "d": latest_date}).fetchall()

    finally:
        conn.close()

    if not factor_rows:
        return {"error": "暂无因子数据", "recommendations": []}

    # ── Build data structures ──
    sector_names = dict(SECTOR_ETF)

    # ETF factor data
    etf_data = {}
    for r in factor_rows:
        code = r[0]
        etf_data[code] = {
            "code": code,
            "name": sector_names.get(code, code),
            "z_flow": float(r[1]) if r[1] else 0,
            "z_mom": float(r[2]) if r[2] else 0,
            "factor": float(r[3]) if r[3] else 0,
            "quadrant": int(r[4]) if r[4] else 0,
            "flow_raw": float(r[5]) if r[5] else 0,
            "mom_raw": float(r[6]) if r[6] else 0,
        }

    # IC stats
    ic_summary = {}
    for r in ic_rows:
        ic_summary[r[0]] = {
            "ic_mean": float(r[1]) if r[1] else None,
            "ic_std": float(r[2]) if r[2] else None,
            "icir": float(r[3]) if r[3] else None,
            "ic_win_rate": float(r[4]) if r[4] else None,
            "sample_count": int(r[5]) if r[5] else 0,
        }

    # Quadrant performance
    qp_data = {}
    for r in qp_rows:
        q = int(r[0])
        avg_ret = float(r[1]) if r[1] else 0
        samples = int(r[2]) if r[2] else 0
        wins = int(r[3]) if r[3] else 0
        qp_data[q] = {
            "avg_return": round(avg_ret * 100, 2),
            "samples": samples,
            "win_rate": round(wins / samples * 100, 1) if samples > 0 else 0,
        }

    # ── ETF correlation (from close prices) ──
    if close_rows:
        cf = pd.DataFrame(close_rows, columns=["ts_code", "trade_date", "close"])
        cf["close"] = cf["close"].astype(float)
        cf["ret"] = cf.groupby("ts_code")["close"].pct_change()
        ret_pivot = cf.pivot(index="trade_date", columns="ts_code", values="ret").dropna()
        etf_corr = ret_pivot.corr()
    else:
        etf_corr = pd.DataFrame()

    # ── Market timing ──
    try:
        timing = compute_market_timing()
    except Exception as exc:
        logger.warning(f"Market timing failed: {exc}")
        timing = {"score": 0, "adjustment": 0, "regime_cn": "未知", "narrative": ""}

    # ── Select and rank candidates ──
    # Only Q1 (strong) and Q2 (lurk) are recommended
    candidates = [e for e in etf_data.values() if e["quadrant"] in (1, 2)]
    candidates.sort(key=lambda x: -x["factor"])

    if not candidates:
        return {
            "date": str(latest_date),
            "recommendations": [],
            "strategy": {
                "name": f"ETF多因子轮动策略 ({preset['label']})",
                "description": "当前无符合条件的ETF推荐",
                "holding_period": "",
            },
            "reasons": ["所有ETF均处于Q3/Q4象限，建议持币观望"],
            "risk_warning": ["市场无明显强势板块，暂停操作"],
        }

    # Correlation-based penalty
    def _correlation_penalty(code: str, selected: list) -> float:
        """Penalty multiplier based on max correlation with already-selected ETFs."""
        if not selected or code not in etf_corr.index:
            return 1.0
        max_corr = 0.0
        for sel in selected:
            if sel in etf_corr.columns and code in etf_corr.index:
                c = abs(etf_corr.loc[code, sel])
                if not np.isnan(c):
                    max_corr = max(max_corr, c)
        if max_corr > 0.7:
            return 0.3  # very high correlation → severe penalty
        elif max_corr > 0.6:
            return 0.5  # high correlation → significant penalty
        elif max_corr > 0.5:
            return 0.7  # moderate correlation → mild penalty
        return 1.0

    # Score each candidate
    scored = []
    selected_codes = []
    for c in candidates:
        # Base score from factor value
        base_score = abs(c["factor"])

        # Quadrant multiplier: Q1=1.0, Q2=0.7
        quad_mult = 1.0 if c["quadrant"] == 1 else 0.7

        # Correlation penalty
        corr_penalty = _correlation_penalty(c["code"], selected_codes)

        final_score = base_score * quad_mult * corr_penalty
        scored.append((c, final_score))
        selected_codes.append(c["code"])

    # Sort by final score
    scored.sort(key=lambda x: -x[1])

    # Take top N (max 5)
    MAX_RECOMMEND = 5
    top = scored[:MAX_RECOMMEND]
    total_score = max(sum(s for _, s in top), 1e-6)

    # ── Position sizing ──
    # Base budget: 100% (full allocation)
    # Adjusted by market timing
    base_budget = 1.0
    timing_adj = timing.get("adjustment", 0.0)
    total_budget = max(0.3, min(1.3, base_budget + timing_adj))

    # Q1 total weight: 60% of budget, Q2: 40%
    q1_count = sum(1 for c, _ in top if c["quadrant"] == 1)
    q2_count = sum(1 for c, _ in top if c["quadrant"] == 2)

    q1_budget = total_budget * 0.60
    q2_budget = total_budget * 0.40

    # Per-ETF cap: 25% absolute, or budget share + buffer
    max_single = min(0.25, total_budget / max(len(top), 1) + 0.05)

    recommendations = []
    allocated = 0.0
    for c, score in top:
        if c["quadrant"] == 1 and q1_count > 0:
            share = score / max(
                sum(s for cc, s in top if cc["quadrant"] == 1), 1e-6
            )
            raw_weight = q1_budget * share
        elif c["quadrant"] == 2 and q2_count > 0:
            share = score / max(
                sum(s for cc, s in top if cc["quadrant"] == 2), 1e-6
            )
            raw_weight = q2_budget * share
        else:
            raw_weight = total_budget / len(top)

        weight = min(raw_weight, max_single)
        allocated += weight

        # Strategy label
        if c["quadrant"] == 1:
            strategy_label = "Q1强势持有"
            strategy_desc = "资金流入 + 价格上涨，趋势共振，持有或加仓"
            holding = preset["forward_periods"][len(preset["forward_periods"]) // 2]
        else:
            strategy_label = "Q2潜伏布局"
            strategy_desc = "资金逆势流入，价格回调，分批建仓"
            holding = preset["forward_periods"][0]  # shortest holding

        # Flow direction display (raw flow, scaled to readable %)
        flow_pct = round(c["flow_raw"] * 100, 1) if abs(c["flow_raw"]) > 0.001 else 0.0
        momentum_str = f"{c['mom_raw']:+.2f}" if abs(c["mom_raw"]) > 0.001 else "0.00"

        recommendations.append({
            "name": c["name"],
            "code": c["code"],
            "strategy": strategy_label,
            "strategy_desc": strategy_desc,
            "flow_pct": flow_pct,
            "momentum": momentum_str,
            "factor_score": round(c["factor"], 4),
            "quadrant": c["quadrant"],
            "holding_days": f"{holding}个交易日",
            "position_ratio": f"{round(weight * 100, 1)}%",
            "confidence": "高" if c["quadrant"] == 1 else "中",
        })

    # ── Risk warnings (use optimal forward period's ICIR) ──
    risk_warnings = []
    best_h = optimal_h  # highest ICIR period
    if best_h in ic_summary and ic_summary[best_h]["icir"] is not None:
        icir_val = ic_summary[best_h]["icir"]
        if icir_val < 0.2:
            risk_warnings.append(
                f"⚠️ 当前因子ICIR={icir_val:.2f}，接近随机水平，建议减仓至50%以下"
            )
        elif icir_val < 0.3:
            risk_warnings.append(
                f"⚠️ 当前因子ICIR={icir_val:.2f}，预测力偏弱，仓位不宜过重"
            )
        elif icir_val < 0.5:
            risk_warnings.append(
                f"✓ 因子ICIR={icir_val:.2f}，具备可用预测力，可按常规仓位操作"
            )
        else:
            risk_warnings.append(
                f"✓ 因子ICIR={icir_val:.2f}，预测力强，可适当加大仓位"
            )

    if timing_adj < -0.1:
        risk_warnings.append(
            f"📉 大盘择时信号偏空（{timing.get('regime_cn','?')}），"
            f"总仓位已下调{abs(timing_adj)*100:.0f}%"
        )
    elif timing_adj > 0.1:
        risk_warnings.append(
            f"📈 大盘择时信号偏多（{timing.get('regime_cn','?')}），"
            f"总仓位已上调{timing_adj*100:.0f}%"
        )

    if q1_count > 0 and q2_count > 0:
        total_pct = q1_count + q2_count
        corr_high = any(
            _correlation_penalty(c["code"], []) < 0.7
            for c, _ in top
        )
        if corr_high:
            risk_warnings.append(
                "🔗 部分推荐ETF间相关性较高，已通过相关性惩罚控制集中度"
            )

    # ── Reasons ──
    reasons = [
        f"基于{preset['label']}预设（flow_lookback={preset['flow_lookback']}d, "
        f"mom_lookback={preset['mom_lookback']}d）的多因子模型",
    ]
    if best_h in ic_summary and ic_summary[best_h]["icir"] is not None:
        ic = ic_summary[best_h]
        reasons.append(
            f"最优H={best_h}天: IC均值={ic['ic_mean']:.4f}, ICIR={ic['icir']:.2f}, "
            f"近{ic['sample_count']}个交易日胜率{ic['ic_win_rate']:.1%}"
        )
    reasons.append("只推荐Q1（强势）+ Q2（潜伏）象限ETF，剔除Q3/Q4高风险品种")
    reasons.append(
        f"风险预算：单ETF≤{max_single*100:.0f}%，Q1:Q2={q1_budget/total_budget*100:.0f}:{q2_budget/total_budget*100:.0f}"
    )
    if abs(timing_adj) > 0.05:
        reasons.append(f"大盘择时信号：{timing.get('narrative','')}")
    reasons.append("建议设置止损：单ETF亏损达-5%或跌破20日均线时减仓")

    # ── Stats ──
    stats = {}
    for q in [1, 2]:
        if q in qp_data:
            d = qp_data[q]
            stats[f"q{q}"] = {
                "win_rate": d["win_rate"],
                "avg_return": d["avg_return"],
                "samples": d["samples"],
            }

    # Strategy description
    strategy_name = f"ETF多因子轮动策略 ({preset['label']})"
    holding_period = f"{preset['forward_periods'][len(preset['forward_periods'])//2]}个交易日中期持有"
    strategy_desc = (
        f"{preset['description']}。"
        f"大盘信号：{timing.get('regime_cn','中性')}（择时调整{timing_adj*100:+.0f}%）。"
    )

    # Top-level IC stats from optimal period
    best_ic = ic_summary.get(best_h, {})
    top_ic_mean = best_ic.get("ic_mean")
    top_icir = best_ic.get("icir")
    top_ic_win_rate = best_ic.get("ic_win_rate")

    return {
        "date": str(latest_date),
        "strategy": {
            "name": strategy_name,
            "description": strategy_desc,
            "holding_period": holding_period,
        },
        "ic_mean": top_ic_mean,
        "icir": top_icir,
        "ic_win_rate": top_ic_win_rate,
        "reasons": reasons,
        "recommendations": recommendations,
        "risk_warning": risk_warnings,
        "stats": stats,
        "timing": {
            "score": timing.get("score", 0),
            "regime": timing.get("regime_cn", ""),
            "adjustment": timing.get("adjustment", 0),
            "narrative": timing.get("narrative", ""),
        },
    }
