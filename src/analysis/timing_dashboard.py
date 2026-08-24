"""大盘温度计：择时仪表盘（五面板 + 仓位合成）。

设计原则（源自 20 年宽基ETF量价份额研究 etf_timing_analysis/REPORT.md）：
- 不做"明日方向预测"（统计上不可行）；每个面板只回答一个状态问题。
- 估值分位 → 长周期位置；趋势状态 → MA200 上/下的状态标签（非交易信号）；
  恐慌仪表 → 极端事件后的短反转（唯一 OOS 稳健的方法族）；
  波动状态 → 量能是"波动计"而非"方向计"，用于仓位乘数；
  家族份额流 → 同指数聚合份额 vs 价格的滚动相关（越跌越买 regime 识别）。
- 仓位合成 = 波动乘数 + 恐慌叠加 + 估值修正（分解展示，非黑盒）。
"""
from __future__ import annotations

import logging
import numpy as np
import pandas as pd
from sqlalchemy import text

logger = logging.getLogger(__name__)

# 市场代理：沪深300ETF（恐慌/波动面板均以其为代表）
MARKET_PROXY = "510300.SH"
# 恐慌弹性参考：研究显示恐慌反转在高β品种上胜率最高（588000 88% / 512100 75%）
PANIC_BETA_CODES = {"588000.SH": "科创50ETF", "512100.SH": "中证1000ETF"}

MA200_WINDOW = 200
YEAR_WINDOW = 250
VOL_WINDOW = 20
VOL_TARGET = 0.12           # 目标年化波动 12%
VOL_MULT_FLOOR = 0.30       # 波动乘数下限（永远保留的最低暴露）
PANIC_RET5D_TH = -0.05      # 5日跌 5%
PANIC_AMOUNT_Z_TH = 1.0     # 量能 60 日 z ≥ 1（放量确认）
PANIC_DEDUPE_DAYS = 10      # 相邻事件去重窗口（episode 化）
LOCATOR_DD_TH = -0.20       # 深跌阈值：距滚动高点 -20%
LOCATOR_SHARE_TH = 0.0      # 家族 20 日份额逆势流入 > 0


def _norm_date(v) -> str:
    s = str(v)
    return s.replace("-", "")[:8]


_ADJ_CLOSE_SQL = """
    SELECT d.trade_date,
           d.close * COALESCE(a.adj_factor, 1)
             / COALESCE((SELECT MAX(adj_factor) FROM etf_adj_factor WHERE ts_code = :c), 1) AS close
    FROM {table} d
    LEFT JOIN etf_adj_factor a
           ON a.ts_code = d.ts_code AND a.trade_date = d.trade_date
    WHERE d.ts_code = :c
    ORDER BY d.trade_date
"""


def _fetch_adj_closes(conn, table: str, code: str, limit: int | None = None):
    """前复权收盘序列 [(date_str, close)]（升序）。

    ETF 份额折算/拆分会造成价格 overnight 跳变（如 512100 2022-09-05 单日
    +176%），未复权序列会污染月收益/回撤/恐慌识别。
    """
    sql = _ADJ_CLOSE_SQL.format(table=table)
    if limit:
        sql = sql.replace(
            "ORDER BY d.trade_date",
            "ORDER BY d.trade_date DESC LIMIT :n"
        )
        rows = conn.execute(text(sql), {"c": code, "n": limit}).fetchall()
        return [(_norm_date(r[0]), float(r[1])) for r in reversed(rows)]
    rows = conn.execute(text(sql), {"c": code}).fetchall()
    return [(_norm_date(r[0]), float(r[1])) for r in rows]


def _percentile(history, current) -> float:
    """当前值在历史序列中的百分位（0-100）。"""
    arr = np.asarray([x for x in history if x is not None and not pd.isna(x)], dtype=float)
    if len(arr) == 0 or current is None or pd.isna(current):
        return 50.0
    return float((arr < current).sum() / len(arr) * 100.0)


