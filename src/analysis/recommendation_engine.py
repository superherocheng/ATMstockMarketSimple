"""Investment recommendation engine.

Generates structured investment recommendations by combining:
- Multi-factor model scores (from factor_daily)
- IC statistics (factor validity assessment)
- Market timing (CSI 500 regime signal)
- Cross-ETF correlation penalty
- Risk budgeting position sizing
- ICIR-gated holding strategy (4 modes: full/reduced/caution/hibernate)

Every recommendation includes confidence level, rationale, and risk warnings.
"""
import json
import logging
from datetime import datetime
from typing import List, Optional

import numpy as np
import pandas as pd
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Module-level cache for schema column detection (avoids 4 queries per call)
_SCHEMA_CACHE = None

# ── ICIR regime constants ──
_ICIR_HOLDING_PERIOD = 15
_ICIR_FULL = 0.50
_ICIR_REDUCED = 0.30
_ICIR_CAUTION = 0.20


def _get_icir_mode(recent_icir: float) -> dict:
    """Classify ICIR into operational regime.

    Returns: {mode, multiplier, label_cn, force_hold, desc}
    """
    if recent_icir is None:
        return {"mode": "caution", "multiplier": 0.5, "label_cn": "谨慎-数据不足",
                "force_hold": False, "desc": "Insufficient data, cautious mode"}
    if recent_icir >= _ICIR_FULL:
        return {"mode": "full", "multiplier": 1.0, "label_cn": "全力出击",
                "force_hold": True, "desc": f"ICIR={recent_icir:.2f} strong, full force"}
    if recent_icir >= _ICIR_REDUCED:
        return {"mode": "reduced", "multiplier": 0.7, "label_cn": "标准策略",
                "force_hold": True, "desc": f"ICIR={recent_icir:.2f} usable, reduced position"}
    if recent_icir >= _ICIR_CAUTION:
        return {"mode": "caution", "multiplier": 0.5, "label_cn": "谨慎模式",
                "force_hold": False, "desc": f"ICIR={recent_icir:.2f} weak, caution"}
    return {"mode": "hibernate", "multiplier": 0.0, "label_cn": "冬眠模式",
            "force_hold": False, "desc": f"ICIR={recent_icir:.2f} near random, hibernate"}


def _trading_days_between(preset_id: str, start_date: str, end_date: str) -> int:
    """Count trading days between two dates from factor_daily."""
    from src.core.db_manager_postgresql import get_conn
    conn = get_conn()
    try:
        row = conn.execute(text(
            "SELECT COUNT(*) FROM factor_daily "
            "WHERE preset_id = :pid AND trade_date > :s AND trade_date <= :e"
        ), {"pid": preset_id, "s": start_date, "e": end_date}).fetchone()
        return int(row[0]) if row else 0
    except Exception:
        return 0
    finally:
        conn.close()


def _load_holdings(preset_id: str) -> dict:
    """Load current holdings with entry dates from analysis_cache."""
    from src.core.db_manager_postgresql import get_conn
    conn = get_conn()
    try:
        row = conn.execute(text(
            "SELECT data_json FROM analysis_cache WHERE key = :key"
        ), {"key": f"holdings_{preset_id}"}).fetchone()
        if row and row[0]:
            data = json.loads(row[0])
            if isinstance(data, dict):
                return data.get("holdings", {})
        return {}
    except Exception as exc:
        logger.debug(f"Could not load holdings: {exc}")
        return {}
    finally:
        conn.close()


