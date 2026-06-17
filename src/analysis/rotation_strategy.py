"""ETF 行业轮动策略引擎 (CITIC Futures 框架的具体化实现).

实现 NEW策略.md 描述的中信期货 ETF 行业轮动策略，作为「个人投资参考」实时信号看板。
策略以两个核心指标驱动：
  ① 市场情绪指标  (market sentiment) —— 总体市场温度
  ② 行业轮动强度  (rotation strength) —— 资金在行业间切换的速度
两者构成双轴决策矩阵 → 决定总仓位；再用「高景气进攻 + 反转预期防守」双层结构构建组合，
并以相关性约束控制分散度。

数据完全来自现有数据库（不新增任何抓取）：
  - 情绪·趋势分：index_etf_daily 中的 3 只宽基 ETF (沪深300/中证500/中证1000)
  - 情绪·宽度分 + 轮动强度 + 组合相关性：sector_etf_daily 中的行业 ETF
  - 进攻/防守选股：factor_daily (preset_id='optimized') 的象限与因子分

复用：rsi_factor.compute_rsi、market_timing._compute_cross_sectional_dispersion、
      recommendation_engine 的相关性惩罚 + 25% 上限再分配 + 覆盖度护栏模式。
不引入 backtest.py（纯实时信号看板，不做历史回测）。
"""
import logging
from datetime import datetime
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
from sqlalchemy import text, bindparam

logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────────────
# 情绪·趋势分基准：3 只宽基 ETF（沪深300 / 中证500 / 中证1000）
BROAD_INDEX_CODES = ["510300.SH", "510500.SH", "512100.SH"]

MA60_WINDOW = 60
MA20_WINDOW = 20
RET20_WINDOW = 20

HISTORY_DAYS = 120          # 历史序列图取最近 120 个交易日
SECTOR_SERIES_DAYS = 60     # 轮动强度序列图取最近 60 个交易日

ROTATION_RET_WINDOW = 5     # 轮动强度用 5 日收益排名
ROTATION_RANK_WINDOW = 20   # 排名变化做 20 日滚动均值

ATTACK_BUDGET_SHARE = 0.70  # 进攻层占总仓位的比例
DEFENSE_BUDGET_SHARE = 0.30
MAX_ATTACK = 4
MAX_DEFENSE = 2
MAX_SINGLE_ETF = 0.25       # 单只 ETF 占总仓位的上限（照搬 rec_engine）
CORR_PENALTY = {0.7: 0.3, 0.6: 0.5, 0.5: 0.7}  # 相关性惩罚倍数

# 情绪区间阈值
SENTIMENT_HIGH = 0.5
SENTIMENT_LOW = -0.5
# 轮动强度百分位阈值
ROTATION_STRONG = 66.7
ROTATION_WEAK = 33.3

REGIME_LABEL = {
    "high": "高位(过热)",
    "mid": "中性",
    "low": "低位",
}
ROTATION_LABEL = {
    "strong": "强(主线不清)",
    "mid": "中",
    "weak": "弱(主线清晰)",
}

# 双轴决策矩阵（落实 NEW策略.md §2.3）：key = (情绪, 轮动强度)
REGIME_MATRIX = {
    ("high", "strong"): {"position": 0.30, "level": "轻仓", "action": "大幅降低仓位，防御为主"},
    ("high", "mid"):    {"position": 0.40, "level": "轻仓", "action": "过热+轮动加速，大幅降低仓位"},
    ("high", "weak"):   {"position": 0.55, "level": "轻仓", "action": "情绪过热，防御为主，保留主线"},
    ("mid", "strong"):  {"position": 0.60, "level": "均衡", "action": "轮动加速，适度降低仓位"},
    ("mid", "mid"):     {"position": 0.75, "level": "均衡", "action": "中性环境，均衡持有"},
    ("mid", "weak"):    {"position": 0.80, "level": "均衡", "action": "中性+主线清晰，标准仓位"},
    ("low", "strong"):  {"position": 0.70, "level": "均衡", "action": "低位但轮动快，均衡配置待主线清晰"},
    ("low", "mid"):     {"position": 0.85, "level": "重仓", "action": "逐步加仓，布局看好方向"},
    ("low", "weak"):    {"position": 0.95, "level": "重仓", "action": "积极加仓，把握主线行情"},
}
SENTIMENT_ORDER = ["high", "mid", "low"]      # 网格行顺序（上→下）
ROTATION_ORDER = ["weak", "mid", "strong"]    # 网格列顺序（左→右）