# ══════════════════════════════════════════════════
# 纯函数（可单测）
# ══════════════════════════════════════════════════
def panic_events(closes: np.ndarray, amounts: np.ndarray):
    """恐慌抛售事件识别与前瞻收益统计。

    事件定义：ret5d <= -5% 且 当日成交额 60 日 z >= 1（放量确认）。
    相邻 10 个交易日内的事件去重为一个 episode（取首个触发日）。
    前瞻收益按 t+1 开盘等价（t+1 收盘入场）计算。

    Returns (events, stats, current):
      events: [{idx, fwd_5d, fwd_10d, fwd_20d}]
      stats:  {n, mean_5d, win_5d, mean_10d, win_10d, mean_20d, win_20d}
      current: {ret_5d, amount_z, triggered, last_event_idx}
    """
    n = len(closes)
    events = []
    last_kept = -10**9
    if n > VOL_WINDOW + 6:
        rets = np.diff(closes) / closes[:-1]
        ret5 = np.full(n, np.nan)
        ret5[5:] = closes[5:] / closes[:-5] - 1
        # 60 日滚动 z 的成交额
        amt = pd.Series(amounts)
        az = ((amt - amt.rolling(60, min_periods=30).mean())
              / amt.rolling(60, min_periods=30).std()).values

        for i in range(60, n):
            if np.isnan(ret5[i]) or np.isnan(az[i]):
                continue
            if ret5[i] <= PANIC_RET5D_TH and az[i] >= PANIC_AMOUNT_Z_TH:
                if i - last_kept < PANIC_DEDUPE_DAYS:
                    continue
                last_kept = i
                ev = {"idx": int(i), "fwd_5d": None, "fwd_10d": None, "fwd_20d": None}
                if i + 1 < n and closes[i + 1] > 0:
                    entry = closes[i + 1]
                    for key, horizon in (("fwd_5d", 5), ("fwd_10d", 10), ("fwd_20d", 20)):
                        j = i + 1 + horizon  # t+1 收盘入场，持有 horizon 日
                        if j < n:
                            ev[key] = float(closes[j] / entry - 1)
                events.append(ev)

        stats = {"n": len(events)}
        for h in ("5d", "10d", "20d"):
            vals = [e[f"fwd_{h}"] for e in events if e[f"fwd_{h}"] is not None]
            stats[f"mean_{h}"] = round(float(np.mean(vals)) * 100, 2) if vals else None
            stats[f"win_{h}"] = round(float(np.mean([v > 0 for v in vals])) * 100, 1) if vals else None

        cur_az = az[-1] if not np.isnan(az[-1]) else 0.0
        current = {
            "ret_5d": round(float(ret5[-1]) * 100, 2) if not np.isnan(ret5[-1]) else None,
            "amount_z": round(float(cur_az), 2),
            "triggered": bool(
                not np.isnan(ret5[-1]) and ret5[-1] <= PANIC_RET5D_TH and cur_az >= PANIC_AMOUNT_Z_TH
            ),
            "last_event_idx": events[-1]["idx"] if events else None,
        }
        return events, stats, current
    return [], {"n": 0}, {"ret_5d": None, "amount_z": None, "triggered": False, "last_event_idx": None}


def drawdown_series(closes: np.ndarray) -> np.ndarray:
    """距滚动历史高点的回撤（负数，0 = 新高）。"""
    s = pd.Series(closes)
    return (s / s.cummax() - 1).values