def _save_holdings(preset_id: str, recommendations: list, latest_date: str):
    """Save current holdings (code + entry_date) to analysis_cache."""
    from sqlalchemy import text as sa_text
    from src.core.db_manager_postgresql import get_conn
    prev_holdings = _load_holdings(preset_id)
    new_holdings = {}
    for r in recommendations:
        code = r["code"]
        if code in prev_holdings:
            new_holdings[code] = prev_holdings[code]
        else:
            new_holdings[code] = {"entry_date": latest_date, "position": r.get("position_ratio", 0)}
    payload = {"date": latest_date, "holdings": new_holdings}
    conn = get_conn()
    try:
        existing = conn.execute(sa_text(
            "SELECT 1 FROM analysis_cache WHERE key = :key"
        ), {"key": f"holdings_{preset_id}"}).fetchone()
        if existing:
            conn.execute(sa_text(
                "UPDATE analysis_cache SET data_json = :data, updated_at = :now WHERE key = :key"
            ), {"data": json.dumps(payload, ensure_ascii=False), "now": str(datetime.now()),
                "key": f"holdings_{preset_id}"})
        else:
            conn.execute(sa_text(
                "INSERT INTO analysis_cache (key, data_json, updated_at) VALUES (:key, :data, :now)"
            ), {"data": json.dumps(payload, ensure_ascii=False), "now": str(datetime.now()),
                "key": f"holdings_{preset_id}"})
        conn.commit()
    except Exception as exc:
        logger.warning(f"Could not save holdings: {exc}")
    finally:
        conn.close()


def _get_conn():
    from src.core.db_manager_postgresql import get_conn
    return get_conn()


def _safe_dict(d):
    from src.core.db_manager_postgresql import safe_dict
    return safe_dict(d)


def _detect_factor_columns(conn):
    """Check which optional columns exist in factor_daily (cached after first call)."""
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE
    has_rsrs = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='factor_daily' AND column_name='rsrs'"
    )).fetchone() is not None
    has_quality = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='factor_daily' AND column_name='z_quality'"
    )).fetchone() is not None
    has_efficiency = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='factor_daily' AND column_name='z_efficiency'"
    )).fetchone() is not None
    has_rsi = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='factor_daily' AND column_name='z_rsi_momentum'"
    )).fetchone() is not None
    _SCHEMA_CACHE = (has_rsrs, has_quality, has_efficiency, has_rsi)
    return _SCHEMA_CACHE


