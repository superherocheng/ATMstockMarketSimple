import logging
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from src.web.services.cache import _cached_persistent
from src.core.db_manager_postgresql import get_conn, query, safe_json
from src.core.db_manager_postgresql import get_db_manager
from config.config import INDEX_ETF, SECTOR_ETF, ANOMALY_STD_THRESHOLD
from src.core.trading_calendar import now_beijing
from src.data_fetchers.tushare_fetcher import _apply_etf_adj

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()


def _detect_anomalies(df, df_share):
    anomalies = {"price": [], "share": []}
    if len(df) > 20 and "pct_chg" in df.columns:
        pct = df["pct_chg"].dropna()
        mean_p = pct.mean()
        std_p = pct.std()
        if std_p > 0:
            mask = (pct - mean_p).abs() > ANOMALY_STD_THRESHOLD * std_p
            anomaly_rows = df.loc[mask]
            anomalies["price"] = anomaly_rows[["trade_date", "pct_chg"]].to_dict("records")

    if len(df_share) > 20 and "fd_share" in df_share.columns:
        shares = df_share["fd_share"].dropna()
        if len(shares) > 20:
            share_chg = shares.pct_change()
            # Remove first-row NaN and any inf values from zero-division
            share_chg = share_chg.replace([float('inf'), float('-inf')], float('nan')).dropna()
            if len(share_chg) > 20:
                mean_s = share_chg.mean()
                std_s = share_chg.std()
                if std_s > 0:
                    z_scores = (share_chg - mean_s).abs() / std_s
                    anomaly_mask = z_scores > ANOMALY_STD_THRESHOLD
                    anomaly_idx = anomaly_mask[anomaly_mask].index
                    if len(anomaly_idx) > 0:
                        anomaly_share = df_share.loc[anomaly_idx].copy()
                        anomaly_share["chg_pct"] = (share_chg.loc[anomaly_idx] * 100).values
                        anomaly_share["z_score"] = z_scores.loc[anomaly_idx].values
                        abs_chg = shares.diff()
                        anomaly_share["chg_abs"] = abs_chg.loc[anomaly_idx].values
                        anomalies["share"] = safe_json(anomaly_share[["trade_date", "fd_share", "chg_pct", "chg_abs", "z_score"]])
    return anomalies


@router.get("/etf", response_class=HTMLResponse)
async def page_etf(request: Request):
    return templates.TemplateResponse("etf.html", {"request": request})


@router.get("/sector", response_class=HTMLResponse)
async def page_sector(request: Request):
    return templates.TemplateResponse("sector.html", {"request": request})


def _compute_index_etf(ts_code):
    df = query(
        "SELECT ts_code, trade_date, open, high, low, close, vol, amount, pre_close, pct_chg "
        "FROM index_etf_daily WHERE ts_code=:p0 ORDER BY trade_date",
        {"p0": ts_code},
    )
    # P2.6: 应用前复权因子
    df = _apply_etf_adj(df, ts_code)

    today_str = now_beijing().strftime("%Y%m%d")
    df_share = query(
        "SELECT trade_date, fd_share FROM etf_share WHERE ts_code=:p0 AND trade_date <= :p1 ORDER BY trade_date",
        {"p0": ts_code, "p1": today_str},
    )

    anomalies = _detect_anomalies(df, df_share)

    return {
        "kline": safe_json(df),
        "shares": safe_json(df_share),
        "anomalies": anomalies,
        "name": INDEX_ETF.get(ts_code, ts_code),
    }


@router.get("/api/index-etf/{ts_code}")
async def api_index_etf(ts_code: str):
    return _cached_persistent(f"index_etf_{ts_code}", lambda: _compute_index_etf(ts_code), max_age_hours=4)


