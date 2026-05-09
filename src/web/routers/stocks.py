import json
import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from src.web.services.cache import _cached_persistent
from src.core.db_manager_postgresql import get_conn, query, safe_json, safe_value
from src.web.services.validators import validate_ts_code
from config.config import CYCLICAL_INDUSTRIES, DATA_DIR
from src.core.trading_calendar import now_beijing

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()

_pinyin_cache = None


def _get_pinyin_cache():
    global _pinyin_cache
    if _pinyin_cache is not None:
        return _pinyin_cache
    from pypinyin import lazy_pinyin
    stocks = query("SELECT ts_code, name FROM stock_basic")
    cache = {}
    for _, row in stocks.iterrows():
        initials = "".join([p[0] for p in lazy_pinyin(str(row["name"]))])
        cache[row["ts_code"]] = initials.lower()
    _pinyin_cache = cache
    return cache


def _ema(data, period):
    """计算 EMA"""
    if len(data) == 0:
        return []
    result = []
    k = 2.0 / (period + 1)
    start = None
    for v in data:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            result.append(None)
            continue
        if start is None:
            start = float(v)
            result.append(start)
        else:
            start = float(v) * k + start * (1 - k)
            result.append(start)
    return result


@router.get("/stocks", response_class=HTMLResponse)
async def page_stocks(request: Request):
    return templates.TemplateResponse("stocks.html", {"request": request})


@router.get("/stock", response_class=HTMLResponse)
@router.get("/stock/", response_class=HTMLResponse)
async def page_stock_search(request: Request):
    return templates.TemplateResponse("stock_detail.html", {"request": request})


@router.get("/stock/{ts_code}", response_class=HTMLResponse)
async def page_stock_detail(ts_code: str, request: Request):
    return templates.TemplateResponse("stock_detail.html", {"request": request})


def _compute_stocks_volatility():
    try:
        vol_df = query("""
            WITH recent_dates AS (
                SELECT DISTINCT trade_date FROM stock_daily
                ORDER BY trade_date DESC LIMIT 30
            )
            SELECT ts_code, pct_chg, trade_date
            FROM stock_daily
            WHERE trade_date IN (SELECT trade_date FROM recent_dates)
              AND pct_chg IS NOT NULL
        """)
        if len(vol_df) == 0:
            return {"high_volatility": [], "low_volatility": []}

        vol_df["abs_pct"] = vol_df["pct_chg"].abs()
        vol_df = vol_df.sort_values(["ts_code", "trade_date"])
        vol_df["rn"] = vol_df.groupby("ts_code").cumcount(ascending=False)
        vol_df = vol_df[vol_df["rn"] < 20]

        vol_stats = vol_df.groupby("ts_code")["abs_pct"].std().reset_index()
        vol_stats.columns = ["ts_code", "volatility"]
        vol_stats = vol_stats.dropna().sort_values("volatility", ascending=False)

        stock_info = query("SELECT ts_code, name, industry FROM stock_basic")
        merged = vol_stats.merge(stock_info, on="ts_code", how="inner")

        latest_price = query("""
            SELECT d.ts_code, d.close, d.pct_chg
            FROM stock_daily d
            WHERE d.trade_date = (SELECT MAX(trade_date) FROM stock_daily)
        """)
        if len(latest_price) > 0:
            merged = merged.merge(latest_price, on="ts_code", how="left")

        return {"high_volatility": safe_json(merged.head(10)),
                "low_volatility": safe_json(merged.tail(10))}
    except Exception as e:
        return {"high_volatility": [], "low_volatility": [], "error": str(e)}


@router.get("/api/stocks/volatility")
async def api_stocks_volatility():
    return _cached_persistent("stocks_volatility", _compute_stocks_volatility, max_age_hours=4)


