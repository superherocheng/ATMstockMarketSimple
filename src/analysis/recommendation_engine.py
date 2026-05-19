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

        # Check if quality columns exist (V4)
        has_quality = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='factor_daily' AND column_name='z_quality'"
        )).fetchone() is not None

        # Check if efficiency columns exist (V5)
        has_efficiency = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='factor_daily' AND column_name='z_efficiency'"
        )).fetchone() is not None

        if has_rsrs and has_quality and has_efficiency:
            factor_rows = conn.execute(text("""
                SELECT etf_code, z_flow, z_mom, factor, quadrant, flow, mom,
                       rsrs, z_rsrs, f_quality, z_quality, intraday_eff, z_efficiency
                FROM factor_daily
                WHERE preset_id = :pid AND trade_date = :d
                ORDER BY factor DESC
            """), {"pid": preset_id, "d": latest_date}).fetchall()
        elif has_rsrs and has_quality:
            factor_rows = conn.execute(text("""
                SELECT etf_code, z_flow, z_mom, factor, quadrant, flow, mom,
                       rsrs, z_rsrs, f_quality, z_quality
                FROM factor_daily
                WHERE preset_id = :pid AND trade_date = :d
                ORDER BY factor DESC
            """), {"pid": preset_id, "d": latest_date}).fetchall()
        elif has_rsrs:
            factor_rows = conn.execute(text("""
                SELECT etf_code, z_flow, z_mom, factor, quadrant, flow, mom,
                       rsrs, z_rsrs
                FROM factor_daily
                WHERE preset_id = :pid AND trade_date = :d
                ORDER BY factor DESC
            """), {"pid": preset_id, "d": latest_date}).fetchall()
        elif has_quality:
            factor_rows = conn.execute(text("""
                SELECT etf_code, z_flow, z_mom, factor, quadrant, flow, mom,
                       f_quality, z_quality
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

        # ── 4a. Compute recent (rolling) ICIR for decay detection ──
        recent_ic_rows = conn.execute(text("""
            SELECT ic_value FROM ic_daily
            WHERE preset_id = :pid AND forward_days = :h
            ORDER BY trade_date DESC LIMIT 60
        """), {"pid": preset_id, "h": optimal_h}).fetchall()
        if len(recent_ic_rows) >= 20:
            _recent_ics = np.array([float(r[0]) for r in recent_ic_rows if r[0] is not None])
            if len(_recent_ics) >= 20:
                _recent_mean = float(_recent_ics.mean())
                _recent_std  = float(_recent_ics.std(ddof=1))
                recent_icir  = _recent_mean / _recent_std if _recent_std > 0 else None
                # Compute decay vs full-sample ICIR
                if best_icir > 0 and recent_icir is not None:
                    icir_decay_pct = max(0, (1 - recent_icir / best_icir) * 100)
                else:
                    icir_decay_pct = None
            else:
                recent_icir = None
                icir_decay_pct = None
        else:
            recent_icir = None
            icir_decay_pct = None

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
        entry = {
            "code": code,
            "name": sector_names.get(code, code),
            "z_flow": float(r[1]) if r[1] else 0,
            "z_mom": float(r[2]) if r[2] else 0,
            "factor": float(r[3]) if r[3] else 0,
            "quadrant": int(r[4]) if r[4] else 0,
            "flow_raw": float(r[5]) if r[5] else 0,
            "mom_raw": float(r[6]) if r[6] else 0,
        }
        # V4: financial quality factor columns
        entry["z_quality"] = 0.0
        entry["f_quality_raw"] = 0.0
        # V5: intraday efficiency columns
        entry["z_efficiency"] = 0.0
        entry["efficiency_raw"] = 0.0

        if has_rsrs and has_quality and has_efficiency and len(r) >= 13:
            entry["z_rsrs"] = float(r[8]) if r[8] else 0
            entry["f_quality_raw"] = float(r[9]) if r[9] else 0
            entry["z_quality"] = float(r[10]) if r[10] else 0
            entry["efficiency_raw"] = float(r[11]) if r[11] else 0
            entry["z_efficiency"] = float(r[12]) if r[12] else 0
        elif has_rsrs and has_quality and len(r) >= 11:
            entry["z_rsrs"] = float(r[8]) if r[8] else 0
            entry["f_quality_raw"] = float(r[9]) if r[9] else 0
            entry["z_quality"] = float(r[10]) if r[10] else 0
        elif has_rsrs and len(r) >= 9:
            entry["z_rsrs"] = float(r[8]) if r[8] else 0
        elif has_quality and len(r) >= 9:
            entry["z_quality"] = float(r[8]) if r[8] else 0
            entry["f_quality_raw"] = float(r[7]) if r[7] else 0
        else:
            entry["z_rsrs"] = 0
        etf_data[code] = entry

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
    # Standard: Q1 (strong) and Q2 (lurk) are always recommended.
    # RSRS override: Q3 (exit) ETFs with strong RSRS (z_rsrs > 0.3)
    #   and positive composite factor also enter the pool,
    #   because RSRS indicates structural support even when
    #   short-term flow/momentum are negative.
    # Q4 (risk) remains excluded — it's the highest-risk quadrant.
    candidates = []
    for e in etf_data.values():
        if e["code"] not in sector_names:
            continue
        if e["quadrant"] in (1, 2):
            candidates.append(e)
        elif e["quadrant"] == 3 and e.get("z_rsrs", 0) > 0.3 and e["factor"] > 0:
            candidates.append(e)
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
            "reasons": ["所有ETF均处于Q3/Q4象限且RSRS偏弱，建议持币观望"],
            "risk_warning": ["市场无明显强势板块且无强支撑信号，暂停操作"],
        }

    # ── Phase 1: Initial scoring (no correlation penalty) ──
    initial_scored = []
    for c in candidates:
        base_score = max(0, c["factor"])
        quad_mult = 1.0 if c["quadrant"] == 1 else 0.7
        initial_scored.append((c, base_score * quad_mult))

    # Sort by initial score descending
    initial_scored.sort(key=lambda x: -x[1])

    # Take a wider pool (top 10 or all if fewer)
    MAX_RECOMMEND = 5
    pool_size = min(len(initial_scored), MAX_RECOMMEND * 2)
    pool = initial_scored[:pool_size]

    # ── Phase 2: Within-pool pairwise correlation penalty ──
    # For each pair in the pool, if correlation > threshold,
    # the lower-ranked (lower initial score) ETF gets penalized.
    penalty_map = {c["code"]: 1.0 for c, _ in pool}

    for i in range(len(pool)):
        for j in range(i + 1, len(pool)):
            code_i = pool[i][0]["code"]
            code_j = pool[j][0]["code"]

            if code_i not in etf_corr.index or code_j not in etf_corr.columns:
                continue
            corr_val = abs(etf_corr.loc[code_i, code_j])
            if np.isnan(corr_val):
                continue

            if corr_val > 0.7:
                p = 0.3
            elif corr_val > 0.6:
                p = 0.5
            elif corr_val > 0.5:
                p = 0.7
            else:
                continue

            # Penalize the lower-ranked ETF (j > i, so lower initial score)
            penalty_map[code_j] = min(penalty_map[code_j], p)

    # Apply penalties and re-sort
    penalized_scored = []
    for c, score in pool:
        final_score = score * penalty_map[c["code"]]
        if final_score > 0:
            penalized_scored.append((c, final_score))

    # Sort by penalized score and take top N
    penalized_scored.sort(key=lambda x: -x[1])
    top = penalized_scored[:MAX_RECOMMEND]
    total_score = max(sum(s for _, s in top), 1e-6)

    # ── Position sizing ──
    # Proportional allocation: all candidates share total_budget by final_score.
    # Q2's 0.7x multiplier already penalizes it in the scoring stage,
    # so no separate Q1/Q2 budget split is needed.
    base_budget = 1.0
    timing_adj = timing.get("adjustment", 0.0)
    total_budget = max(0.3, min(1.3, base_budget + timing_adj))

    total_final_score = sum(s for _, s in top)
    if total_final_score <= 0:
        return {"error": "无有效因子信号", "recommendations": []}

    # Per-ETF cap: 25% absolute
    max_single = 0.25

    recommendations = []
    allocated = 0.0
    for c, score in top:
        share = score / total_final_score
        raw_weight = total_budget * share

        weight = min(raw_weight, max_single)
        allocated += weight

        # Strategy label
        if c["quadrant"] == 1:
            strategy_label = "Q1强势持有"
            strategy_desc = "资金流入 + 价格上涨，趋势共振，持有或加仓"
            holding = preset["forward_periods"][0]
        elif c["quadrant"] == 2:
            strategy_label = "Q2潜伏布局"
            strategy_desc = "资金逆势流入，价格回调，分批建仓"
            holding = preset["forward_periods"][0]
        else:
            # Q3 with RSRS override: structural support despite weak flow/momentum
            strategy_label = "Q3支撑博弈"
            strategy_desc = "RSRS支撑结构较强，资金与动量偏弱，试探性配置"
            holding = preset["forward_periods"][0]

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
            "z_quality": round(c["z_quality"], 4),
            "f_quality_raw": round(c["f_quality_raw"], 4),
            "z_efficiency": round(c["z_efficiency"], 4),
            "efficiency_raw": round(c["efficiency_raw"], 4),
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

    # ── Rolling ICIR decay warning ──
    if recent_icir is not None:
        if icir_decay_pct is not None and icir_decay_pct > 40:
            risk_warnings.append(
                f"📉 近60日滚动ICIR={recent_icir:.2f}，较全样ICIR({best_icir:.2f})衰减"
                f"{icir_decay_pct:.0f}%，因子预测力持续下降，建议谨慎操作"
            )
        elif icir_decay_pct is not None and icir_decay_pct > 20:
            risk_warnings.append(
                f"📉 近60日滚动ICIR={recent_icir:.2f}，较全样ICIR({best_icir:.2f})衰减"
                f"{icir_decay_pct:.0f}%，因子信号质量有所下滑"
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

    # Check pairwise correlations within the final top selection
    if len(top) >= 2:
        max_pair_corr = 0.0
        high_corr_pairs = []
        top_codes = [c["code"] for c, _ in top]
        for i in range(len(top_codes)):
            for j in range(i + 1, len(top_codes)):
                ci, cj = top_codes[i], top_codes[j]
                if ci in etf_corr.index and cj in etf_corr.columns:
                    cv = abs(etf_corr.loc[ci, cj])
                    if not np.isnan(cv):
                        max_pair_corr = max(max_pair_corr, cv)
                        if cv > 0.5:
                            high_corr_pairs.append((ci, cj, cv))
        if max_pair_corr > 0.5:
            risk_warnings.append(
                f"🔗 推荐ETF间相关性最高达{max_pair_corr:.2f}，"
                f"已通过相关性惩罚控制集中度"
            )

    # ── Reasons ──
    reasons = [
        f"基于{preset['label']}预设（flow_lookback={preset['flow_lookback']}d, "
        f"mom_lookback={preset['mom_lookback']}d）的四因子模型（RSRS+资金流+动量+财务质量）",
    ]
    if best_h in ic_summary and ic_summary[best_h]["icir"] is not None:
        ic = ic_summary[best_h]
        reasons.append(
            f"最优H={best_h}天: IC均值={ic['ic_mean']:.4f}, ICIR={ic['icir']:.2f}, "
            f"近{ic['sample_count']}个交易日胜率{ic['ic_win_rate']:.1%}"
        )
    reasons.append("主要推荐Q1（强势）+ Q2（潜伏）象限ETF；Q3（撤离）中RSRS>0.3的品种按信号强度纳入候选")
    reasons.append(
        "V4新增财务质量因子（F_Quality）：综合预期ROE、PB估值分位（反向）、盈利加速度三个子因子，"
        "基于行业成分股流通市值加权合成"
    )
    reasons.append(
        "V5新增日内效率因子（IntEff）：基于OHLC代理的日内价格方向性指标，"
        "衡量趋势流畅度。高IntEff=单边趋势强、噪音低；低IntEff=震荡折返多"
    )
    reasons.append(
        f"风险预算：单ETF≤{max_single*100:.0f}%，按因子分比例配仓"
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
    holding_period = f"{preset['forward_periods'][0]}个交易日中期持有"
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