def build_investment_recommendation(preset_id: str = "short",
                                    existing_positions: Optional[List[str]] = None) -> dict:
    """Generate a professional investment recommendation report.

    Args:
        preset_id: Factor preset to use ("short", "medium", "long")
        existing_positions: List of ETF codes currently held. If provided,
                            candidates highly correlated (>0.6) with any
                            existing position will have their score penalized
                            by 0.5 to reduce concentration risk.

    Returns:
        dict matching the investment_recommendation.html frontend schema.
    """
    from src.analysis.presets import get_preset
    from src.analysis.market_timing import compute_market_timing
    from config.config import SECTOR_ETF

    preset = get_preset(preset_id)
    conn = _get_conn()
    # ICIR mode defaults (overridden inside try block when DB data available)
    icir_mode = _get_icir_mode(None)
    mode_multiplier = icir_mode["multiplier"]
    mode_force_hold = icir_mode["force_hold"]
    holding_days = {}
    str_latest_date = ""
    try:
        # ── 1. Get latest factor date ──
        date_row = conn.execute(text("""
            SELECT MAX(trade_date) FROM factor_daily WHERE preset_id = :pid
        """), {"pid": preset_id}).fetchone()
        if not date_row or not date_row[0]:
            return {"error": "No factor data available. Please run factor calculation first.", "recommendations": []}
        latest_date = date_row[0]

        # ── 2. Get all ETFs' latest factor values ──
        # Check which optional columns exist (cached after first call)
        has_rsrs, has_quality, has_efficiency, has_rsi = _detect_factor_columns(conn)

        if has_rsrs and has_quality and has_efficiency and has_rsi:
            factor_rows = conn.execute(text("""
                SELECT etf_code, z_flow, z_mom, factor, quadrant, flow, mom,
                       rsrs, z_rsrs, f_quality, z_quality, intraday_eff, z_efficiency,
                       rsi_momentum, z_rsi_momentum
                FROM factor_daily
                WHERE preset_id = :pid AND trade_date = :d
                ORDER BY factor DESC
            """), {"pid": preset_id, "d": latest_date}).fetchall()
        elif has_rsrs and has_quality and has_efficiency:
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

        # ── 4b. ICIR regime: determine strategy mode ──
        icir_mode = _get_icir_mode(recent_icir)
        mode_multiplier = icir_mode["multiplier"]
        mode_force_hold = icir_mode["force_hold"]

        # ── 4c. Load existing holdings for holding-day tracking ──
        str_latest_date = str(latest_date)
        existing_holdings = _load_holdings(preset_id)
        holding_days = {}
        for code, info in existing_holdings.items():
            entry_date = info.get("entry_date", "")
            if entry_date:
                days = _trading_days_between(preset_id, entry_date, str_latest_date)
                holding_days[code] = {"days_held": days, "entry_date": entry_date}
            else:
                holding_days[code] = {"days_held": 0, "entry_date": str_latest_date}

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
              AND trade_date >= (SELECT MAX(trade_date) - INTERVAL '180 days' FROM sector_etf_daily)
            ORDER BY ts_code, trade_date
        """), {"pid": preset_id, "d": latest_date}).fetchall()

    finally:
        conn.close()

    if not factor_rows:
        return {"error": "No factor data available", "recommendations": []}

    # ── Build data structures ──
    sector_names = dict(SECTOR_ETF)

    def _safe_float(val):
        """Convert DB value to float, returning None for missing/NaN instead of 0."""
        if val is None or val is pd.NA:
            return None
        try:
            f = float(val)
            if pd.isna(f):
                return None
            return f
        except (ValueError, TypeError):
            return None

    def _safe_int(val):
        """Convert DB value to int, returning None for missing."""
        if val is None or val is pd.NA:
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    # ETF factor data
    etf_data = {}
    for r in factor_rows:
        code = r[0]
        entry = {
            "code": code,
            "name": sector_names.get(code, code),
            "z_flow": _safe_float(r[1]) or 0,
            "z_mom": _safe_float(r[2]) or 0,
            "factor": _safe_float(r[3]) or 0,
            "quadrant": _safe_int(r[4]) or 0,
            "flow_raw": _safe_float(r[5]) or 0,
            "mom_raw": _safe_float(r[6]) or 0,
        }
        # Track which critical factors are missing (None) for confidence penalty
        entry["_missing_factors"] = []

        # V4: financial quality factor columns
        entry["z_quality"] = 0.0
        entry["f_quality_raw"] = 0.0
        # V5: intraday efficiency columns
        entry["z_efficiency"] = 0.0
        entry["efficiency_raw"] = 0.0
        # V6: RSI momentum columns
        entry["z_rsi_momentum"] = 0.0
        entry["rsi_momentum_raw"] = 0.0

        if has_rsrs and has_quality and has_efficiency and has_rsi and len(r) >= 15:
            entry["z_rsrs"] = _safe_float(r[8]) or 0
            entry["f_quality_raw"] = _safe_float(r[9]) or 0
            entry["z_quality"] = _safe_float(r[10]) or 0
            entry["efficiency_raw"] = _safe_float(r[11]) or 0
            entry["z_efficiency"] = _safe_float(r[12]) or 0
            entry["rsi_momentum_raw"] = _safe_float(r[13]) or 0
            entry["z_rsi_momentum"] = _safe_float(r[14]) or 0
        elif has_rsrs and has_quality and has_efficiency and len(r) >= 13:
            entry["z_rsrs"] = _safe_float(r[8]) or 0
            entry["f_quality_raw"] = _safe_float(r[9]) or 0
            entry["z_quality"] = _safe_float(r[10]) or 0
            entry["efficiency_raw"] = _safe_float(r[11]) or 0
            entry["z_efficiency"] = _safe_float(r[12]) or 0
        elif has_rsrs and has_quality and len(r) >= 11:
            entry["z_rsrs"] = _safe_float(r[8]) or 0
            entry["f_quality_raw"] = _safe_float(r[9]) or 0
            entry["z_quality"] = _safe_float(r[10]) or 0
        elif has_rsrs and len(r) >= 9:
            entry["z_rsrs"] = _safe_float(r[8]) or 0
        elif has_quality and len(r) >= 9:
            entry["z_quality"] = _safe_float(r[8]) or 0
            entry["f_quality_raw"] = _safe_float(r[7]) or 0
        else:
            entry["z_rsrs"] = 0

        # Data completeness check: flag missing critical factors
        for fname, idx in [("z_flow", 1), ("z_mom", 2), ("factor", 3)]:
            if _safe_float(r[idx]) is None:
                entry["_missing_factors"].append(fname)
        if has_rsrs and len(r) >= 9 and _safe_float(r[8]) is None:
            entry["_missing_factors"].append("z_rsrs")
        if has_quality and _safe_float(entry.get("z_quality")) is None:
            entry["_missing_factors"].append("z_quality")

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
        timing = {"score": 0, "adjustment": 0, "regime_cn": "Unknown", "narrative": ""}

    # ── Data coverage stats ──
    # Measure BOTH row coverage AND usable-factor coverage. A factor_daily row may
    # exist for the latest date with factor=NaN (today's price/flow data only
    # partially arrived), which makes the cross-sectional snapshot unusable even
    # though the row count looks healthy. The app reads NaN via pandas, so we use
    # _safe_float (which treats NaN/None as None) rather than a SQL COUNT — note
    # PostgreSQL evaluates NaN = NaN as TRUE, so a SQL COUNT(factor) would wrongly
    # count NaN rows as valid.
    total_tracked_etfs = len(sector_names)
    latest_etf_count = 0       # tracked ETFs with a row on the latest date
    factor_valid_count = 0     # tracked ETFs with a usable (non-NaN) factor
    for r in factor_rows:
        if r[0] not in sector_names:
            continue
        latest_etf_count += 1
        if _safe_float(r[3]) is not None:
            factor_valid_count += 1

    # If the latest day's cross-section is incomplete, do NOT emit investment advice.
    if (latest_etf_count < total_tracked_etfs * 0.5
            or factor_valid_count < total_tracked_etfs * 0.5):
        logger.warning(
            f"Latest-day cross-section incomplete for {latest_date}: "
            f"{factor_valid_count}/{total_tracked_etfs} ETFs have usable factors "
            f"({latest_etf_count} rows present). Skipping recommendation."
        )
        return {
            "error": "data_incomplete",
            "data_incomplete": True,
            "date": str(latest_date),
            "recommendations": [],
            "message": (
                f"最新交易日 {latest_date} 的截面数据尚未齐全"
                f"（仅 {factor_valid_count}/{total_tracked_etfs} 只ETF有有效因子），"
                f"暂不生成投资建议，待数据更新后自动恢复。"
            ),
            "strategy": {
                "name": f"ETF Multi-Factor Rotation Strategy ({preset['label']})",
                "description": "最新交易日截面数据不完整，等待数据更新后自动恢复",
                "holding_period": "",
            },
            "reasons": ["最新交易日截面数据不完整，因子计算尚未完成，请等待数据更新"],
            "risk_warning": [
                f"⚠️ 最新交易日截面数据不完整（{factor_valid_count}/{total_tracked_etfs} "
                f"只ETF有有效因子），当前建议不适用"
            ],
            "stats": {},
        }

    # ── Select and rank candidates ──
    # Standard: Q1 (strong) and Q2 (lurk) are always recommended.
    # RSRS override: Q3 (exit) ETFs with strong RSRS (z_rsrs > 0.3)
    #   and positive composite factor also enter the pool,
    #   because RSRS indicates structural support even when
    #   short-term flow/momentum are negative.
    # Q4 (risk) remains excluded — it's the highest-risk quadrant.
    # Fallback: if fewer than MIN_RECOMMEND candidates pass strict
    #   filtering, relax Q3/Q4 thresholds to ensure diversification.

    MIN_RECOMMEND = 3

    candidates = []
    for e in etf_data.values():
        if e["code"] not in sector_names:
            continue
        if e["quadrant"] in (1, 2):
            candidates.append(e)
        elif e["quadrant"] == 3 and e.get("z_rsrs", 0) > 0.3 and e["factor"] > 0:
            candidates.append(e)
    candidates.sort(key=lambda x: -x["factor"])

    # ── Fallback: relax thresholds when strict candidates are too few ──
    if len(candidates) < MIN_RECOMMEND:
        existing_codes = {c["code"] for c in candidates}
        for e in etf_data.values():
            if e["code"] not in sector_names or e["code"] in existing_codes:
                continue
            # Relaxed Q3: any positive RSRS
            if e["quadrant"] == 3 and e.get("z_rsrs", 0) > 0 and e["factor"] > 0:
                candidates.append(e)
            # Relaxed Q4: strong RSRS can compensate for risk quadrant
            elif e["quadrant"] == 4 and e.get("z_rsrs", 0) > 0.3 and e["factor"] > 0:
                candidates.append(e)
        candidates.sort(key=lambda x: -x["factor"])

    # ── Force-hold: retain existing positions that haven't completed H days ──
    if mode_force_hold and etf_data and holding_days:
        candidate_codes = {c["code"] for c in candidates}
        for code, hd in holding_days.items():
            if hd["days_held"] >= _ICIR_HOLDING_PERIOD:
                continue
            if code not in etf_data or code in candidate_codes:
                continue
            e = etf_data[code]
            if e["quadrant"] == 4 and e.get("z_rsrs", 0) <= 0.3:
                continue
            if e["factor"] <= 0:
                continue
            e["_force_held"] = True
            e["_held_days"] = hd["days_held"]
            candidates.append(e)
        if any(c.get("_force_held") for c in candidates):
            candidates.sort(key=lambda x: -x["factor"])
            held = [c["code"] for c in candidates if c.get("_force_held")]
            logger.info(f"Force-held {len(held)} ETFs: {','.join(held)} (mode={icir_mode['mode']})")

    if not candidates:
        return {
            "date": str(latest_date),
            "recommendations": [],
            "strategy": {
                "name": f"ETF Multi-Factor Rotation Strategy ({preset['label']})",
                "description": "No ETFs currently meet the selection criteria",
                "holding_period": "",
            },
            "reasons": ["All ETFs are in Q3/Q4 quadrants with weak RSRS. Consider holding cash."],
            "risk_warning": ["No strong sector momentum or support signals. Trading paused."],
        }

    # ── Phase 1: Initial scoring (no correlation penalty) ──
    initial_scored = []
    for c in candidates:
        # Q1/Q2 always get a minimum score to survive the final_score > 0 check
        if c["quadrant"] in (1, 2):
            base_score = max(0.05, c["factor"])
        else:
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

    # ── Phase 2b: Existing positions correlation penalty ──
    # If the user already holds some ETFs, penalize candidates that are
    # highly correlated with those positions to reduce concentration risk.
    if existing_positions:
        for c, _ in pool:
            code = c["code"]
            for held_code in existing_positions:
                if code == held_code:
                    continue
                if code not in etf_corr.index or held_code not in etf_corr.columns:
                    continue
                corr_val = abs(etf_corr.loc[code, held_code])
                if np.isnan(corr_val):
                    continue
                if corr_val > 0.6:
                    # Apply 0.5 penalty when correlation exceeds threshold
                    penalty_map[code] = min(penalty_map[code], 0.5)
                    break

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
    # ICIR mode multiplier: reduces position when signal is weak
    mode_budget = base_budget * mode_multiplier
    total_budget = max(0.0, min(1.3, mode_budget + timing_adj))

    # ── Hibernate mode: don't select any ETFs ──
    if total_budget <= 0:
        return {
            "date": str(latest_date),
            "recommendations": [],
            "strategy": {
                "name": f"ETF Multi-Factor Rotation Strategy ({preset['label']})",
                "description": f"ICIR门控: {icir_mode['label_cn']} — {icir_mode['desc']}. 因子预测力不足，暂停选股。",
                "holding_period": "",
            },
            "reasons": [f"ICIR={recent_icir:.2f}, factor near random level. Holding cash recommended."],
            "risk_warning": [f"⏸ ICIR={recent_icir:.2f}，因子信号接近随机。策略进入{icir_mode['label_cn']}，不推荐ETF。"],
        }

    total_final_score = sum(s for _, s in top)
    if total_final_score <= 0:
        return {"error": "No valid factor signals", "recommendations": []}

    # Per-ETF cap: 25% absolute, with redistribution of capped excess
    max_single = 0.25

    # First pass: compute raw weights and identify capped ETFs
    raw_weights = []
    for c, score in top:
        share = score / total_final_score
        raw_weights.append(total_budget * share)

    # Apply cap and collect excess
    capped_weights = []
    excess = 0.0
    capped_indices = set()
    for i, w in enumerate(raw_weights):
        if w > max_single:
            excess += w - max_single
            capped_weights.append(max_single)
            capped_indices.add(i)
        else:
            capped_weights.append(w)

    # Redistribute excess proportionally among uncapped ETFs
    if excess > 0 and len(capped_indices) < len(capped_weights):
        uncapped_total = sum(capped_weights[i] for i in range(len(capped_weights)) if i not in capped_indices)
        if uncapped_total > 0:
            for i in range(len(capped_weights)):
                if i not in capped_indices:
                    redistribution = excess * (capped_weights[i] / uncapped_total)
                    capped_weights[i] = min(capped_weights[i] + redistribution, max_single)

    recommendations = []
    allocated = 0.0
    for idx, (c, score) in enumerate(top):
        weight = capped_weights[idx]
        allocated += weight

        # Strategy label
        if c["quadrant"] == 1:
            strategy_label = "Q1 Strong Hold"
            strategy_desc = "Capital inflow + price uptrend. Trend alignment. Hold or add."
            holding = preset["forward_periods"][0]
        elif c["quadrant"] == 2:
            strategy_label = "Q2 Accumulate"
            strategy_desc = "Contrarian capital inflow with price pullback. Scale in gradually."
            holding = preset["forward_periods"][0]
        else:
            # Q3 with RSRS override: structural support despite weak flow/momentum
            strategy_label = "Q3 RSRS Support"
            strategy_desc = "Strong RSRS structural support despite weak flow/momentum. Exploratory allocation."
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
            "holding_days": f"{holding} trading days",
            "days_held": c.get("_held_days", 0),
            "holding_days_remaining": max(0, _ICIR_HOLDING_PERIOD - c.get("_held_days", 0)),
            "force_held": c.get("_force_held", False),
            "position_ratio": round(weight, 4),
            "confidence": ("High" if c["quadrant"] == 1 else "Mid") if not c.get("_missing_factors") else "Low",
            "z_quality": round(c["z_quality"], 4),
            "f_quality_raw": round(c["f_quality_raw"], 4),
            "z_efficiency": round(c["z_efficiency"], 4),
            "efficiency_raw": round(c["efficiency_raw"], 4),
            "z_rsi_momentum": round(c["z_rsi_momentum"], 4),
            "rsi_momentum_raw": round(c["rsi_momentum_raw"], 4),
        })

    # ── Risk warnings (use optimal forward period's ICIR) ──
    risk_warnings = []
    best_h = optimal_h  # highest ICIR period

    # ICIR regime warning
    if icir_mode["mode"] == "full":
        risk_warnings.append(
            f"✅ ICIR门控: {icir_mode['label_cn']} — 近期ICIR={recent_icir:.2f}，信号强劲。"
            f"强制持仓{_ICIR_HOLDING_PERIOD}日，锁定完整预期收益。"
        )
    elif icir_mode["mode"] == "reduced":
        risk_warnings.append(
            f"✅ ICIR门控: {icir_mode['label_cn']} — 近期ICIR={recent_icir:.2f}，信号可用。"
            f"强制持仓{_ICIR_HOLDING_PERIOD}日，仓位降至{icir_mode['multiplier']*100:.0f}%。"
        )
    elif icir_mode["mode"] == "caution":
        risk_warnings.append(
            f"⚠️ ICIR门控: {icir_mode['label_cn']} — 近期ICIR={recent_icir:.2f}，信号较弱。"
            f"不强制持有，仓位仅{icir_mode['multiplier']*100:.0f}%。"
        )
    elif icir_mode["mode"] == "hibernate":
        risk_warnings.append(
            f"⏸ ICIR门控: {icir_mode['label_cn']} — 近期ICIR={recent_icir:.2f}，近乎随机。暂停选股。"
        )
    if best_h in ic_summary and ic_summary[best_h]["icir"] is not None:
        icir_val = ic_summary[best_h]["icir"]
        if icir_val < 0.2:
            risk_warnings.append(
                f"⚠️ Current factor ICIR={icir_val:.2f}, near random level. Consider reducing positions to under 50%."
            )
        elif icir_val < 0.3:
            risk_warnings.append(
                f"⚠️ Current factor ICIR={icir_val:.2f}, weak predictive power. Avoid heavy positioning."
            )
        elif icir_val < 0.5:
            risk_warnings.append(
                f"✓ Factor ICIR={icir_val:.2f}, usable predictive power. Standard position sizing is appropriate."
            )
        else:
            risk_warnings.append(
                f"✓ Factor ICIR={icir_val:.2f}, strong predictive power. May consider larger positions."
            )

    # ── Rolling ICIR decay warning ──
    if recent_icir is not None:
        if icir_decay_pct is not None and icir_decay_pct > 40:
            risk_warnings.append(
                f"📉 60-day rolling ICIR={recent_icir:.2f}, decayed {icir_decay_pct:.0f}% "
                f"vs full-sample ({best_icir:.2f}). Factor predictive power declining. Exercise caution."
            )
        elif icir_decay_pct is not None and icir_decay_pct > 20:
            risk_warnings.append(
                f"📉 60-day rolling ICIR={recent_icir:.2f}, decayed {icir_decay_pct:.0f}% "
                f"vs full-sample ({best_icir:.2f}). Factor signal quality softening."
            )

    if timing_adj < -0.1:
        risk_warnings.append(
            f"📉 Market timing signal bearish ({timing.get('regime_cn','?')}). "
            f"Total position reduced by {abs(timing_adj)*100:.0f}%."
        )
    elif timing_adj > 0.1:
        risk_warnings.append(
            f"📈 Market timing signal bullish ({timing.get('regime_cn','?')}). "
            f"Total position increased by {timing_adj*100:.0f}%."
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
                f"🔗 Max pairwise correlation among recommended ETFs is {max_pair_corr:.2f}. "
                f"Concentration controlled via correlation penalty."
            )

    # ── Data coverage warning ──
    if latest_etf_count < total_tracked_etfs:
        risk_warnings.append(
            f"ℹ️ ETF data coverage: only {latest_etf_count}/{total_tracked_etfs} "
            f"sector ETFs have latest factor data (remaining ETFs have delayed share data). "
            f"Rankings are for reference only."
        )

    # ── Reasons ──
    reasons = [
        f"Based on {preset['label']} preset — 6-factor model (RSRS + Capital Flow + Momentum + RSI Momentum) "
        f"on {total_tracked_etfs} sector ETFs, H={preset['forward_periods'][0]}d forward period",
    ]
    if best_h in ic_summary and ic_summary[best_h]["icir"] is not None:
        ic = ic_summary[best_h]
        reasons.append(
            f"Optimal forward period H={best_h}d: IC mean={ic['ic_mean']:.4f}, ICIR={ic['icir']:.2f}, "
            f"win rate over {ic['sample_count']} trading days: {ic['ic_win_rate']:.1%}"
        )
    reasons.append("Primary recommendations from Q1 (Strong) + Q2 (Lurk) quadrants; Q3 (Exit) ETFs with RSRS>0.3 included by signal strength.")
    reasons.append(
        f"Portfolio stickiness={preset.get('portfolio_stickiness', 0)}: favors holding continuity to reduce turnover. "
        f"Risk budget: single ETF ≤ {max_single*100:.0f}%, allocated by factor score proportion."
    )
    if abs(timing_adj) > 0.05:
        reasons.append(f"Market timing signal: {timing.get('narrative','')}")
    reasons.append("Stop-loss recommended: reduce position when single ETF loss reaches -5% or breaks below 20-day MA.")

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
    strategy_name = f"ETF Multi-Factor Rotation Strategy ({preset['label']})"
    holding_period = f"{preset['forward_periods'][0]}-day medium-term holding"
    strategy_desc = (
        f"{preset['description']}. "
        f"V8权重: RSRS(28%) Mom(32%) Flow(20%) RSI(14%) Efficiency(6%). "
        f"ICIR门控: {icir_mode['label_cn']} (近期ICIR={recent_icir:.2f}). "
        f"Market signal: {timing.get('regime_cn','Neutral')} (timing adjustment {timing_adj*100:+.0f}%)."
    )

    # Top-level IC stats from optimal period
    best_ic = ic_summary.get(best_h, {})
    top_ic_mean = best_ic.get("ic_mean")
    top_icir = best_ic.get("icir")
    top_ic_win_rate = best_ic.get("ic_win_rate")

    # Save holdings for next call's holding-day tracking
    if recommendations:
        _save_holdings(preset_id, recommendations, str_latest_date)

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
        "strategy_mode": icir_mode,
        "reasons": reasons,
        "recommendations": recommendations,
        "risk_warning": risk_warnings,
        "stats": stats,
        "etf_data_coverage": {
            "with_data": latest_etf_count,
            "tracked_total": total_tracked_etfs,
            "pct": round(latest_etf_count / total_tracked_etfs * 100, 0) if total_tracked_etfs > 0 else 0,
        },
        "weight_allocation": {
            "quality_active": has_quality,
            "efficiency_active": True,
            "rsi_momentum_active": has_rsi,
        },
        "timing": {
            "score": timing.get("score", 0),
            "regime": timing.get("regime_cn", ""),
            "adjustment": timing.get("adjustment", 0),
            "narrative": timing.get("narrative", ""),
        },
    }


# ════════════════════════════════════════════════════════════
#  变更追踪：调仓买入 / 调整权重 / 持有
# ════════════════════════════════════════════════════════════

_PREV_WEIGHT_THRESHOLD = 0.01


def _load_prev_recommendation(preset_id: str) -> list:
    """Load previous day's recommendation from analysis_cache."""
    from src.core.db_manager_postgresql import get_conn
    conn = get_conn()
    try:
        row = conn.execute(text(
            "SELECT data_json FROM analysis_cache WHERE key = :key"
        ), {"key": f"prev_rec_{preset_id}"}).fetchone()
        if row and row[0]:
            data = json.loads(row[0])
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "recommendations" in data:
                return data["recommendations"]
        return []
    except Exception as exc:
        logger.debug(f"Could not load prev recommendation: {exc}")
        return []
    finally:
        conn.close()


