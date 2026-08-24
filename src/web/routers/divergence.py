"""Price × share-flow divergence analysis (价格×份额 背离分析).

For every tracked ETF (5 index + 32 sector) and a lookback window
(5/10/20/60 trading days), compute:
- price_chg_pct : window price change on forward-adjusted closes (%)
- share_chg_pct : window change of fund shares fd_share (%, 万份)
- net_inflow    : share_chg_qty × latest close → 资金口径 (万元),
                  comparable across ETFs unlike raw share counts
- divergence    : ABSOLUTE tag — "risk" (价涨份额缩) / "lurk" (价跌份额增) /
                  "none" (共振或走平)
- risk_streak / lurk_streak : consecutive trading days of that divergence
- rank_gap      : |price-change rank − share-change rank| across the universe
- quadrant      : ABSOLUTE quadrant from the SAME raw window as the scatter
                  (price sign × share sign): 1 强势 / 2 潜伏 / 3 撤离 / 4 风险
- factor_quadrant : RELATIVE flow×momentum quadrant from factor_daily (sector
                  only) — different lens (EWMA share slope × vol-adjusted
                  momentum), shown separately so chip and bubble position can
                  never disagree

Unlike the cross-sectional quadrant model (rank-Z by construction splits the
universe symmetrically, e.g. 8/8/8/8 for 32 ETFs), the divergence tag here is
absolute: an ETF whose price rises while shares shrink is flagged regardless
of what peers do — the "指数涨、份额跌" case.
"""
import asyncio
import logging

import pandas as pd
from fastapi import APIRouter
from sqlalchemy import text

from src.web.services.cache import _cached_persistent
from src.core.db_manager_postgresql import get_conn, bind_inlist
from config.config import INDEX_ETF, SECTOR_ETF, INDEX_ETF_FAMILY
from src.analysis.family import aggregate_family_share
from src.data_fetchers.tushare_fetcher import _apply_etf_adj

logger = logging.getLogger(__name__)

router = APIRouter()

VALID_WINDOWS = (5, 10, 20, 60)

# (table, code→name map, universe tag) — index ETFs first so consumers can
# tell them apart without another lookup.
SOURCES = (
    ("index_etf_daily", INDEX_ETF, "index"),
    ("sector_etf_daily", SECTOR_ETF, "sector"),
)


async def _async_cached(cache_key, compute_fn, max_age_hours):
    """Run sync _cached_persistent in a thread to avoid blocking the event loop."""
    return await asyncio.to_thread(_cached_persistent, cache_key, compute_fn, max_age_hours)


def _fetch_price_frames(conn, window: int):
    """Last (window+1) daily bars per ETF as {code: (df_adj, raw_close, amount)}.

    _apply_etf_adj divides by the latest adj factor, so ratios inside the
    window match full-history adjustment — safe on a short slice.
    """
    frames = {}
    n = window + 1
    for table, code_map, _tag in SOURCES:
        codes = list(code_map.keys())
        if not codes:
            continue
        placeholders, params = bind_inlist(codes, prefix="dp_")
        params["n"] = n
        rows = conn.execute(
            text(f"""
                WITH ranked AS (
                    SELECT ts_code, trade_date, open, high, low, close, pre_close,
                           pct_chg, vol, amount,
                           ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) as rn
                    FROM {table}
                    WHERE ts_code IN ({placeholders})
                )
                SELECT ts_code, trade_date, open, high, low, close, pre_close,
                       pct_chg, vol, amount
                FROM ranked WHERE rn <= :n
            """),
            params,
        ).fetchall()
        if not rows:
            continue
        cols = ["ts_code", "trade_date", "open", "high", "low", "close",
                "pre_close", "pct_chg", "vol", "amount"]
        df_all = pd.DataFrame(rows, columns=cols)
        for code, group in df_all.groupby("ts_code"):
            group = group.sort_values("trade_date").reset_index(drop=True)
            raw_close = float(group["close"].iloc[-1]) if pd.notna(group["close"].iloc[-1]) else None
            amount = float(group["amount"].iloc[-1]) if pd.notna(group["amount"].iloc[-1]) else None
            frames[code] = (_apply_etf_adj(group, code), raw_close, amount)
    return frames