def locator_events(drawdown: np.ndarray, share_chg20: np.ndarray,
                   share_series: np.ndarray | None = None):
    """底部定位器事件：深跌(<=-20%) 且 家族20日份额逆势流入(>0)。

    首次满足条件记为触发；恢复到 -10% 以内后重置。
    share_series（原始份额值）可选：用于剔除份额折算/拆分的假流入
    （单日变动 >50% 视为折算，该点不计入逆势流入）。
    Returns (event_idx_list, active_bool)
    """
    events = []
    in_event = False
    for i in range(len(drawdown)):
        share_ok = False
        if not np.isnan(share_chg20[i]):
            share_ok = share_chg20[i] > LOCATOR_SHARE_TH
            # 份额折算/合并（单日跳变>50%）不视为真流入
            if share_series is not None and i >= 1 and share_series[i] and share_series[i - 1]:
                day_chg = share_series[i] / share_series[i - 1] - 1
                if abs(day_chg) > 0.5:
                    share_ok = False
        dd_ok = drawdown[i] <= LOCATOR_DD_TH
        if not in_event and dd_ok and share_ok:
            events.append(i)
            in_event = True
        elif in_event and drawdown[i] > -0.10:
            in_event = False
    return events, bool(in_event and len(drawdown) and drawdown[-1] <= LOCATOR_DD_TH)


def monthly_avg_returns(dates, closes):
    """按日历月复合月收益 → 各月份历史平均（%）。dates: YYYYMMDD 或 date。

    Returns (avg_by_month[12], n_months, detail) — avg 为 None 表示样本不足。
    """
    df = pd.DataFrame({"d": [str(x).replace("-", "")[:6] for x in dates], "c": closes})
    month_last = df.groupby("d")["c"].last()
    month_last = month_last.sort_index()
    if len(month_last) < 2:
        return [None] * 12, 0, {}
    mret = month_last / month_last.shift(1) - 1
    mret = mret.iloc[1:]  # 首月无前月基准
    detail = {k: round(float(v) * 100, 2) for k, v in mret.items()}
    by_month = {}
    for k, v in mret.items():
        by_month.setdefault(k[4:6], []).append(float(v))
    avg = []
    for m in range(1, 13):
        vals = by_month.get(f"{m:02d}", [])
        avg.append(round(float(np.mean(vals)) * 100, 2) if vals else None)
    return avg, len(mret), detail


def rolling_corr_regime(share_chg: np.ndarray, rets: np.ndarray, window: int = 60) -> tuple:
    """份额日变化与日收益的滚动相关 → 当前 regime 判定。"""
    if len(share_chg) < window + 5:
        return None, None, "unknown"
    corr = pd.Series(share_chg).rolling(window).corr(pd.Series(rets)).values
    cur = corr[-1]
    if np.isnan(cur):
        return None, None, "unknown"
    if cur < -0.05:
        label = "dip_buying"       # 越跌越买：机构/配置盘承接
    elif cur > 0.05:
        label = "chasing"          # 追涨杀跌：动量申购
    else:
        label = "neutral"
    return round(float(cur), 3), [None if np.isnan(c) else round(float(c), 3) for c in corr[-120:]], label


# ══════════════════════════════════════════════════
# 面板计算（查库）
# ══════════════════════════════════════════════════
def compute_valuation_panel(conn) -> dict:
    from config.config import INDEX_VALUATION_CODES
    indices = []
    for code, name in INDEX_VALUATION_CODES.items():
        try:
            rows = conn.execute(text(
                "SELECT trade_date, pe, pb FROM index_daily_basic "
                "WHERE ts_code=:c ORDER BY trade_date"
            ), {"c": code}).fetchall()
        except Exception as exc:
            logger.warning("valuation query failed for %s: %s", code, exc)
            continue
        if not rows:
            indices.append({"code": code, "name": name, "pe": None, "pe_pct": None,
                            "pb": None, "pb_pct": None, "days": 0, "date": None})
            continue
        pe = [float(r[1]) for r in rows if r[1] is not None and float(r[1]) > 0]
        pb = [float(r[2]) for r in rows if r[2] is not None and float(r[2]) > 0]
        cur_pe = pe[-1] if pe else None
        cur_pb = pb[-1] if pb else None
        indices.append({
            "code": code, "name": name,
            "pe": round(cur_pe, 2) if cur_pe else None,
            "pe_pct": round(_percentile(pe[:-1], cur_pe), 1) if cur_pe else None,
            "pb": round(cur_pb, 2) if cur_pb else None,
            "pb_pct": round(_percentile(pb[:-1], cur_pb), 1) if cur_pb else None,
            "days": len(rows), "date": _norm_date(rows[-1][0]),
        })
    return {"indices": indices}