def _compute_stocks_gainers():
    try:
        daily = query("""
            WITH recent_dates AS (
                SELECT DISTINCT trade_date FROM stock_daily
                ORDER BY trade_date DESC LIMIT 30
            )
            SELECT d.ts_code, d.trade_date, d.close, d.pct_chg,
                   b.name, b.industry
            FROM stock_daily d
            JOIN stock_basic b ON d.ts_code = b.ts_code
            WHERE d.trade_date IN (SELECT trade_date FROM recent_dates)
              AND d.close IS NOT NULL
        """)
        if len(daily) == 0:
            return {"top_gainers": [], "top_losers": []}
        daily["close"] = pd.to_numeric(daily["close"], errors="coerce")

        def calc_chg(group):
            if len(group) < 2:
                return pd.Series({"cum_chg": 0, "latest_close": group["close"].iloc[0]})
            sorted_g = group.sort_values("trade_date")
            start_price = float(sorted_g["close"].iloc[0])
            end_price = float(sorted_g["close"].iloc[-1])
            return pd.Series({
                "cum_chg": (end_price - start_price) / start_price * 100 if start_price > 0 else 0,
                "latest_close": end_price,
            })

        result = daily.groupby("ts_code").apply(calc_chg, include_groups=False).reset_index()
        info = daily.groupby("ts_code").agg({"name": "first", "industry": "first"}).reset_index()
        result = result.merge(info, on="ts_code", how="left")
        result = result.sort_values("cum_chg", ascending=False)

        return {"top_gainers": safe_json(result.head(10)),
                "top_losers": safe_json(result.tail(10))}
    except Exception as e:
        return {"top_gainers": [], "top_losers": [], "error": str(e)}


@router.get("/api/stocks/gainers")
async def api_stocks_gainers():
    return _cached_persistent("stocks_gainers", _compute_stocks_gainers, max_age_hours=4)


def _compute_stocks_fundamental():
    try:
        latest_row = query("SELECT MAX(trade_date) as md FROM stock_daily_basic")
        if len(latest_row) == 0 or not latest_row.iloc[0]["md"]:
            return {"error": "暂无每日估值数据。请运行: python fetch_data.py --funda",
                    "trade_date": "", "stocks": []}
        latest_date = latest_row.iloc[0]["md"]

        fina_cnt = query("SELECT COUNT(*) as cnt FROM stock_fina_indicator")
        if len(fina_cnt) == 0 or fina_cnt.iloc[0]["cnt"] == 0:
            return {"error": "暂无财务指标数据（需Tushare 2000+积分）。请运行: python fetch_data.py --funda",
                    "trade_date": "", "stocks": []}

        val = query("""
            SELECT ts_code, pe_ttm, pb, total_mv
            FROM stock_daily_basic WHERE trade_date = :p0
        """, {"p0": latest_date})

        fina = query("""
            SELECT f.ts_code, f.end_date, f.roe, f.netprofit_yoy, f.tr_yoy,
                   f.grossprofit_margin, f.netprofit_margin, f.eps,
                   f.debt_to_assets, f.current_ratio
            FROM stock_fina_indicator f
            INNER JOIN (
                SELECT ts_code, MAX(end_date) as max_ed
                FROM stock_fina_indicator
                GROUP BY ts_code
            ) latest ON f.ts_code = latest.ts_code AND f.end_date = latest.max_ed
        """)

        info = query("SELECT ts_code, name, industry FROM stock_basic")

        if len(val) == 0 or len(fina) == 0:
            return {"error": "数据不完整，无法评分", "trade_date": latest_date, "stocks": []}

        merged = val.merge(info, on="ts_code", how="inner")
        merged = merged.merge(fina, on="ts_code", how="inner")

        for col in ["pe_ttm", "pb", "total_mv", "roe", "netprofit_yoy",
                     "tr_yoy", "grossprofit_margin", "netprofit_margin"]:
            merged[col] = pd.to_numeric(merged[col], errors="coerce")

        merged = merged[
            (merged["total_mv"] >= 200) &
            (merged["pe_ttm"] > 0) &
            (merged["pb"] > 0) &
            (merged["roe"].notna()) &
            (merged["tr_yoy"].notna()) &
            (merged["netprofit_yoy"].notna()) &
            (merged["grossprofit_margin"].notna())
        ]

        if len(merged) == 0:
            return {"error": "筛选后无符合条件的股票", "trade_date": latest_date, "stocks": []}

        merged["is_cyclical"] = merged["industry"].isin(CYCLICAL_INDUSTRIES)

        def _norm(series):
            s_min, s_max = series.min(), series.max()
            if s_max == s_min:
                return pd.Series(50.0, index=series.index)
            return ((series - s_min) / (s_max - s_min) * 100).fillna(0)

        merged["roe_score"] = _norm(merged["roe"])
        merged["margin_score"] = _norm(merged["grossprofit_margin"])
        merged["tr_yoy_score"] = _norm(merged["tr_yoy"])
        merged["profit_yoy_score"] = _norm(merged["netprofit_yoy"])

        merged["growth_score"] = (merged["tr_yoy_score"] * 0.5 +
                                  merged["profit_yoy_score"] * 0.5)

        merged["profitability_score"] = (merged["roe_score"] * 0.6 +
                                         merged["margin_score"] * 0.4)

        def _val_score_col(group):
            metric = "pb" if group["is_cyclical"].iloc[0] else "pe_ttm"
            vals = group[metric].rank(pct=True)
            return (1 - vals) * 100

        merged["valuation_score"] = (
            merged.groupby("industry", group_keys=False)
            .apply(_val_score_col, include_groups=False)
            .reset_index(level=0, drop=True)
        )

        merged["composite_score"] = (
            merged["growth_score"] * 0.30 +
            merged["profitability_score"] * 0.30 +
            merged["valuation_score"] * 0.40
        )

        merged = merged.sort_values("composite_score", ascending=False).head(30)

        output_cols = [
            "ts_code", "name", "industry", "composite_score",
            "growth_score", "profitability_score", "valuation_score",
            "pe_ttm", "pb", "total_mv", "tr_yoy", "netprofit_yoy",
            "roe", "grossprofit_margin", "is_cyclical",
        ]
        result = merged[output_cols].copy()
        result = result.round(2)
        result["is_cyclical"] = result["is_cyclical"].map({True: 1, False: 0})
        result["total_mv"] = (result["total_mv"] / 10000).round(2)

        return {"trade_date": latest_date, "stocks": safe_json(result)}
    except Exception as e:
        return {"error": str(e), "trade_date": "", "stocks": []}