def _fetch_share_series(conn, codes, window: int, max_date):
    """Last (window+1) share points per ETF (trade_date <= max_date), ascending."""
    series = {}
    if not codes or not max_date:
        return series
    placeholders, params = bind_inlist(codes, prefix="ds_")
    params["n"] = window + 1
    params["maxd"] = max_date
    rows = conn.execute(
        text(f"""
            WITH ranked AS (
                SELECT ts_code, trade_date, fd_share,
                       ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) as rn
                FROM etf_share
                WHERE ts_code IN ({placeholders})
                  AND trade_date <= :maxd
                  AND fd_share IS NOT NULL
            )
            SELECT ts_code, trade_date, fd_share FROM ranked WHERE rn <= :n
        """),
        params,
    ).fetchall()
    for code, date, share in rows:
        series.setdefault(code, []).append((str(date), float(share)))
    for code in series:
        series[code].sort(key=lambda x: x[0])
    return series


def _fetch_quadrants(conn):
    """Latest relative quadrant per sector ETF from factor_daily (optimized)."""
    quadrants = {}
    try:
        row = conn.execute(text(
            "SELECT MAX(trade_date) FROM factor_daily WHERE preset_id = 'optimized'"
        )).fetchone()
        if row and row[0]:
            frows = conn.execute(text(
                "SELECT etf_code, quadrant FROM factor_daily "
                "WHERE preset_id = 'optimized' AND trade_date = :d"
            ), {"d": row[0]}).fetchall()
            for fr in frows:
                if fr[1] is not None:
                    quadrants[fr[0]] = int(fr[1])
    except Exception as exc:
        logger.warning("Failed to load factor quadrants: %s", exc)
    return quadrants


def _fetch_quadrant_stats(conn, window: int, days: int = 60, horizon: int = 15) -> dict:
    """近 N 日各象限（与散点同口径：窗口价格×份额符号）的平均前瞻收益。

    直接用 raw 窗口口径在面板上重算，而不是复用因子象限的 quadrant_perf——
    后者是另一套坐标系（EWMA份额斜率×波动调整动量），贴在 raw 象限的散点
    角上会再次产生"标签与位置两张皮"的问题。
    """
    stats = {}
    try:
        import numpy as np
        from src.analysis.family import aggregate_family_share
        from config.config import INDEX_ETF_FAMILY

        n_need = window + horizon + days + 5
        frames = {}
        for table, code_map, _tag in SOURCES:
            codes = list(code_map.keys())
            ph, params = bind_inlist(codes, prefix="qs_")
            params["n"] = n_need
            rows = conn.execute(text(f"""
                WITH ranked AS (
                    SELECT ts_code, trade_date, close,
                           ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) as rn
                    FROM {table} WHERE ts_code IN ({ph})
                )
                SELECT r.ts_code, r.trade_date,
                       r.close * COALESCE(a.adj_factor, 1)
                         / COALESCE((SELECT MAX(adj_factor) FROM etf_adj_factor
                                 WHERE ts_code = r.ts_code), 1) AS close
                FROM ranked r
                LEFT JOIN etf_adj_factor a
                       ON a.ts_code = r.ts_code AND a.trade_date = r.trade_date
                WHERE r.rn <= :n
            """), params).fetchall()
            for code, d, c in rows:
                frames.setdefault(code, {})[str(d)[:10]] = float(c)

        # 份额（含宽基家族聚合），前向填充对齐到价格日期
        fam_codes = set()
        for code in frames:
            fam_codes.update(INDEX_ETF_FAMILY.get(code, []))
        share_map_all = {}
        all_share_codes = sorted(set(frames.keys()) | fam_codes)
        if all_share_codes:
            ph, params = bind_inlist(all_share_codes, prefix="qsh_")
            rows = conn.execute(text(f"""
                SELECT ts_code, trade_date, fd_share FROM etf_share
                WHERE ts_code IN ({ph}) AND fd_share IS NOT NULL
            """), params).fetchall()
            member_series = {}
            for code, d, v in rows:
                member_series.setdefault(code, []).append((str(d)[:10], float(v)))
            for code in frames:
                members = INDEX_ETF_FAMILY.get(code, [code])
                ms = {m: member_series.get(m, []) for m in members if member_series.get(m)}
                share_map_all[code] = dict(aggregate_family_share(ms)) if len(ms) >= 2 else dict(ms.get(code, []))

        # 统一交易日轴（并集升序）
        all_dates = sorted({d for f in frames.values() for d in f})
        if len(all_dates) < n_need // 2:
            return stats

        acc = {q: {"ret": []} for q in (1, 2, 3, 4)}
        eval_dates = all_dates[-(days + 1):-horizon - 1]
        d_idx = {d: i for i, d in enumerate(all_dates)}
        for code, closes in frames.items():
            shares = share_map_all.get(code, {})
            closes_v = np.array(
                [closes.get(d) if closes.get(d) is not None else np.nan for d in all_dates]
            )
            # 份额前向填充对齐到价格日
            s_last = None
            s_aligned = []
            for d in all_dates:
                if d in shares:
                    s_last = shares[d]
                s_aligned.append(s_last)
            shares_v = np.array([s if s is not None else np.nan for s in s_aligned], dtype=float)

            pchg = np.full(len(all_dates), np.nan)
            pchg[window:] = closes_v[window:] / closes_v[:-window] - 1
            schg = np.full(len(all_dates), np.nan)
            schg[window:] = shares_v[window:] / shares_v[:-window] - 1

            for d in eval_dates:
                j = d_idx[d]
                p, s = pchg[j], schg[j]
                k_entry, k_exit = j + 1, j + 1 + horizon
                if k_exit >= len(closes_v):
                    continue
                entry, exit_c = closes_v[k_entry], closes_v[k_exit]
                if not (np.isfinite(p) and np.isfinite(s) and p != 0 and s != 0):
                    continue
                if not (np.isfinite(entry) and entry > 0 and np.isfinite(exit_c)):
                    continue
                fwd = exit_c / entry - 1
                q = 1 if (p > 0 and s > 0) else 2 if (p < 0 and s > 0) else 4 if (p > 0 and s < 0) else 3
                acc[q]["ret"].append(fwd)

        n_dates = max(len(eval_dates), 1)
        for q, a in acc.items():
            if a["ret"]:
                stats[q] = {
                    "avg_fwd_15d_pct": round(float(np.mean(a["ret"])) * 100, 2),
                    "avg_etf_count": round(len(a["ret"]) / n_dates, 1),
                    "days": n_dates,
                }
    except Exception as exc:
        logger.warning("Failed to compute raw quadrant stats: %s", exc)
    return stats