def compute_trend_panel(conn) -> dict:
    from config.config import INDEX_ETF
    out = []
    for code, name in INDEX_ETF.items():
        rows = _fetch_adj_closes(conn, "index_etf_daily", code, YEAR_WINDOW + 10)
        if not rows:
            continue
        closes = np.array([c for _, c in rows])
        ma200 = float(closes[-MA200_WINDOW:].mean()) if len(closes) >= MA200_WINDOW else None
        last = closes[-1]
        win = closes[-YEAR_WINDOW:]
        hi, lo = float(win.max()), float(win.min())
        out.append({
            "code": code, "name": name, "date": rows[-1][0],
            "close": round(last, 3),
            "ma200": round(ma200, 3) if ma200 else None,
            "vs_ma200_pct": round((last / ma200 - 1) * 100, 2) if ma200 else None,
            "state": ("above" if last >= ma200 else "below") if ma200 else None,
            "high_1y": round(hi, 3), "low_1y": round(lo, 3),
            "off_high_pct": round((last / hi - 1) * 100, 2),
            "off_low_pct": round((last / lo - 1) * 100, 2),
        })
    return {"indices": out}


def compute_panic_panel(conn) -> dict:
    from config.config import INDEX_ETF
    result = {"market": None, "high_beta": []}
    for code in [MARKET_PROXY] + list(PANIC_BETA_CODES.keys()):
        rows = conn.execute(text("""
            SELECT d.trade_date,
                   d.close * COALESCE(a.adj_factor, 1)
                     / COALESCE((SELECT MAX(adj_factor) FROM etf_adj_factor WHERE ts_code = :c), 1) AS close,
                   d.amount
            FROM index_etf_daily d
            LEFT JOIN etf_adj_factor a
                   ON a.ts_code = d.ts_code AND a.trade_date = d.trade_date
            WHERE d.ts_code = :c
            ORDER BY d.trade_date
        """), {"c": code}).fetchall()
        if len(rows) < 80:
            continue
        dates = [_norm_date(r[0]) for r in rows]
        closes = np.array([float(r[1]) for r in rows])
        amounts = np.array([float(r[2]) if r[2] is not None else 0.0 for r in rows])
        events, stats, current = panic_events(closes, amounts)
        payload = {
            "code": code,
            "name": INDEX_ETF.get(code, PANIC_BETA_CODES.get(code, code)),
            "date": dates[-1],
            "current": current,
            "stats": stats,
            "recent_events": [
                {
                    "date": dates[e["idx"]],
                    "fwd_5d": round(e["fwd_5d"] * 100, 2) if e["fwd_5d"] is not None else None,
                    "fwd_10d": round(e["fwd_10d"] * 100, 2) if e["fwd_10d"] is not None else None,
                    "fwd_20d": round(e["fwd_20d"] * 100, 2) if e["fwd_20d"] is not None else None,
                }
                for e in events[-10:]
            ],
        }
        if code == MARKET_PROXY:
            result["market"] = payload
        else:
            result["high_beta"].append(payload)
    return result