@router.get("/api/stocks/fundamental")
async def api_stocks_fundamental():
    return _cached_persistent("stocks_fundamental", _compute_stocks_fundamental, max_age_hours=4)


def _compute_stocks_lhb():
    conn = None
    try:
        conn = get_conn()
        row = conn.execute(
            text("SELECT data_json FROM lhb_data ORDER BY trade_date DESC LIMIT 1")
        ).fetchone()
        if row:
            cached = json.loads(row[0])
            if cached.get('data') and len(cached['data']) > 0:
                first = cached['data'][0]
                has_name = first.get('股票名称') or first.get('名称') or first.get('name')
                if has_name:
                    name_keys = ['股票名称', '名称', 'name']
                    st_pattern = re.compile(r'^[*]*ST', re.IGNORECASE)
                    filtered_data = [
                        item for item in cached['data']
                        if not any(
                            st_pattern.match(str(item.get(key, '')))
                            for key in name_keys if item.get(key)
                        )
                    ]
                    cached['data'] = filtered_data
                    return cached
    except Exception:
        pass
    finally:
        if conn:
            conn.close()
    csv_dir = DATA_DIR / "akshare"
    if not csv_dir.exists():
        return {"data": [], "date": "", "error": "暂无龙虎榜数据，请先更新数据"}
    files = sorted(csv_dir.glob("lhb_*.csv"))
    if not files:
        return {"data": [], "date": "", "error": "暂无龙虎榜数据，请先更新数据"}
    latest = files[-1]
    date_str = latest.stem.replace("lhb_", "")
    try:
        df = pd.read_csv(str(latest), encoding="utf-8-sig", dtype=str)

        stock_info = query("SELECT ts_code, name, industry FROM stock_basic")
        if len(stock_info) == 0:
            result = {"data": safe_json(df), "date": date_str}
            return result

        stock_info['ts_code_base'] = stock_info['ts_code'].str.replace(r'\.(SH|SZ)', '', regex=True)
        code_to_info = {}
        for _, r in stock_info.iterrows():
            code_to_info[r['ts_code_base']] = {'name': r['name'], 'industry': r['industry']}
            code_to_info[r['ts_code']] = {'name': r['name'], 'industry': r['industry']}

        code_cols = ['股票代码', '代码', 'code', 'ts_code']

        for idx, row_df in df.iterrows():
            code = None
            for col in code_cols:
                if col in df.columns and pd.notna(row_df.get(col)) and str(row_df.get(col)).strip():
                    code = str(row_df[col]).strip()
                    break

            if code:
                code_clean = code.replace('.SH', '').replace('.SZ', '')
                if code_clean in code_to_info:
                    info = code_to_info[code_clean]
                    if '股票名称' in df.columns:
                        if pd.isna(row_df.get('股票名称')) or row_df.get('股票名称') == '':
                            df.at[idx, '股票名称'] = info['name']
                    if '名称' in df.columns:
                        if pd.isna(row_df.get('名称')) or row_df.get('名称') == '':
                            df.at[idx, '名称'] = info['name']
                    if '行业' in df.columns:
                        if pd.isna(row_df.get('行业')) or row_df.get('行业') == '':
                            df.at[idx, '行业'] = info['industry']

        name_cols = ['股票名称', '名称', 'name']
        mask = pd.Series([True] * len(df))
        for col in name_cols:
            if col in df.columns:
                mask = mask & ~df[col].fillna('').str.contains(r'^[*]*ST', case=False, regex=True)
        df = df[mask]

        result = {"data": safe_json(df), "date": date_str}
        conn = None
        try:
            conn = get_conn()
            conn.execute(
                text("""INSERT INTO lhb_data (trade_date, data_json)
                   VALUES (:trade_date, :data_json)
                   ON CONFLICT (trade_date)
                   DO UPDATE SET data_json = EXCLUDED.data_json"""),
                {"trade_date": date_str, "data_json": json.dumps(result, ensure_ascii=False, default=str)},
            )
            conn.commit()
        except Exception:
            pass
        finally:
            if conn:
                conn.close()
        return result
    except Exception as e:
        return {"data": [], "date": date_str, "error": str(e)}