def _save_prev_recommendation(preset_id: str, recommendations: list, latest_date: str):
    """Save current recommendation to analysis_cache for next comparison."""
    from sqlalchemy import text as sa_text
    from src.core.db_manager_postgresql import get_conn
    snapshot = [
        {"code": r["code"], "position": r.get("position_ratio", 0)}
        for r in recommendations
    ]
    payload = {"date": latest_date, "recommendations": snapshot}
    conn = get_conn()
    try:
        existing = conn.execute(sa_text(
            "SELECT 1 FROM analysis_cache WHERE key = :key"
        ), {"key": f"prev_rec_{preset_id}"}).fetchone()
        if existing:
            conn.execute(sa_text(
                "UPDATE analysis_cache SET data_json = :data, updated_at = :now WHERE key = :key"
            ), {"data": json.dumps(payload, ensure_ascii=False), "now": str(datetime.now()),
                "key": f"prev_rec_{preset_id}"})
        else:
            conn.execute(sa_text(
                "INSERT INTO analysis_cache (key, data_json, updated_at) VALUES (:key, :data, :now)"
            ), {"data": json.dumps(payload, ensure_ascii=False), "now": str(datetime.now()),
                "key": f"prev_rec_{preset_id}"})
        conn.commit()
    except Exception as exc:
        logger.warning(f"Could not save prev recommendation: {exc}")
    finally:
        conn.close()


def _compute_change_action(rec: dict, prev_map: dict) -> str:
    """Determine change action: 'new'(调仓买入), 'adjust'(调整权重), 'hold'(持有)."""
    code = rec["code"]
    new_weight = rec.get("position_ratio", 0)
    prev = prev_map.get(code)
    if prev is None:
        return "new"
    prev_weight = prev.get("position", 0)
    if abs(new_weight - prev_weight) >= _PREV_WEIGHT_THRESHOLD:
        return "adjust"
    return "hold"


def enrich_change_actions(preset_id: str, recommendations: list, latest_date: str) -> list:
    """Add change_action field by comparing with previous day's recommendations.

    Called from API endpoint AFTER cache lookup so actions are always fresh.
    """
    try:
        prev_recs = _load_prev_recommendation(preset_id)
        prev_map = {}
        for p in prev_recs:
            prev_map[p["code"]] = p
        for rec in recommendations:
            rec["change_action"] = _compute_change_action(rec, prev_map)
        _save_prev_recommendation(preset_id, recommendations, latest_date)
    except Exception as exc:
        logger.warning(f"Could not enrich change_actions: {exc}")
        for rec in recommendations:
            rec["change_action"] = "hold"
    return recommendations