def compute_volatility_panel(conn) -> dict:
    rows = _fetch_adj_closes(conn, "index_etf_daily", MARKET_PROXY)
    if len(rows) < VOL_WINDOW + 60:
        return {"date": None, "vol_20d": None, "vol_pct": None, "target_mult": None,
                "series": []}
    dates = [d for d, _ in rows]
    closes = np.array([c for _, c in rows])
    rets = pd.Series(closes).pct_change()
    vol = rets.rolling(VOL_WINDOW).std() * np.sqrt(252)
    vol_valid = vol.dropna()
    cur = float(vol_valid.iloc[-1])
    mult = float(np.clip(VOL_TARGET / cur, VOL_MULT_FLOOR, 1.0))
    return {
        "date": dates[-1],
        "vol_20d": round(cur * 100, 2),
        "vol_pct": round(_percentile(vol_valid.values[:-1], cur), 1),
        "target_mult": round(mult, 3),
        "target_vol": VOL_TARGET,
        "series": [
            {"date": d, "vol": round(float(v) * 100, 2)}
            for d, v in zip(dates[-250:], vol.values[-250:]) if not np.isnan(v)
        ],
    }


def compute_family_flow_panel(conn) -> dict:
    from config.config import INDEX_ETF, INDEX_ETF_FAMILY
    from src.analysis.family import aggregate_family_share
    out = []
    for code, name in INDEX_ETF.items():
        family = INDEX_ETF_FAMILY.get(code, [code])
        ph = ", ".join(f":fc{i}" for i in range(len(family)))
        params = {f"fc{i}": c for i, c in enumerate(family)}
        share_rows = conn.execute(text(
            f"SELECT ts_code, trade_date, fd_share FROM etf_share "
            f"WHERE ts_code IN ({ph}) AND fd_share IS NOT NULL ORDER BY trade_date"
        ), params).fetchall()
        price_rows = _fetch_adj_closes(conn, "index_etf_daily", code, 500)
        if not share_rows or not price_rows:
            continue
        member_series = {}
        for r in share_rows:
            member_series.setdefault(r[0], []).append((_norm_date(r[1]), float(r[2])))
        agg = aggregate_family_share(member_series) if len(member_series) >= 2 else []
        if not agg:
            continue
        agg_map = dict(agg)
        prices = price_rows

        # 对齐：份额日期(YYYYMMDD) × 价格日期
        share_dates = [d for d, _ in agg][-500:]
        close_by_date = dict(prices)
        # 份额日变化与当日收益的滚动相关
        s_vals = np.array([agg_map[d] for d in share_dates], dtype=float)
        s_chg = np.diff(s_vals) / s_vals[:-1]
        c_vals = np.array([close_by_date.get(d, np.nan) for d in share_dates])
        crets = np.diff(c_vals) / c_vals[:-1]
        mask = ~np.isnan(crets)
        corr, corr_series, label = rolling_corr_regime(s_chg[mask], crets[mask], 60)

        chg20 = None
        if len(s_vals) > 20 and s_vals[-21] > 0:
            chg20 = round(float(s_vals[-1] / s_vals[-21] - 1) * 100, 2)

        series = [
            {"date": d, "share": round(float(agg_map[d]), 1),
             "close": close_by_date.get(d)}
            for d in share_dates[-120:]
        ]
        out.append({
            "code": code, "name": name, "family_members": len(member_series),
            "chg_20d_pct": chg20, "corr_60d": corr, "regime": label,
            "series": series,
        })
    return {"indices": out}