def _compute_sector_etf_all():
    today_str = now_beijing().strftime("%Y%m%d")
    codes = list(SECTOR_ETF.keys())

    # Batch-fetch all kline data in one query
    all_kline = {}
    if codes:
        placeholders = ",".join(f":c{i}" for i in range(len(codes)))
        params = {f"c{i}": c for i, c in enumerate(codes)}
        rows = query(
            f"SELECT ts_code, trade_date, open, high, low, close, vol, amount, pre_close, pct_chg "
            f"FROM sector_etf_daily WHERE ts_code IN ({placeholders}) ORDER BY ts_code, trade_date",
            params,
        )
        for _, row in rows.iterrows():
            code = row["ts_code"]
            if code not in all_kline:
                all_kline[code] = []
            all_kline[code].append(row.to_dict())

    # Batch-fetch all share data in one query
    all_shares = {}
    if codes:
        placeholders = ",".join(f":s{i}" for i in range(len(codes)))
        params = {f"s{i}": c for i, c in enumerate(codes)}
        params["today"] = today_str
        rows = query(
            f"SELECT ts_code, trade_date, fd_share FROM etf_share "
            f"WHERE ts_code IN ({placeholders}) AND trade_date <= :today ORDER BY ts_code, trade_date",
            params,
        )
        for _, row in rows.iterrows():
            code = row["ts_code"]
            if code not in all_shares:
                all_shares[code] = []
            all_shares[code].append(row.to_dict())

    # Fetch latest factor data from factor_daily (short preset)
    factor_quadrants = {}
    financial_quality = {}
    try:
        from src.core.db_manager_postgresql import get_conn
        from sqlalchemy import text
        conn = get_conn()
        row = conn.execute(text(
            "SELECT MAX(trade_date) FROM factor_daily WHERE preset_id = 'short'"
        )).fetchone()
        if row and row[0]:
            latest_fdate = row[0]
            frows = conn.execute(text(
                "SELECT etf_code, quadrant FROM factor_daily "
                "WHERE preset_id = 'short' AND trade_date = :d",
            ), {"d": latest_fdate}).fetchall()
            for fr in frows:
                factor_quadrants[fr[0]] = int(fr[1])
            # V4: Load financial quality data for sector display
            # Primary source: financial_factor table (all 17 ETFs, latest calc_date)
            try:
                ffrows = conn.execute(text("""
                    SELECT f.ts_code, f.f_roe, f.f_pb_pct, f.f_earnings_yoy, f.f_quality
                    FROM financial_factor f
                    WHERE f.calc_date = (SELECT MAX(calc_date) FROM financial_factor)
                """)).fetchall()
                for ffr in ffrows:
                    financial_quality[ffr[0]] = {
                        "z_quality": float(ffr[4]) if ffr[4] else 0,
                        "f_quality": float(ffr[4]) if ffr[4] else 0,
                        "f_roe": float(ffr[1]) if ffr[1] else 0,
                        "f_pb_pct": float(ffr[2]) if ffr[2] else 0,
                        "f_earnings_yoy": float(ffr[3]) if ffr[3] else 0,
                    }
                # Override z_quality from factor_daily (cross-sectionally Z-scored) when available
                try:
                    qrows = conn.execute(text("""
                        SELECT etf_code, z_quality FROM factor_daily
                        WHERE preset_id = 'short' AND trade_date = :d AND z_quality IS NOT NULL
                    """), {"d": latest_fdate}).fetchall()
                    for qr in qrows:
                        if qr[0] in financial_quality:
                            financial_quality[qr[0]]["z_quality"] = float(qr[1]) if qr[1] else 0
                except Exception:
                    pass
            except Exception:
                pass  # financial_factor table may not exist yet
        conn.close()
    except Exception:
        pass  # Factor data may not exist yet — fallback only

    result = []
    for code, name in SECTOR_ETF.items():
        df = all_kline.get(code, [])
        df_share = all_shares.get(code, [])
        # Apply forward-adjusted factors
        if df:
            df_pd = pd.DataFrame(df)
            df_pd = _apply_etf_adj(df_pd, code)
            kline_serialized = safe_json(df_pd)
        else:
            df_pd = pd.DataFrame()
            kline_serialized = []

        quadrant = factor_quadrants.get(code)
        signal = _compute_signal(
            df_pd,
            pd.DataFrame(df_share) if df_share else pd.DataFrame(),
            quadrant=quadrant,
        )

        quality_data = financial_quality.get(code, {})
        result.append({
            "ts_code": code,
            "name": name,
            "kline": kline_serialized,
            "shares": safe_json(pd.DataFrame(df_share) if df_share else []),
            "signal": signal,
            "financial_quality": {
                "z_quality": quality_data.get("z_quality", 0),
                "f_quality": quality_data.get("f_quality", 0),
                "f_roe": quality_data.get("f_roe", 0),
                "f_pb_pct": quality_data.get("f_pb_pct", 0),
                "f_earnings_yoy": quality_data.get("f_earnings_yoy", 0),
            },
        })
    return result