@router.get("/api/stocks/lhb")
async def api_stocks_lhb():
    return _cached_persistent("stocks_lhb", _compute_stocks_lhb, max_age_hours=4)


@router.get("/api/search")
async def api_search(q: str = ""):
    if not q or len(q) < 1:
        return []
    q = q.strip().lower()
    df = query(
        "SELECT ts_code, name, industry FROM stock_basic "
        "WHERE ts_code ILIKE :p0 OR name ILIKE :p1",
        {"p0": q + "%", "p1": "%" + q + "%"},
    )
    if len(df) == 0:
        df = query("SELECT ts_code, name, industry FROM stock_basic")
    if len(df) == 0:
        return []
    pinyin_map = _get_pinyin_cache()

    results = []
    for _, row in df.iterrows():
        code = str(row["ts_code"])
        name = str(row["name"])
        py = pinyin_map.get(code, "")
        score = 0
        if code.startswith(q) or code.replace(".", "").startswith(q):
            score = 100
        elif q in name:
            score = 80
        elif py.startswith(q):
            score = 60
        elif q in py:
            score = 40
        if score > 0:
            results.append({"ts_code": code, "name": name,
                            "industry": str(row.get("industry", "") or ""), "score": score})
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:10]


@router.get("/api/stock/{ts_code}")
async def api_stock_detail(ts_code: str):
    if not validate_ts_code(ts_code):
        return JSONResponse(
            {"error": "无效的股票代码格式，应为: 6位数字.SH/SZ/BJ"},
            status_code=400
        )

    # 1. 基本信息
    info_df = query("SELECT ts_code, name, industry FROM stock_basic WHERE ts_code=:p0", {"p0": ts_code})
    if len(info_df) == 0:
        return {"error": "未找到该股票"}
    info = info_df.iloc[0]

    # 2. 最近 60 个交易日 K 线
    kline_df = query(
        "SELECT trade_date, open, high, low, close, vol, amount, pct_chg "
        "FROM stock_daily WHERE ts_code=:p0 ORDER BY trade_date DESC LIMIT 60",
        {"p0": ts_code},
    )
    if len(kline_df) == 0:
        return {"error": "暂无日线数据"}
    kline_df = kline_df.iloc[::-1].reset_index(drop=True)
    for col in ["open", "high", "low", "close", "vol", "amount", "pct_chg"]:
        kline_df[col] = pd.to_numeric(kline_df[col], errors="coerce")

    closes = kline_df["close"].values
    dates = kline_df["trade_date"].tolist()

    # 3. 布林带 (20日 SMA ± 2σ)
    period = 20
    sma, upper, lower = [], [], []
    for i in range(len(closes)):
        if i < period - 1:
            sma.append(None)
            upper.append(None)
            lower.append(None)
        else:
            window = closes[i - period + 1:i + 1]
            m = float(np.mean(window))
            s = float(np.std(window, ddof=0))
            sma.append(round(m, 3))
            upper.append(round(m + 2 * s, 3))
            lower.append(round(m - 2 * s, 3))

    # 4. MACD (12, 26, 9)
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    dif = [float(a - b) if (a is not None and b is not None) else None
           for a, b in zip(ema12, ema26)]
    dea = _ema([d for d in dif if d is not None], 9)
    dea_aligned = []
    j = 0
    for d in dif:
        if d is not None:
            dea_aligned.append(dea[j] if j < len(dea) else None)
            j += 1
        else:
            dea_aligned.append(None)
    macd_bar = [round(2 * (d - e), 4) if (d is not None and e is not None) else None
                for d, e in zip(dif, dea_aligned)]

    # 5. 成交量百分位
    vols = kline_df["vol"].values
    vol_pct = []
    for i in range(len(vols)):
        if i < 4:
            vol_pct.append(None)
        else:
            window_v = vols[:i + 1]
            rank = float(np.sum(window_v[-1] >= window_v)) / len(window_v) * 100
            vol_pct.append(round(rank, 1))

    # 6.最新估值
    val_df = query(
        "SELECT pe_ttm, pb, total_mv, turnover_rate FROM stock_daily_basic "
        "WHERE ts_code=:p0 ORDER BY trade_date DESC LIMIT 1", {"p0": ts_code}
    )
    valuation = safe_json(val_df)[0] if len(val_df) > 0 else {}

    # 7. 最新财务指标
    fina_df = query(
        "SELECT roe, netprofit_yoy, tr_yoy, grossprofit_margin, netprofit_margin, eps, "
        "debt_to_assets, current_ratio, end_date FROM stock_fina_indicator "
        "WHERE ts_code=:p0 ORDER BY end_date DESC LIMIT 1", {"p0": ts_code}
    )
    financials = safe_json(fina_df)[0] if len(fina_df) > 0 else {}

    # 8. ROE/PE 四象限 — 同行业股票
    industry = str(info.get("industry", ""))
    industry = industry if industry and industry != "nan" else ""
    quadrant = {"stocks": [], "current": None}
    if industry:
        peers = query(
            "SELECT b.ts_code, b.name, f.roe, v.pe_ttm "
            "FROM stock_basic b "
            "JOIN stock_fina_indicator f ON b.ts_code = f.ts_code "
            "JOIN (SELECT ts_code, MAX(end_date) as med FROM stock_fina_indicator GROUP BY ts_code) lm "
            "  ON f.ts_code = lm.ts_code AND f.end_date = lm.med "
            "JOIN (SELECT ts_code, pe_ttm FROM stock_daily_basic "
            "  WHERE trade_date = (SELECT MAX(trade_date) FROM stock_daily_basic)) v "
            "  ON b.ts_code = v.ts_code "
            "WHERE b.industry = :p0 AND f.roe IS NOT NULL AND v.pe_ttm > 0",
            {"p0": industry}
        )
        if len(peers) > 0:
            peers["roe"] = pd.to_numeric(peers["roe"], errors="coerce")
            peers["pe_ttm"] = pd.to_numeric(peers["pe_ttm"], errors="coerce")
            peers = peers.dropna(subset=["roe", "pe_ttm"])
            quadrant["stocks"] = safe_json(peers.head(100))
            for _, p in peers.iterrows():
                if p["ts_code"] == ts_code:
                    quadrant["current"] = {"pe_ttm": float(p["pe_ttm"]), "roe": float(p["roe"])}
                    break

    return {
        "ts_code": ts_code,
        "name": str(info["name"]),
        "industry": industry,
        "kline": safe_json(kline_df),
        "bollinger": {"sma": sma, "upper": upper, "lower": lower},
        "dif": [round(d, 4) if d is not None else None for d in dif],
        "dea": [round(d, 4) if d is not None else None for d in dea_aligned],
        "macd_bar": macd_bar,
        "vol_pct": vol_pct,
        "valuation": valuation,
        "financials": financials,
        "quadrant": quadrant,
    }