def _get_conn():
    from src.core.db_manager_postgresql import get_conn
    return get_conn()


# ════════════════════════════════════════════════════════════
# 数据加载
# ════════════════════════════════════════════════════════════
def _load_panel(conn, table: str, codes: List[str]) -> pd.DataFrame:
    """拉取多只 ETF 的日线收盘价面板。trade_date 已是 DATE 类型(迁移008)。"""
    sql = text(
        f"SELECT ts_code, trade_date, close FROM {table} "
        f"WHERE ts_code IN :codes ORDER BY ts_code, trade_date"
    ).bindparams(bindparam("codes", expanding=True))
    rows = conn.execute(sql, {"codes": list(codes)}).fetchall()
    if not rows:
        return pd.DataFrame(columns=["ts_code", "trade_date", "close"])
    df = pd.DataFrame(rows, columns=["ts_code", "trade_date", "close"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df["trade_date"] = df["trade_date"].apply(
        lambda d: d.strftime("%Y%m%d") if hasattr(d, "strftime") else str(d).replace("-", "")
    )
    return df


def _non_commodity_sector_codes() -> List[str]:
    """行业 ETF 剔除商品类（黄金/石油，无行业轮动语义）。"""
    from config.config import SECTOR_ETF, COMMODITY_ETF_CODES
    return [c for c in SECTOR_ETF if c not in COMMODITY_ETF_CODES]


def _breadth_universe_codes() -> List[str]:
    """宽度温度计用到的全部非商品 ETF（宽基 + 行业）。"""
    from config.config import INDEX_ETF
    return list(INDEX_ETF.keys()) + _non_commodity_sector_codes()


# ════════════════════════════════════════════════════════════
# ① 市场情绪指标
# ════════════════════════════════════════════════════════════
def _compute_index_trend(conn) -> Tuple[pd.DataFrame, str, list]:
    """3 只宽基 ETF 的趋势分序列。

    返回 (daily_series_df, latest_date, latest_components)。
    daily_series_df 列: [trade_date, trend]（3 只宽基的合成趋势分等权平均）。
    latest_components: 每只宽基 ETF 最新一日的分项明细（供页面展示）。
    """
    from src.analysis.rsi_factor import compute_rsi
    from config.config import INDEX_ETF

    df = _load_panel(conn, "index_etf_daily", BROAD_INDEX_CODES)
    if df.empty:
        return pd.DataFrame(columns=["trade_date", "trend"]), "", []

    pivot = df.pivot(index="trade_date", columns="ts_code", values="close").sort_index()
    per_index_scores = {}  # code -> DataFrame(dev, rsi, ret20) 日期对齐

    for code in BROAD_INDEX_CODES:
        if code not in pivot.columns:
            continue
        s = pivot[code].dropna()
        if len(s) < MA60_WINDOW + 5:
            continue
        ma60 = s.rolling(MA60_WINDOW, min_periods=MA60_WINDOW // 2).mean()
        dev_ma60 = (s - ma60) / ma60
        rsi14 = compute_rsi(s, 14)
        ret20 = s.pct_change(RET20_WINDOW)
        per_index_scores[code] = pd.DataFrame(
            {"dev": dev_ma60, "rsi": rsi14, "ret20": ret20}, index=s.index
        )

    if not per_index_scores:
        return pd.DataFrame(columns=["trade_date", "trend"]), "", []

    combined = pd.concat(
        {code: d for code, d in per_index_scores.items()}, axis=1
    ).sort_index()
    # ret20 在 3 只宽基间横截面排名 → [0,1] → 中心化到 [-1,1]
    ret20_block = combined.xs("ret20", axis=1, level=1)
    ret20_rank = ret20_block.rank(axis=1, pct=True)

    per_index_final = {}
    for code in per_index_scores:
        dev = combined[(code, "dev")]
        rsi = combined[(code, "rsi")]
        rank_c = ret20_rank[code] if code in ret20_rank.columns else pd.Series(0.5, index=combined.index)
        s_idx = (
            0.40 * dev.clip(-1, 1)
            + 0.35 * ((rsi - 50) / 25).clip(-1, 1)
            + 0.25 * (rank_c - 0.5) * 2
        )
        per_index_final[code] = s_idx

    score_df = pd.DataFrame(per_index_final)
    daily_trend = score_df.mean(axis=1)  # 等权平均

    latest_date = daily_trend.index[-1]
    components = []
    for code in BROAD_INDEX_CODES:
        if code not in per_index_final:
            continue
        dev_v = combined[(code, "dev")].iloc[-1]
        rsi_v = combined[(code, "rsi")].iloc[-1]
        ret_v = combined[(code, "ret20")].iloc[-1]
        components.append({
            "code": code,
            "name": INDEX_ETF.get(code, code),
            "dev_ma60": round(float(dev_v), 4) if pd.notna(dev_v) else 0.0,
            "rsi14": round(float(rsi_v), 1) if pd.notna(rsi_v) else 50.0,
            "ret20": round(float(ret_v), 4) if pd.notna(ret_v) else 0.0,
            "score": round(float(per_index_final[code].iloc[-1]), 3) if pd.notna(per_index_final[code].iloc[-1]) else 0.0,
        })

    series = daily_trend.dropna().tail(HISTORY_DAYS).reset_index()
    series.columns = ["trade_date", "trend"]
    series["trend"] = series["trend"].astype(float)
    return series, latest_date, components


def _compute_breadth(conn) -> Tuple[pd.Series, str]:
    """全部非商品 ETF 的市场宽度温度计序列。

    每日: frac_above_ma20 / frac_above_ma60 加权 → breadth_pct → 中心化到 [-1,1]。
    返回 (daily_breadth_series[YYYYMMDD], latest_date)。
    """
    codes = _breadth_universe_codes()
    df = _load_panel(conn, "sector_etf_daily", codes)
    if df.empty:
        df = _load_panel(conn, "index_etf_daily", codes)
    if df.empty:
        return pd.Series(dtype=float), ""

    pivot = df.pivot(index="trade_date", columns="ts_code", values="close").sort_index()
    ma20 = pivot.rolling(MA20_WINDOW, min_periods=MA20_WINDOW // 2).mean()
    ma60 = pivot.rolling(MA60_WINDOW, min_periods=MA60_WINDOW // 2).mean()
    above20 = (pivot > ma20).mean(axis=1)
    above60 = (pivot > ma60).mean(axis=1)
    breadth_pct = 0.5 * above20 + 0.5 * above60
    breadth_score = (breadth_pct - 0.5) * 2
    cleaned = breadth_score.dropna()
    return cleaned, (cleaned.index[-1] if cleaned.size else "")


def compute_market_sentiment(conn=None) -> dict:
    """市场情绪指标。

    score = clip((0.55*趋势分 + 0.45*宽度分) * 离散度折扣, -1, +1)
    区间: >+0.5 高位(过热) / [-0.5,+0.5] 中性 / <-0.5 低位
    """
    from src.analysis.market_timing import _compute_cross_sectional_dispersion

    own_conn = conn is None
    if own_conn:
        conn = _get_conn()
    try:
        trend_series, trend_date, trend_components = _compute_index_trend(conn)
        breadth_series, breadth_date = _compute_breadth(conn)

        latest_date = trend_date or breadth_date or ""
        dispersion = _compute_cross_sectional_dispersion(conn, latest_date) if latest_date else 1.0
        discount = 1.0 / max(1.0, dispersion)

        if trend_series.empty or breadth_series.empty:
            return {"date": latest_date, "score": 0.0, "regime": "mid",
                    "regime_label": REGIME_LABEL["mid"], "components": {},
                    "series": [], "dispersion": round(float(dispersion), 3),
                    "discount": round(float(discount), 3)}

        trend_latest = float(trend_series["trend"].iloc[-1]) if len(trend_series) else 0.0
        breadth_latest = float(breadth_series.iloc[-1])
        raw = 0.55 * trend_latest + 0.45 * breadth_latest
        score = max(-1.0, min(1.0, raw * discount))
        regime = "high" if score > SENTIMENT_HIGH else ("low" if score < SENTIMENT_LOW else "mid")

        # 合成每日序列（用最新离散度折扣统一缩放，保证序列末点 ≈ headline）
        t = trend_series.set_index("trade_date")["trend"]
        aligned = pd.DataFrame({"trend": t, "breadth": breadth_series}).dropna()
        aligned["score"] = (0.55 * aligned["trend"] + 0.45 * aligned["breadth"]) * discount
        aligned["score"] = aligned["score"].clip(-1, 1)
        series = aligned.tail(HISTORY_DAYS).reset_index()
        series_records = [
            {"date": d, "score": round(float(s), 3),
             "trend": round(float(tr), 3), "breadth": round(float(br), 3)}
            for d, s, tr, br in zip(series["trade_date"], series["score"],
                                    series["trend"], series["breadth"])
        ]

        # 宽度分项明细
        breadth_detail = {}
        try:
            bdf = _load_panel(conn, "sector_etf_daily", _breadth_universe_codes())
            if bdf.empty:
                bdf = _load_panel(conn, "index_etf_daily", _breadth_universe_codes())
            if not bdf.empty:
                bp = bdf.pivot(index="trade_date", columns="ts_code", values="close").sort_index()
                bma20 = bp.rolling(MA20_WINDOW, min_periods=MA20_WINDOW // 2).mean()
                bma60 = bp.rolling(MA60_WINDOW, min_periods=MA60_WINDOW // 2).mean()
                last = bp.iloc[-1]
                breadth_detail = {
                    "frac_above_ma20": round(float((last > bma20.iloc[-1]).mean()), 3),
                    "frac_above_ma60": round(float((last > bma60.iloc[-1]).mean()), 3),
                    "n_etfs": int(bp.shape[1]),
                }
        except Exception as exc:
            logger.warning("breadth detail failed: %s", exc)

        return {
            "date": latest_date,
            "score": round(score, 3),
            "regime": regime,
            "regime_label": REGIME_LABEL[regime],
            "components": {
                "trend_score": round(trend_latest, 3),
                "breadth_score": round(breadth_latest, 3),
                "dispersion": round(float(dispersion), 3),
                "discount": round(float(discount), 3),
                "broad_index": trend_components,
                "breadth": breadth_detail,
            },
            "series": series_records,
        }
    finally:
        if own_conn:
            conn.close()


# ════════════════════════════════════════════════════════════
# ② 行业轮动强度指标
# ════════════════════════════════════════════════════════════
def compute_rotation_strength(conn=None) -> dict:
    """行业轮动强度 = 行业 5 日收益排名的日均绝对变化，做 20 日滚动均值。

    高 = 资金在各行业间快速切换、主线不清；低 = 主线清晰、资金聚焦。
    strength_pct = 最新值在全历史的百分位。等级按三分位划分。
    """
    from scipy.stats import percentileofscore

    own_conn = conn is None
    if own_conn:
        conn = _get_conn()
    try:
        codes = _non_commodity_sector_codes()
        df = _load_panel(conn, "sector_etf_daily", codes)
        if df.empty:
            return {"date": "", "score": 0.0, "strength_pct": 50.0,
                    "level": "mid", "level_label": ROTATION_LABEL["mid"], "series": []}

        pivot = df.pivot(index="trade_date", columns="ts_code", values="close").sort_index()
        ret5 = pivot.pct_change(ROTATION_RET_WINDOW)
        rank = ret5.rank(axis=1, pct=True)
        delta_rank = rank.diff().abs()
        churn = delta_rank.mean(axis=1)
        rolling = churn.rolling(ROTATION_RANK_WINDOW, min_periods=ROTATION_RANK_WINDOW // 2).mean().dropna()
        if rolling.empty:
            return {"date": str(pivot.index[-1]), "score": 0.0, "strength_pct": 50.0,
                    "level": "mid", "level_label": ROTATION_LABEL["mid"], "series": []}

        latest = float(rolling.iloc[-1])
        pct = float(percentileofscore(rolling.values, latest))
        level = "strong" if pct > ROTATION_STRONG else ("weak" if pct < ROTATION_WEAK else "mid")

        series = rolling.tail(SECTOR_SERIES_DAYS)
        churn_tail = churn.reindex(series.index)
        series_records = [
            {"date": d, "churn": round(float(c), 3) if pd.notna(c) else 0.0,
             "rolling_mean": round(float(r), 3)}
            for d, c, r in zip(series.index, churn_tail.values, series.values)
        ]

        return {
            "date": str(series.index[-1]),
            "score": round(latest, 3),
            "strength_pct": round(pct, 1),
            "level": level,
            "level_label": ROTATION_LABEL[level],
            "series": series_records,
        }
    finally:
        if own_conn:
            conn.close()


# ════════════════════════════════════════════════════════════
# ③ 双轴决策矩阵
# ════════════════════════════════════════════════════════════
def classify_regime(sentiment_regime: str, rotation_level: str) -> dict:
    """情绪×轮动 → 总仓位/等级/操作。返回当前格 + 3×3 网格渲染数据。"""
    cell = REGIME_MATRIX[(sentiment_regime, rotation_level)]
    cur_sent, cur_rot = sentiment_regime, rotation_level
    rows = []
    for s in SENTIMENT_ORDER:
        cells = []
        for r in ROTATION_ORDER:
            m = REGIME_MATRIX[(s, r)]
            cells.append({
                "sentiment": s, "rotation": r,
                "position": m["position"], "level": m["level"],
                "action": m["action"],
                "current": (s == cur_sent and r == cur_rot),
            })
        rows.append({"sentiment": s, "label": REGIME_LABEL[s], "cells": cells})
    return {
        "current_cell": [cur_sent, cur_rot],
        "recommended_position": cell["position"],
        "level": cell["level"],
        "action": cell["action"],
        "sentiment_order": SENTIMENT_ORDER,
        "rotation_order": ROTATION_ORDER,
        "rotation_labels": {r: ROTATION_LABEL[r] for r in ROTATION_ORDER},
        "rows": rows,
    }


# ════════════════════════════════════════════════════════════
# ④ 进攻/防守组合
# ════════════════════════════════════════════════════════════
def _fetch_factor_snapshot(conn, preset_id: str = "optimized") -> Tuple[List[dict], Optional[str]]:
    """最新一日的因子快照（仅取稳健常驻列，避免可选列探测）。

    返回 (etf_rows, latest_date)。每项含 code/name/z_flow/z_mom/factor/quadrant。
    """
    from config.config import SECTOR_ETF
    row = conn.execute(text(
        "SELECT MAX(trade_date) FROM factor_daily WHERE preset_id = :pid"
    ), {"pid": preset_id}).fetchone()
    if not row or not row[0]:
        return [], None
    latest_date = row[0]
    factor_rows = conn.execute(text("""
        SELECT etf_code, z_flow, z_mom, factor, quadrant
        FROM factor_daily
        WHERE preset_id = :pid AND trade_date = :d
    """), {"pid": preset_id, "d": latest_date}).fetchall()

    def _sf(v):
        if v is None or v is pd.NA:
            return 0.0
        try:
            f = float(v)
            return 0.0 if pd.isna(f) else f
        except (ValueError, TypeError):
            return 0.0

    out = []
    for r in factor_rows:
        code = r[0]
        out.append({
            "code": code,
            "name": SECTOR_ETF.get(code, code),
            "z_flow": _sf(r[1]),
            "z_mom": _sf(r[2]),
            "factor": _sf(r[3]),
            "quadrant": int(r[4]) if r[4] is not None else 0,
        })
    return out, latest_date


def _compute_corr_matrix(conn, codes: List[str]) -> pd.DataFrame:
    """持仓篮子的 180 日收益相关矩阵（照搬 rec_engine:195-202,323-328 模式）。"""
    if not codes:
        return pd.DataFrame()
    sql = text(
        "SELECT ts_code, trade_date, close FROM sector_etf_daily "
        "WHERE ts_code IN :codes ORDER BY ts_code, trade_date"
    ).bindparams(bindparam("codes", expanding=True))
    rows = conn.execute(sql, {"codes": list(codes)}).fetchall()
    if not rows:
        return pd.DataFrame()
    cf = pd.DataFrame(rows, columns=["ts_code", "trade_date", "close"])
    cf["close"] = pd.to_numeric(cf["close"], errors="coerce")
    cf["ret"] = cf.groupby("ts_code")["close"].pct_change()
    ret_pivot = cf.pivot(index="trade_date", columns="ts_code", values="ret").dropna()
    if ret_pivot.empty:
        return pd.DataFrame()
    return ret_pivot.corr()


def _full_pool_corr(conn, preset_id: str, latest_date) -> pd.DataFrame:
    """全候选池的相关矩阵（用于进攻篮子内部去相关）。"""
    sql = text("""
        SELECT ts_code, trade_date, close FROM sector_etf_daily
        WHERE ts_code IN (SELECT etf_code FROM factor_daily
                          WHERE preset_id = :pid AND trade_date = :d)
          AND trade_date >= (SELECT MAX(trade_date) - INTERVAL '180 days' FROM sector_etf_daily)
        ORDER BY ts_code, trade_date
    """)
    rows = conn.execute(sql, {"pid": preset_id, "d": latest_date}).fetchall()
    if not rows:
        return pd.DataFrame()
    cf = pd.DataFrame(rows, columns=["ts_code", "trade_date", "close"])
    cf["close"] = pd.to_numeric(cf["close"], errors="coerce")
    cf["ret"] = cf.groupby("ts_code")["close"].pct_change()
    ret_pivot = cf.pivot(index="trade_date", columns="ts_code", values="ret").dropna()
    return ret_pivot.corr() if not ret_pivot.empty else pd.DataFrame()


def _size_basket(scored: List[Tuple[dict, float]], budget: float) -> List[Tuple[dict, float]]:
    """按得分比例分配预算，单只上限 MAX_SINGLE_ETF(占总仓位)，溢出再分配。

    scored: [(entry, final_score), ...] 已按得分降序。返回 [(entry, weight), ...]。
    """
    total_score = sum(s for _, s in scored)
    if total_score <= 0:
        n = max(len(scored), 1)
        return [(e, budget / n) for e, _ in scored]

    weights = [budget * (s / total_score) for _, s in scored]
    # 迭代上限再分配（照搬 rec_engine:515-543）
    for _ in range(6):
        excess = sum(max(0, w - MAX_SINGLE_ETF) for w in weights)
        capped_any = False
        for i in range(len(weights)):
            if weights[i] > MAX_SINGLE_ETF:
                weights[i] = MAX_SINGLE_ETF
                capped_any = True
        if excess <= 0 or not capped_any:
            break
        uncapped_idx = [i for i in range(len(weights)) if weights[i] < MAX_SINGLE_ETF - 1e-9]
        uncapped_total = sum(weights[i] for i in uncapped_idx)
        if uncapped_total <= 0 or not uncapped_idx:
            break
        for i in uncapped_idx:
            weights[i] += excess * (weights[i] / uncapped_total)
    return [(e, w) for e, w in zip([e for e, _ in scored], weights)]


def _select_attack(factor_rows: List[dict], pool_corr: pd.DataFrame,
                   budget: float, max_n: int = MAX_ATTACK) -> List[dict]:
    """进攻层：Q1(强势)象限按 factor 排序，池内两阶段相关性惩罚，取前 max_n。

    若 Q1 不足 2 只，回退纳入最高 factor 的 Q2/Q3，确保进攻有标的。
    """
    from config.config import SECTOR_ETF
    candidates = [e for e in factor_rows
                  if e["code"] in SECTOR_ETF and e["quadrant"] == 1 and e["factor"] > 0]
    if len(candidates) < 2:
        for e in factor_rows:
            if e["code"] in SECTOR_ETF and e["quadrant"] in (2, 3) and e["factor"] > 0 and e not in candidates:
                candidates.append(e)
    candidates.sort(key=lambda x: -x["factor"])
    if not candidates:
        return []

    pool = candidates[: max_n * 2]
    penalty = {e["code"]: 1.0 for e in pool}
    if pool_corr is not None and not pool_corr.empty:
        for i in range(len(pool)):
            for j in range(i + 1, len(pool)):
                ci, cj = pool[i]["code"], pool[j]["code"]
                if ci not in pool_corr.index or cj not in pool_corr.columns:
                    continue
                cv = abs(float(pool_corr.loc[ci, cj]))
                if np.isnan(cv):
                    continue
                for thr, pen in CORR_PENALTY.items():
                    if cv > thr:
                        penalty[cj] = min(penalty[cj], pen)
                        break

    scored = [(e, max(0.0, e["factor"]) * penalty[e["code"]]) for e in pool]
    scored = [(e, s) for e, s in scored if s > 0]
    scored.sort(key=lambda x: -x[1])
    top = scored[:max_n] if scored else [(e, max(0.0, e["factor"])) for e in pool[:max_n]]
    sized = _size_basket(top, budget)

    return [{
        "code": e["code"], "name": e["name"], "quadrant": e["quadrant"],
        "factor_score": round(float(e["factor"]), 3),
        "z_mom": round(float(e["z_mom"]), 3),
        "position_ratio": round(float(w), 4), "role": "attack",
    } for e, w in sized]


def _select_defense(factor_rows: List[dict], pool_corr: pd.DataFrame,
                    attack_codes: List[str], budget: float,
                    max_n: int = MAX_DEFENSE) -> List[dict]:
    """防守层：Q2(反转/潜伏)象限按 factor 排序，与进攻篮子 corr>0.6 者降权，取前 max_n。"""
    from config.config import SECTOR_ETF
    candidates = [e for e in factor_rows
                  if e["code"] in SECTOR_ETF and e["quadrant"] == 2]
    candidates.sort(key=lambda x: -x["factor"])
    if not candidates:
        return []

    pool = candidates[: max_n * 2]
    scored = []
    for e in pool:
        pen = 1.0
        if pool_corr is not None and not pool_corr.empty:
            for ac in attack_codes:
                if ac == e["code"] or ac not in pool_corr.index or e["code"] not in pool_corr.columns:
                    continue
                cv = abs(float(pool_corr.loc[ac, e["code"]]))
                if not np.isnan(cv) and cv > 0.6:
                    pen = min(pen, 0.5)
                    break
        scored.append((e, max(0.0, e["factor"]) * pen))
    scored.sort(key=lambda x: -x[1])
    top = scored[:max_n]
    sized = _size_basket(top, budget)

    return [{
        "code": e["code"], "name": e["name"], "quadrant": e["quadrant"],
        "factor_score": round(float(e["factor"]), 3),
        "z_mom": round(float(e["z_mom"]), 3),
        "position_ratio": round(float(w), 4), "role": "defense",
    } for e, w in sized]


def build_rotation_portfolio(conn=None, preset_id: str = "optimized",
                             total_position: float = 0.75) -> dict:
    """构建进攻/防守组合 + 持仓相关性矩阵。

    total_position 由决策矩阵给出；按 ATTACK/DEFENSE 比例分配到两层。
    """
    own_conn = conn is None
    if own_conn:
        conn = _get_conn()
    try:
        factor_rows, latest_date = _fetch_factor_snapshot(conn, preset_id)
        pool_corr = _full_pool_corr(conn, preset_id, latest_date) if latest_date else pd.DataFrame()

        attack_budget = total_position * ATTACK_BUDGET_SHARE
        defense_budget = total_position * DEFENSE_BUDGET_SHARE
        attack = _select_attack(factor_rows, pool_corr, attack_budget)
        attack_codes = [a["code"] for a in attack]
        defense = _select_defense(factor_rows, pool_corr, attack_codes, defense_budget)

        # 持仓相关性热力图（进攻+防守，≤6 只）。矩阵按 code 计算相关系数，
        # 但坐标轴/tooltip 显示 ETF 名称（与 holding_codes 同序）。
        holding_codes = attack_codes + [d["code"] for d in defense]
        holding_corr = _compute_corr_matrix(conn, holding_codes)
        holding_names = [a["name"] for a in attack] + [d["name"] for d in defense]
        corr_payload = {"labels": holding_names, "matrix": []}
        if not holding_corr.empty and holding_codes:
            sub = holding_corr.reindex(index=holding_codes, columns=holding_codes)
            corr_payload["matrix"] = [
                [round(float(sub.loc[r, c]), 2) if pd.notna(sub.loc[r, c]) else 0.0
                 for c in holding_codes]
                for r in holding_codes
            ]

        return {
            "attack": attack,
            "defense": defense,
            "correlation": corr_payload,
            "total_position": round(float(total_position), 3),
            "split": {"attack": ATTACK_BUDGET_SHARE, "defense": DEFENSE_BUDGET_SHARE},
            "attack_count": len(attack),
            "defense_count": len(defense),
            "preset_id": preset_id,
        }
    finally:
        if own_conn:
            conn.close()


# ════════════════════════════════════════════════════════════
# 顶层入口：组装完整报告
# ════════════════════════════════════════════════════════════
def build_rotation_report(preset_id: str = "optimized") -> dict:
    """生成轮动策略完整报告（页面 /api/rotation/report 的数据源）。"""
    from config.config import SECTOR_ETF
    from src.core.db_manager_postgresql import safe_dict

    conn = _get_conn()
    try:
        # 1) 数据覆盖度护栏（照搬 rec_engine:356-374）
        cov_row = conn.execute(text("""
            SELECT COUNT(*) FROM factor_daily
            WHERE preset_id = :pid AND trade_date = (
                SELECT MAX(trade_date) FROM factor_daily WHERE preset_id = :pid)
        """), {"pid": preset_id}).fetchone()
        latest_count = cov_row[0] if cov_row else 0
        total_tracked = len(SECTOR_ETF)
        if latest_count < total_tracked * 0.5:
            logger.warning("rotation: 数据覆盖不足 %s/%s", latest_count, total_tracked)
            return safe_dict({
                "date": str(datetime.now().date()),
                "data_incomplete": True,
                "error": "ETF 份额数据覆盖不足，等待下一个交易日数据更新后自动恢复",
                "sentiment": {}, "rotation": {}, "regime_matrix": {},
                "portfolio": {"attack": [], "defense": [],
                              "correlation": {"labels": [], "matrix": []},
                              "total_position": 0, "split": {},
                              "attack_count": 0, "defense_count": 0},
                "narrative": [],
                "risk_warning": ["⚠️ ETF 数据覆盖不足，当前策略建议不适用"],
            })

        # 2) 三大指标
        sentiment = compute_market_sentiment(conn)
        rotation = compute_rotation_strength(conn)

        # 3) 决策矩阵 → 总仓位
        regime = classify_regime(sentiment["regime"], rotation["level"])
        total_position = regime["recommended_position"]

        # 4) 组合
        portfolio = build_rotation_portfolio(conn, preset_id, total_position)
    finally:
        conn.close()

    # 5) 文字解读
    s_regime_cn = sentiment["regime_label"]
    r_level_cn = rotation["level_label"]
    comps = sentiment.get("components", {}) or {}
    narrative = [
        f"市场情绪{s_regime_cn}（情绪分 {sentiment['score']:+.2f}，"
        f"趋势分 {comps.get('trend_score', 0):+.2f} / 宽度分 {comps.get('breadth_score', 0):+.2f}）。",
        f"行业轮动{r_level_cn}（强度百分位 {rotation['strength_pct']:.0f}%）。",
        f"当前处于【{s_regime_cn} × {r_level_cn}】格局，建议总仓位 "
        f"{total_position*100:.0f}%（{regime['level']}）：{regime['action']}。",
    ]
    if portfolio["attack"]:
        names = "、".join(a["name"] for a in portfolio["attack"][:3])
        narrative.append(f"进攻层（约 {ATTACK_BUDGET_SHARE*100:.0f}%）聚焦：{names}。")
    else:
        narrative.append("当前无符合 Q1 强势条件的进攻标的，进攻层暂空。")
    if portfolio["defense"]:
        names = "、".join(d["name"] for d in portfolio["defense"])
        narrative.append(f"防守层（约 {DEFENSE_BUDGET_SHARE*100:.0f}%）配置反转预期：{names}。")

    # 6) 风险提示
    risk = []
    if rotation["level"] == "strong":
        risk.append("⚠️ 行业轮动强度偏高，主线不清晰，注意控制单一行业暴露。")
    if sentiment["regime"] == "high":
        risk.append("⚠️ 市场情绪处于高位（过热），警惕回调，优先防御。")
    elif sentiment["regime"] == "low":
        risk.append("ℹ️ 市场情绪处于低位，反转上行概率上升，是逐步布局时机。")
    matrix = portfolio["correlation"].get("matrix", [])
    max_corr = 0.0
    if matrix and len(matrix) > 1:
        for i in range(len(matrix)):
            for j in range(i + 1, len(matrix)):
                max_corr = max(max_corr, matrix[i][j])
    if max_corr > 0:
        risk.append(f"🔗 组合内最大两两相关系数 {max_corr:.2f}，分散度"
                    f"{'良好' if max_corr < 0.6 else '偏低，注意集中度'}。")
    risk.append(f"ℹ️ ETF 数据覆盖：{latest_count}/{total_tracked} 只行业 ETF 有最新因子数据。")
    risk.append("ⓘ 本页为中信期货 ETF 轮动框架的量化参考实现，不构成投资建议。市场有风险，投资需谨慎。")

    return safe_dict({
        "date": sentiment.get("date") or rotation.get("date") or str(datetime.now().date()),
        "preset_id": preset_id,
        "sentiment": sentiment,
        "rotation": rotation,
        "regime_matrix": regime,
        "portfolio": portfolio,
        "narrative": narrative,
        "risk_warning": risk,
        "data_incomplete": False,
    })