def compute_position_composite(conn, vol_mult, panic_triggered, valuation_median_pct) -> dict:
    """仓位合成：波动乘数为底，恐慌事件加仓、估值极值修正；因子层ICIR另列参考。"""
    panic_adj = 0.15 if panic_triggered else 0.0
    val_adj = 0.0
    if valuation_median_pct is not None:
        if valuation_median_pct <= 20:
            val_adj = 0.10
        elif valuation_median_pct >= 80:
            val_adj = -0.10
    base = vol_mult if vol_mult is not None else 0.7
    suggested = float(np.clip(base + panic_adj + val_adj, 0.20, 1.00))

    # 因子层参考：近 60 日 ICIR 门控乘数（无数据则 None，不参与合成）
    icir_mult = None
    icir_val = None
    try:
        rows = conn.execute(text(
            "SELECT ic_value FROM ic_daily WHERE preset_id='optimized' "
            "ORDER BY trade_date DESC LIMIT 60"
        )).fetchall()
        if rows and len(rows) >= 20:
            arr = np.array([float(r[0]) for r in rows if r[0] is not None])
            if len(arr) >= 20:
                icir_val = round(float(arr.mean() / arr.std()), 3) if arr.std() > 0 else None
                if icir_val is not None:
                    icir_mult = (1.0 if icir_val >= 0.5 else
                                 0.7 if icir_val >= 0.3 else
                                 0.5 if icir_val >= 0.2 else 0.0)
    except Exception as exc:
        logger.warning("ICIR gating lookup failed: %s", exc)

    return {
        "suggested_pct": round(suggested * 100, 0),
        "decomposition": [
            {"name": "波动乘数(底仓)", "value": round(base * 100, 0),
             "note": f"目标年化波动{VOL_TARGET*100:.0f}% / 当前20日波动"},
            {"name": "恐慌叠加", "value": round(panic_adj * 100, 0),
             "note": "5日跌≥5%且放量 → 历史5日胜率见恐慌面板"},
            {"name": "估值修正", "value": round(val_adj * 100, 0),
             "note": f"PE分位中位数 {valuation_median_pct}%（≤20加/≥80减）"},
            {"name": "因子层ICIR(参考)", "value": icir_mult,
             "note": f"近60日ICIR={icir_val}（不参与合成，独立参考）"},
        ],
        "icir_value": icir_val,
    }


# ══════════════════════════════════════════════════
# 日历热力图 / 底部定位器
# ══════════════════════════════════════════════════
# 标注窗口来自 AStockBenchmark 日历效应研究（353 日历日 FDR 筛后仅存的有效窗口）
CALENDAR_NOTES = [
    {"month": 2, "tag": "春节红包", "note": "二月效应+春节红包为全年第强窗口"},
    {"month": 6, "tag": "端午", "note": "端午后10日历史均值-2.12%（节后回调）"},
    {"month": 3, "tag": "季末", "note": "创业板季末效应+0.88% (p=.005)，仅高弹性品种"},
    {"month": 9, "tag": "季末", "note": "季末效应同上"},
]


def build_calendar() -> dict:
    """月度 × ETF 历史平均收益热力图数据（基于回补后的完整历史）。"""
    from config.config import INDEX_ETF, SECTOR_ETF
    from src.core.db_manager_postgresql import get_conn
    conn = get_conn()
    rows_out = []
    try:
        for table, code_map, tag in (
            ("index_etf_daily", INDEX_ETF, "index"),
            ("sector_etf_daily", SECTOR_ETF, "sector"),
        ):
            for code, name in code_map.items():
                try:
                    rows = _fetch_adj_closes(conn, table, code)
                except Exception as exc:
                    logger.warning("calendar query failed %s: %s", code, exc)
                    continue
                if len(rows) < 40:
                    continue
                dates = [d for d, _ in rows]
                closes = np.array([c for _, c in rows])
                avg, n_months, _ = monthly_avg_returns(dates, closes)
                rows_out.append({
                    "code": code, "name": name, "type": tag,
                    "months": avg, "n_months": n_months,
                    "first_date": dates[0],
                })
    finally:
        conn.close()
    rows_out.sort(key=lambda r: (r["type"] != "index", r["name"]))
    return {"rows": rows_out, "notes": CALENDAR_NOTES}