def _streaks(prices, shares):
    """Consecutive-day streaks of each absolute divergence, ending at the latest day.

    prices: [(date, daily pct_chg)] ascending; shares: [(date, value)] ascending.
    Share values are forward-filled onto price dates (share series may lag or
    lead by a day). Returns (risk_streak, lurk_streak).
    """
    aligned = []
    si = 0
    last_share = None
    for date, pct in prices:
        while si < len(shares) and shares[si][0] <= date:
            last_share = shares[si][1]
            si += 1
        aligned.append((pct, last_share))
    risk = lurk = 0
    for i in range(len(aligned) - 1, 0, -1):
        pct, share_now = aligned[i]
        _, share_prev = aligned[i - 1]
        if pct is None or share_now is None or share_prev is None:
            break
        if pct > 0 and share_now < share_prev:
            risk += 1
        elif pct < 0 and share_now > share_prev:
            lurk += 1
        else:
            break
    return risk, lurk


def _compute_divergence(window: int):
    if window not in VALID_WINDOWS:
        window = 10
    items = []
    with get_conn() as conn:
        frames = _fetch_price_frames(conn, window)
        if not frames:
            return {"date": None, "window": window, "items": []}

        all_codes = list(frames.keys())
        max_date = max(str(df["trade_date"].iloc[-1]) for df, _, _ in frames.values())
        # 宽基ETF连同家族成员一起取份额（聚合消除工具轮动假信号）
        fetch_codes = list(all_codes)
        for code in all_codes:
            fetch_codes.extend(INDEX_ETF_FAMILY.get(code, []))
        shares = _fetch_share_series(conn, sorted(set(fetch_codes)), window, max_date)
        quadrants = _fetch_quadrants(conn)
        quadrant_stats = _fetch_quadrant_stats(conn, window)

        for table, code_map, tag in SOURCES:
            for code, name in code_map.items():
                entry = frames.get(code)
                if entry is None:
                    continue
                df, raw_close, amount = entry
                share_series = shares.get(code, [])

                # 宽基：用同指数家族聚合份额替换单只份额（消除轮动搬家）
                family_members = None
                if tag == "index" and code in INDEX_ETF_FAMILY:
                    member_series = {
                        m: s for m, s in (
                            (m, shares.get(m, [])) for m in INDEX_ETF_FAMILY[code]
                        ) if s
                    }
                    if len(member_series) >= 2:
                        agg = aggregate_family_share(member_series)
                        if agg:
                            share_series = agg
                            family_members = len(member_series)

                price_chg_pct = None
                if len(df) > window and df["close"].iloc[-1 - window]:
                    base = float(df["close"].iloc[-1 - window])
                    last = float(df["close"].iloc[-1])
                    if base > 0:
                        price_chg_pct = round((last / base - 1) * 100, 2)

                share_chg_pct = None
                share_chg_qty = None
                if len(share_series) > window:
                    latest = share_series[-1][1]
                    ago = share_series[-1 - window][1]
                    if ago > 0:
                        share_chg_pct = round((latest / ago - 1) * 100, 2)
                        share_chg_qty = round(latest - ago, 2)

                # 资金口径：万份 × 元 = 万元（raw close 作单位净值近似）
                net_inflow = None
                if share_chg_qty is not None and raw_close:
                    net_inflow = round(share_chg_qty * raw_close, 2)

                divergence = "none"
                quadrant = None
                if price_chg_pct is not None and share_chg_pct is not None:
                    if price_chg_pct > 0 and share_chg_pct < 0:
                        divergence = "risk"
                    elif price_chg_pct < 0 and share_chg_pct > 0:
                        divergence = "lurk"
                    # 与散点图同口径的绝对象限（价格符号×份额符号）
                    if price_chg_pct != 0 and share_chg_pct != 0:
                        p_up, s_up = price_chg_pct > 0, share_chg_pct > 0
                        if p_up and s_up:
                            quadrant = 1      # 强势：价涨份额增
                        elif s_up:
                            quadrant = 2      # 潜伏：价跌份额增
                        elif p_up:
                            quadrant = 4      # 风险：价涨份额缩
                        else:
                            quadrant = 3      # 撤离：价跌份额缩

                prices = [
                    (str(r.trade_date), float(r.pct_chg) if pd.notna(r.pct_chg) else None)
                    for r in df.itertuples()
                ]
                risk_streak, lurk_streak = _streaks(prices, share_series)

                items.append({
                    "ts_code": code,
                    "name": name,
                    "type": tag,
                    "price_chg_pct": price_chg_pct,
                    "share_chg_pct": share_chg_pct,
                    "share_chg_qty": share_chg_qty,
                    "nav": raw_close,
                    "net_inflow": net_inflow,
                    "amount": amount,
                    "divergence": divergence,
                    "risk_streak": risk_streak,
                    "lurk_streak": lurk_streak,
                    "rank_gap": None,
                    "quadrant": quadrant,
                    "factor_quadrant": quadrants.get(code),
                    "family_members": family_members,
                })

    # Cross-universe ranks → rank_gap (relative divergence strength)
    valid = [it for it in items
             if it["price_chg_pct"] is not None and it["share_chg_pct"] is not None]
    if len(valid) >= 2:
        by_price = sorted(valid, key=lambda it: it["price_chg_pct"], reverse=True)
        by_share = sorted(valid, key=lambda it: it["share_chg_pct"], reverse=True)
        price_rank = {it["ts_code"]: i for i, it in enumerate(by_price, 1)}
        share_rank = {it["ts_code"]: i for i, it in enumerate(by_share, 1)}
        for it in items:
            if it["ts_code"] in price_rank:
                it["rank_gap"] = abs(price_rank[it["ts_code"]] - share_rank[it["ts_code"]])

    items.sort(key=lambda it: (it["rank_gap"] is None, -(it["rank_gap"] or 0)))
    return {
        "date": max_date.replace("-", ""),
        "window": window,
        "items": items,
        "quadrant_stats": quadrant_stats,
    }


@router.get("/api/divergence")
async def api_divergence(window: int = 10):
    return await _async_cached(
        f"divergence_w{window}",
        lambda: _compute_divergence(window),
        max_age_hours=4,
    )