# Unified quadrant → signal mapping (shared across sector page & analysis page)
QUADRANT_SIGNAL_MAP = {
    1: {"tag": "strong", "label": "强势"},
    2: {"tag": "lurk",   "label": "潜伏"},
    3: {"tag": "exit",   "label": "撤离"},
    4: {"tag": "risk",   "label": "风险"},
}


def _compute_signal(kline_df, share_df, window=10, quadrant=None):
    """判断ETF近期走势信号。

    优先使用因子模型的象限数据（quadrant），无因子数据时回退到旧逻辑。
    
    旧逻辑：取近 window 个交易日的份额变化趋势和价格变化趋势。
    - 份额持续流入 + 价格上涨 → 强势
    - 份额持续流入 + 价格不涨/下跌 → 潜伏
    - 份额持续流出 + 价格下跌 → 撤离
    - 份额持续流出 + 价格不跌/上涨 → 风险
    - 数据不足 → 无信号
    
    Args:
        kline_df: K线DataFrame
        share_df: 份额DataFrame
        window: 回溯窗口（旧逻辑使用）
        quadrant: 因子模型象限值（1-4），优先使用
    
    Returns:
        dict: {"label": str, "tag": str, "share_change": float, "price_change": float}
    """
    # 优先使用因子模型象限数据
    if quadrant is not None and quadrant in QUADRANT_SIGNAL_MAP:
        q = QUADRANT_SIGNAL_MAP[quadrant]
        return {
            "label": q["label"],
            "tag": q["tag"],
            "share_change": 0,
            "price_change": 0,
            "source": "factor_model",
        }

    # 回退到旧逻辑
    if len(kline_df) < window or len(share_df) < window:
        return {"label": "--", "tag": "none"}

    recent_kline = kline_df.tail(window)
    recent_shares = share_df.tail(window)

    # 份额趋势：最近窗口期末 vs 期初
    share_vals = recent_shares["fd_share"].astype(float).values
    if share_vals[0] == 0:
        return {"label": "--", "tag": "none"}
    share_change = (share_vals[-1] - share_vals[0]) / abs(share_vals[0]) * 100

    # 价格趋势：最近窗口涨跌幅
    closes = recent_kline["close"].astype(float).values
    if closes[0] == 0:
        return {"label": "--", "tag": "none"}
    price_change = (closes[-1] - closes[0]) / abs(closes[0]) * 100

    inflow = share_change > 0
    rising = price_change > 0

    if inflow and rising:
        tag = "strong"
        label = "强势"
    elif inflow and not rising:
        tag = "lurk"
        label = "潜伏"
    elif not inflow and not rising:
        tag = "exit"
        label = "撤离"
    else:
        tag = "risk"
        label = "风险"

    return {
        "label": label,
        "tag": tag,
        "share_change": round(share_change, 2),
        "price_change": round(price_change, 2),
        "source": "fallback",
    }


@router.get("/api/sector-etf")
async def api_sector_etf_all():
    return _cached_persistent("sector_etf_all_list", _compute_sector_etf_all, max_age_hours=4)


def _compute_sector_etf_one(ts_code):
    today_str = now_beijing().strftime("%Y%m%d")
    df = query(
        "SELECT ts_code, trade_date, open, high, low, close, vol, amount, pre_close, pct_chg "
        "FROM sector_etf_daily WHERE ts_code=:p0 ORDER BY trade_date",
        {"p0": ts_code},
    )
    # P2.6: 应用前复权因子
    df = _apply_etf_adj(df, ts_code)

    df_share = query(
        "SELECT trade_date, fd_share FROM etf_share WHERE ts_code=:p0 AND trade_date <= :p1 ORDER BY trade_date",
        {"p0": ts_code, "p1": today_str},
    )

    anomalies = _detect_anomalies(df, df_share)

    return {
        "kline": safe_json(df),
        "shares": safe_json(df_share),
        "anomalies": anomalies,
        "name": SECTOR_ETF.get(ts_code, ts_code),
    }