def build_locator() -> dict:
    """底部定位器：深跌(距滚动高点≤-20%) + 家族20日份额逆势流入。

    研究结论：该组合 3 次大底（2018Q4 / 2024初 / 2025-04）方向全对，
    是"底部区域定位器"——用于识别区域，不用于精确择时。
    """
    from config.config import INDEX_ETF, INDEX_ETF_FAMILY
    from src.analysis.family import aggregate_family_share
    from src.core.db_manager_postgresql import get_conn
    conn = get_conn()
    out = []
    try:
        for code, name in INDEX_ETF.items():
            price_rows = _fetch_adj_closes(conn, "index_etf_daily", code)
            if len(price_rows) < 100:
                continue
            dates = [d for d, _ in price_rows]
            closes = np.array([c for _, c in price_rows])
            dd = drawdown_series(closes)

            family = INDEX_ETF_FAMILY.get(code, [code])
            ph = ", ".join(f":fc{i}" for i in range(len(family)))
            params = {f"fc{i}": c for i, c in enumerate(family)}
            share_rows = conn.execute(text(
                f"SELECT ts_code, trade_date, fd_share FROM etf_share "
                f"WHERE ts_code IN ({ph}) AND fd_share IS NOT NULL ORDER BY trade_date"
            ), params).fetchall()
            member_series = {}
            for r in share_rows:
                member_series.setdefault(r[0], []).append((_norm_date(r[1]), float(r[2])))
            agg = dict(aggregate_family_share(member_series)) if len(member_series) >= 2 else {}

            # 份额对齐到价格日期（前向填充），算 20 日变化
            s20 = np.full(len(dates), np.nan)
            vals = []
            si = 0
            keys = sorted(agg.keys())
            last = None
            for i, d in enumerate(dates):
                while si < len(keys) and keys[si] <= d:
                    last = agg[keys[si]]
                    si += 1
                vals.append(last)
                if i >= 20 and vals[i] and vals[i - 20] and vals[i - 20] > 0:
                    s20[i] = vals[i] / vals[i - 20] - 1

            vals_arr = np.array([v if v is not None else np.nan for v in vals], dtype=float)
            events, active = locator_events(dd, s20, vals_arr)
            ev_list = []
            for i in events:
                fwd60 = None
                if i + 61 < len(closes):
                    fwd60 = round(float(closes[i + 60] / closes[i] - 1) * 100, 2)
                ev_list.append({
                    "date": dates[i], "drawdown": round(float(dd[i]) * 100, 1),
                    "share_20d_pct": round(float(s20[i]) * 100, 2) if not np.isnan(s20[i]) else None,
                    "fwd_60d_pct": fwd60,
                })

            tail = slice(-500, None)
            out.append({
                "code": code, "name": name,
                "series": [
                    {"date": d, "close": round(float(c), 3),
                     "drawdown": round(float(x) * 100, 2)}
                    for d, c, x in zip(dates[tail], closes[tail], dd[tail])
                ],
                "share_series": [
                    {"date": d, "chg20_pct": round(float(x) * 100, 2)}
                    for d, x in zip(dates[tail], s20[tail]) if not np.isnan(x)
                ],
                "events": ev_list[-8:],
                "current": {
                    "drawdown_pct": round(float(dd[-1]) * 100, 2),
                    "share_20d_pct": round(float(s20[-1]) * 100, 2) if not np.isnan(s20[-1]) else None,
                    "active": active,
                },
            })
    finally:
        conn.close()
    return {"indices": out}


def build_thermometer() -> dict:
    from src.core.db_manager_postgresql import get_conn
    conn = get_conn()
    try:
        valuation = compute_valuation_panel(conn)
        trend = compute_trend_panel(conn)
        panic = compute_panic_panel(conn)
        volatility = compute_volatility_panel(conn)
        family_flow = compute_family_flow_panel(conn)

        pcts = [i["pe_pct"] for i in valuation["indices"] if i.get("pe_pct") is not None]
        val_median = float(np.median(pcts)) if pcts else None
        triggered = bool(panic.get("market") and panic["market"]["current"]["triggered"])
        position = compute_position_composite(
            conn, volatility.get("target_mult"), triggered, val_median
        )

        return {
            "date": trend["indices"][0]["date"] if trend["indices"] else None,
            "valuation": valuation,
            "valuation_median_pe_pct": round(val_median, 1) if val_median is not None else None,
            "trend": trend,
            "panic": panic,
            "volatility": volatility,
            "family_flow": family_flow,
            "position": position,
        }
    finally:
        conn.close()
