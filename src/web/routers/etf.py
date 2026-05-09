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

        result.append({
            "ts_code": code,
            "name": name,
            "kline": kline_serialized,
            "shares": safe_json(pd.DataFrame(df_share) if df_share else []),
            "signal": _compute_signal(df_pd, pd.DataFrame(df_share) if df_share else pd.DataFrame()),
        })
    return result


def _compute_signal(kline_df, share_df, window=10):
    """判断ETF近期走势信号。

    逻辑：取近 window 个交易日的份额变化趋势和价格变化趋势。
    - 份额持续流入 + 价格上涨 → 强势
    - 份额持续流入 + 价格不涨/下跌 → 埋伏
    - 份额持续流出 + 价格下跌 → 撤离
    - 份额持续流出 + 价格不跌/上涨 → 风险
    - 数据不足 → 无信号
    """
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
        label = "埋伏"
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
    }


@router.get("/api/sector-etf")
async def api_sector_etf_all():
    return _cached_persistent("sector_etf_all", _compute_sector_etf_all, max_age_hours=4)


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