@router.get("/api/sector-etf/{ts_code}")
async def api_sector_etf_one(ts_code: str):
    return _cached_persistent(f"sector_etf_{ts_code}", lambda: _compute_sector_etf_one(ts_code), max_age_hours=4)


def _compute_sector_cards():
    conn = get_conn()
    result = []
    try:
        for code, name in SECTOR_ETF.items():
            rows = conn.execute(
                text("SELECT trade_date, open, high, low, close, pre_close, pct_chg "
                     "FROM sector_etf_daily WHERE ts_code=:code ORDER BY trade_date DESC LIMIT 5"),
                {"code": code}
            ).fetchall()
            if not rows:
                result.append({
                    "ts_code": code, "name": name, "trade_date": "",
                    "pct_chg": 0, "close": 0, "amplitude": 0, "sparkline": [],
                })
                continue
            cols = ["trade_date", "open", "high", "low", "close", "pre_close", "pct_chg"]
            df = pd.DataFrame(rows, columns=cols)
            # P2.6: 应用前复权因子 (卡片也用调整后价格)
            df = _apply_etf_adj(df, code)
            latest = df.iloc[0]
            hi = float(latest.get("high", 0) or 0)
            lo = float(latest.get("low", 0) or 0)
            pre = float(latest.get("pre_close", 0) or 0)
            amplitude = ((hi - lo) / pre * 100) if pre > 0 else 0
            closes = [float(x) for x in df.sort_values("trade_date")["close"].tolist()]
            result.append({
                "ts_code": code,
                "name": name,
                "trade_date": str(latest.get("trade_date", "")),
                "pct_chg": round(float(latest.get("pct_chg", 0) or 0), 2),
                "close": float(latest.get("close", 0) or 0),
                "amplitude": round(amplitude, 2),
                "sparkline": closes,
            })
    finally:
        conn.close()
    return result


@router.get("/api/sector-cards")
async def api_sector_cards():
    return _cached_persistent("sector_cards", _compute_sector_cards, max_age_hours=4)


def _compute_share_std(ts_code: str):
    conn = get_conn()
    try:
        rows = conn.execute(
            text("SELECT trade_date, fd_share FROM etf_share "
                 "WHERE ts_code=:code ORDER BY trade_date DESC LIMIT 11"),
            {"code": ts_code}
        ).fetchall()
        
        if len(rows) < 10:
            return {"error": "insufficient_data"}
        
        shares = [float(r[1]) for r in reversed(rows)]
        dates = [str(r[0]) for r in reversed(rows)]
        
        share_changes = []
        for i in range(1, len(shares)):
            if shares[i-1] > 0:
                change_pct = (shares[i] - shares[i-1]) / shares[i-1] * 100
                share_changes.append(change_pct)
        
        if len(share_changes) < 9:
            return {"error": "insufficient_data"}
        
        recent_10_changes = share_changes[-10:]
        
        mean_change = sum(recent_10_changes) / len(recent_10_changes)
        variance = sum((x - mean_change) ** 2 for x in recent_10_changes) / len(recent_10_changes)
        std_change = variance ** 0.5
        
        latest_change = recent_10_changes[-1]
        z_score = (latest_change - mean_change) / std_change if std_change > 0 else 0
        
        positive_count = sum(1 for x in recent_10_changes if x > 0)
        negative_count = sum(1 for x in recent_10_changes if x < 0)
        
        return {
            "ts_code": ts_code,
            "latest_date": dates[-1],
            "std_dev": round(std_change, 4),
            "mean_change": round(mean_change, 4),
            "latest_change": round(latest_change, 4),
            "z_score": round(z_score, 2),
            "positive_days": positive_count,
            "negative_days": negative_count,
            "max_change": round(max(recent_10_changes), 4),
            "min_change": round(min(recent_10_changes), 4),
            "total_change": round(sum(recent_10_changes), 4),
        }
    finally:
        conn.close()


@router.get("/api/share-std/{ts_code}")
async def api_share_std(ts_code: str):
    return _cached_persistent(
        f"share_std_{ts_code}",
        lambda: _compute_share_std(ts_code),
        max_age_hours=4
    )


# Investment recommendation moved to analysis.py (recommendation_engine)
# This route is now handled by /api/investment-recommendation in analysis.py



