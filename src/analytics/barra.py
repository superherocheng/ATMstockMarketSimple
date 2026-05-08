"""
ATMstockMarket BARRA 多因子分析模块 v3
=======================================
v3: 迁移至PostgreSQL —— 使用连接池和并发支持，
    进一步提升分析查询性能和并发能力。

优化特性：
  - 缓存 _get_recent_trade_dates 结果（模块级变量）
  - turnover 查询限定日期范围（消除全表扫描）
  - 预计算缓存到 precomputed_cache 表（跨请求复用）
  - PostgreSQL连接池管理
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

SCRIPT_DIR = Path(__file__).resolve().parent

from src.core.trading_calendar import now_beijing
from src.core.db_manager_postgresql import init_db_manager, get_db_manager

# ── 模块级缓存 ──────────────────────────────────
_trade_dates_cache = {"dates": None, "updated": 0.0}


def _conn():
    """获取PostgreSQL连接"""
    return get_db_manager().get_connection()


def _query(sql, params=None):
    """执行查询（向量化执行）"""
    try:
        return get_db_manager().query(sql, params)
    except Exception:
        return pd.DataFrame()


def _safe_json(df):
    if df is None or len(df) == 0:
        return []
    return df.fillna("").to_dict(orient="records")


# ══════════════════════════════════════════════════
#  交易日期缓存
# ══════════════════════════════════════════════════
def _get_recent_trade_dates(n=30):
    """获取最近 n 个交易日（带 60 秒模块级缓存）"""
    import time
    now = time.time()
    if _trade_dates_cache["dates"] is not None and (now - _trade_dates_cache["updated"]) < 60:
        dates = _trade_dates_cache["dates"]
        return dates[:n] if len(dates) >= n else dates

    conn = _conn()
    rows = conn.execute(
        text("SELECT DISTINCT trade_date FROM stock_daily ORDER BY trade_date DESC LIMIT 200")
    ).fetchall()
    result = [r[0] for r in rows] if rows else []

    _trade_dates_cache["dates"] = result
    _trade_dates_cache["updated"] = now
    return result[:n] if len(result) >= n else result


# ══════════════════════════════════════════════════
#  预计算缓存
# ══════════════════════════════════════════════════
def _precomputed_get(cache_key):
    """从 precomputed_cache 读取缓存结果"""
    try:
        conn = _conn()
        row = conn.execute(
            text("SELECT data_json FROM precomputed_cache WHERE cache_key = :key"),
            {"key": cache_key}
        ).fetchone()
        if row and row[0]:
            return json.loads(row[0])
    except Exception:
        pass
    return None


def _precomputed_set(cache_key, data):
    """写入预计算缓存"""
    try:
        conn = _conn()
        conn.execute(
            text("""INSERT INTO precomputed_cache (cache_key, updated_at, data_json) 
               VALUES (:key, :updated_at, :data_json)
               ON CONFLICT (cache_key) 
               DO UPDATE SET updated_at = EXCLUDED.updated_at, data_json = EXCLUDED.data_json"""),
            {"key": cache_key, "updated_at": now_beijing().strftime("%Y-%m-%d %H:%M:%S"), "data_json": json.dumps(data, ensure_ascii=False)},
        )
        conn.commit()
    except Exception:
        pass


def _cache_key(factor_name):
    """生成包含日期的缓存 key，确保跨交易日自动失效。"""
    dates = _get_recent_trade_dates(1)
    latest = dates[0] if dates else "unknown"
    return f"barra_{factor_name}_{latest}_v2"


def _fetch_industry_daily_data(recent_dates):
    """获取行业日线数据"""
    placeholders = ",".join([f":p{i}" for i in range(len(recent_dates))])
    params = {f"p{i}": d for i, d in enumerate(recent_dates)}
    df = _query(f"""
        SELECT b.industry, d.trade_date, d.pct_chg, d.close, d.vol, d.amount
        FROM stock_daily d
        JOIN stock_basic b ON d.ts_code = b.ts_code
        WHERE b.industry IS NOT NULL AND b.industry != ''
          AND d.pct_chg IS NOT NULL
          AND d.trade_date IN ({placeholders})
    """, params)
    return df


def _aggregate_industry_daily(df):
    """聚合行业日线数据"""
    df["pct_chg"] = pd.to_numeric(df["pct_chg"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df["vol"] = pd.to_numeric(df["vol"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    industry_daily = df.groupby(["industry", "trade_date"]).agg({
        "pct_chg": "mean",
        "amount": "sum",
        "close": "last",
    }).reset_index()
    return industry_daily.sort_values(["industry", "trade_date"])


def _calculate_industry_metrics(industry, group, stock_counts):
    """计算单个行业的因子指标"""
    group = group.sort_values("trade_date")
    recent = group.tail(20)
    if len(recent) < 5:
        return None

    momentum_5 = recent.tail(5)["pct_chg"].sum()
    momentum_20 = recent["pct_chg"].sum()
    volatility_20 = recent["pct_chg"].std()
    avg_amount = recent["amount"].mean()
    latest_date_ind = recent.iloc[-1]["trade_date"]

    return_risk_ratio = momentum_20 / volatility_20 if volatility_20 > 0 else 0

    if momentum_20 < -5 and volatility_20 > 2.5:
        risk_level = "high"
    elif momentum_20 < 0 and volatility_20 > 2:
        risk_level = "medium"
    else:
        risk_level = "low"

    stock_count = stock_counts.get(industry, 1) // max(len(recent), 1)

    return {
        "industry": industry,
        "latest_date": latest_date_ind,
        "momentum_5": round(momentum_5, 2),
        "momentum_20": round(momentum_20, 2),
        "volatility_20": round(volatility_20, 2),
        "avg_amount_yi": round(avg_amount / 100000, 2) if avg_amount else 0,
        "return_risk_ratio": round(return_risk_ratio, 2),
        "risk_level": risk_level,
        "stock_count": max(stock_count, 1),
    }


# ══════════════════════════════════════════════════
#  行业因子
# ══════════════════════════════════════════════════
def calc_industry_factors():
    cache_key = _cache_key("industry")
    cached = _precomputed_get(cache_key)
    if cached is not None:
        return cached

    recent_dates = _get_recent_trade_dates(30)
    if not recent_dates:
        return {"industries": [], "risk_warnings": []}

    df = _fetch_industry_daily_data(recent_dates)
    if len(df) == 0:
        return {"industries": [], "risk_warnings": []}

    industry_daily = _aggregate_industry_daily(df)
    latest_date = industry_daily["trade_date"].max()
    stock_counts = df.groupby("industry")["close"].count().to_dict()

    results = []
    for industry, group in industry_daily.groupby("industry"):
        metrics = _calculate_industry_metrics(industry, group, stock_counts)
        if metrics:
            results.append(metrics)

    if not results:
        return {"industries": [], "risk_warnings": []}

    results_df = pd.DataFrame(results).sort_values("momentum_20", ascending=False)
    risk_warnings = results_df[results_df["risk_level"] != "low"].to_dict("records")

    result = {
        "date": latest_date,
        "industries": _safe_json(results_df),
        "risk_warnings": _safe_json(pd.DataFrame(risk_warnings)),
    }
    _precomputed_set(cache_key, result)
    return result


# ══════════════════════════════════════════════════
#  动量因子（优化版：turnover 查询限定日期范围）
# ══════════════════════════════════════════════════
def calc_momentum_factors():
    cache_key = _cache_key("momentum")
    cached = _precomputed_get(cache_key)
    if cached is not None:
        all_stocks = cached.get('stocks', [])
        all_high_risk = cached.get('high_risk', [])
        all_valid = all(
            s.get('name', '') != '' and s.get('industry', '') != '' 
            for s in all_stocks
        )
        high_risk_valid = all(
            s.get('name', '') != '' and s.get('industry', '') != '' 
            for s in all_high_risk
        )
        if all_valid and high_risk_valid:
            return cached

    recent_dates = _get_recent_trade_dates(25)
    if not recent_dates:
        return {"stocks": [], "high_risk": []}
    placeholders = ",".join([f":p{i}" for i in range(len(recent_dates))])
    params = {f"p{i}": d for i, d in enumerate(recent_dates)}

    # ── P1.1: Push aggregation into SQL (eliminates Python groupby loop) ──
    agg_df = _query(f"""
        WITH ranked AS (
            SELECT d.ts_code, d.trade_date, d.close, d.pct_chg, d.vol, d.amount,
                   ROW_NUMBER() OVER (PARTITION BY d.ts_code ORDER BY d.trade_date DESC) as rn,
                   COUNT(*) OVER (PARTITION BY d.ts_code) as cnt
            FROM stock_daily d
            WHERE d.pct_chg IS NOT NULL AND d.vol IS NOT NULL
              AND d.trade_date IN ({placeholders})
        ),
        filtered AS (
            SELECT * FROM ranked WHERE cnt >= 20 AND rn <= 20
        )
        SELECT ts_code,
               SUM(pct_chg) as momentum_20,
               STDDEV(pct_chg) as volatility_20,
               COALESCE(CORR(close, vol), 0) as pv_corr,
               AVG(amount) as avg_amount,
               (ARRAY_AGG(close ORDER BY rn DESC))[1] as latest_close,
               (ARRAY_AGG(pct_chg ORDER BY rn DESC))[1] as latest_pct_chg,
               COUNT(*) as n
        FROM filtered
        GROUP BY ts_code
        HAVING COUNT(*) >= 10
    """, params)
    if len(agg_df) == 0:
        return {"stocks": [], "high_risk": []}

    # ── Stock info (single batch query) ──
    ts_codes = agg_df['ts_code'].unique().tolist()
    placeholders_info = ",".join([f":p{i}" for i in range(len(ts_codes))])
    params_info = {f"p{i}": c for i, c in enumerate(ts_codes)}
    info = _query(f"""
        SELECT COALESCE(si.ts_code, sb.ts_code) as ts_code,
               COALESCE(si.name, sb.name, '') as name,
               COALESCE(si.sw_level3, sb.industry, '') as industry
        FROM (SELECT UNNEST(ARRAY[{placeholders_info}]) as ts_code) AS codes
        LEFT JOIN stock_info si ON codes.ts_code = si.ts_code
        LEFT JOIN stock_basic sb ON codes.ts_code = sb.ts_code
    """, params_info)

    # ── Turnover (single batch query) ──
    recent_20_dates = recent_dates[:20] if len(recent_dates) >= 20 else recent_dates
    placeholders_to = ",".join([f":p{i}" for i in range(len(recent_20_dates))])
    params_to = {f"p{i}": d for i, d in enumerate(recent_20_dates)}
    turnover = _query(f"""
        SELECT ts_code, AVG(turnover_rate) as avg_turnover_20
        FROM stock_daily_basic
        WHERE turnover_rate IS NOT NULL
          AND trade_date IN ({placeholders_to})
        GROUP BY ts_code
    """, params_to)

    # ── Merge and score (vectorized, no loop) ──
    results_df = agg_df.merge(info, on="ts_code", how="left")
    results_df = results_df.merge(turnover, on="ts_code", how="left")

    results_df["name"] = results_df["name"].fillna("")
    results_df["industry"] = results_df["industry"].fillna("")
    results_df = results_df[(results_df["name"] != "") & (results_df["industry"] != "")]

    for col in ["momentum_20", "volatility_20", "pv_corr", "avg_amount", "avg_turnover_20"]:
        results_df[col] = pd.to_numeric(results_df[col], errors="coerce")

    # Vectorized risk score — percentile-based (P2.2)
    risk_score = pd.Series(0, index=results_df.index)

    # Top 5% volatility → risky
    vol_95 = results_df["volatility_20"].quantile(0.95)
    vol_mask = results_df["volatility_20"].notna() & (results_df["volatility_20"] >= vol_95)
    risk_score = risk_score + vol_mask.astype(int)

    # Top 5% turnover → risky
    to_95 = results_df["avg_turnover_20"].quantile(0.95)
    to_mask = results_df["avg_turnover_20"].notna() & (results_df["avg_turnover_20"] >= to_95)
    risk_score = risk_score + to_mask.astype(int)

    # Bottom 10% pv_corr AND negative momentum → risky
    pv_10 = results_df["pv_corr"].quantile(0.10)
    pv_mask = (results_df["pv_corr"] <= pv_10) & (results_df["momentum_20"] < 0)
    risk_score = risk_score + pv_mask.astype(int)

    results_df["risk_score"] = risk_score
    results_df["avg_amount_wan"] = results_df["avg_amount"].fillna(0).round(0)
    results_df["latest_close"] = pd.to_numeric(results_df["latest_close"], errors="coerce").round(2)
    results_df["latest_pct_chg"] = pd.to_numeric(results_df["latest_pct_chg"], errors="coerce").round(2)

    high_risk = results_df[results_df["risk_score"] >= 2].sort_values(
        "volatility_20", ascending=False
    ).head(20)
    results_df = results_df.sort_values("volatility_20", ascending=False)

    # Round display columns
    for col, decimals in [("momentum_20", 2), ("volatility_20", 2),
                           ("avg_turnover_20", 2), ("pv_corr", 3)]:
        results_df[col] = results_df[col].round(decimals)
        if col in high_risk.columns:
            high_risk[col] = high_risk[col].round(decimals)

    result = {
        "stocks": _safe_json(results_df.head(100)),
        "high_risk": _safe_json(high_risk),
    }
    _precomputed_set(cache_key, result)
    return result


# ══════════════════════════════════════════════════
#  规模因子（SMB）
# ══════════════════════════════════════════════════
def calc_size_factors():
    cache_key = _cache_key("size")
    cached = _precomputed_get(cache_key)
    if cached is not None:
        return cached

    recent_dates = _get_recent_trade_dates(25)
    if not recent_dates:
        return {"style": "neutral", "confidence": 0, "size_groups": [], "history": []}
    placeholders = ",".join([f":p{i}" for i in range(len(recent_dates))])
    params = {f"p{i}": d for i, d in enumerate(recent_dates)}
    db = _query(f"""
        SELECT v.ts_code, v.trade_date, v.total_mv,
               d.pct_chg
        FROM stock_daily_basic v
        JOIN stock_daily d ON v.ts_code = d.ts_code AND v.trade_date = d.trade_date
        WHERE v.total_mv IS NOT NULL AND d.pct_chg IS NOT NULL
          AND v.trade_date IN ({placeholders})
    """, params)
    if len(db) == 0:
        return {"style": "neutral", "confidence": 0, "size_groups": [], "history": []}

    db["total_mv"] = pd.to_numeric(db["total_mv"], errors="coerce")
    db["pct_chg"] = pd.to_numeric(db["pct_chg"], errors="coerce")
    db = db.dropna(subset=["total_mv", "pct_chg"])

    latest_date = db["trade_date"].max()
    latest = db[db["trade_date"] == latest_date].copy()

    if len(latest) < 50:
        return {"style": "neutral", "confidence": 0, "size_groups": [], "history": []}

    # ── P2.4: Median split for SMB (standard Fama-French) ──
    mv_median = latest["total_mv"].median()

    def _size_bucket(mv):
        return "大盘" if mv >= mv_median else "小盘"

    latest["size_group"] = latest["total_mv"].apply(_size_bucket)

    size_groups = []
    for g in ["大盘", "小盘"]:
        sub = latest[latest["size_group"] == g]
        if len(sub) == 0:
            continue
        size_groups.append({
            "group": g,
            "count": len(sub),
            "avg_mv_yi": round(sub["total_mv"].mean() / 10000, 2),
            "avg_pct_chg": round(sub["pct_chg"].mean(), 2),
        })

    dates = sorted(db["trade_date"].unique())
    recent_dates_hist = dates[-20:] if len(dates) >= 20 else dates

    history = []
    for td in recent_dates_hist:
        day_data = db[db["trade_date"] == td].copy()
        if len(day_data) < 50:
            continue
        # P2.4: median split
        mv_med = day_data["total_mv"].median()

        large = day_data[day_data["total_mv"] >= mv_med]["pct_chg"].mean()
        small = day_data[day_data["total_mv"] < mv_med]["pct_chg"].mean()
        smb = small - large if (small is not None and large is not None) else 0

        history.append({
            "date": td,
            "large_return": round(large, 2) if large is not None else None,
            "small_return": round(small, 2) if small is not None else None,
            "smb": round(smb, 2),
        })

    if len(history) >= 5:
        recent_smb = [h["smb"] for h in history[-5:]]
        avg_smb = np.mean(recent_smb)
        if avg_smb > 0.3:
            style = "small_cap"
            confidence = min(abs(avg_smb) / 2, 1.0)
        elif avg_smb < -0.3:
            style = "large_cap"
            confidence = min(abs(avg_smb) / 2, 1.0)
        else:
            style = "balanced"
            confidence = 1.0 - min(abs(avg_smb) / 0.3, 1.0)
    else:
        style = "neutral"
        confidence = 0

    result = {
        "date": latest_date,
        "style": style,
        "confidence": round(confidence, 2),
        "size_groups": size_groups,
        "history": history,
    }
    _precomputed_set(cache_key, result)
    return result


# ══════════════════════════════════════════════════
#  风格因子（HML：成长 vs 价值）
# ══════════════════════════════════════════════════
def calc_style_factors():
    cache_key = _cache_key("style")
    cached = _precomputed_get(cache_key)
    if cached is not None:
        return cached

    recent_dates = _get_recent_trade_dates(25)
    if not recent_dates:
        return {"style": "neutral", "confidence": 0, "growth_stats": {}, "value_stats": {}, "history": []}
    placeholders = ",".join([f":p{i}" for i in range(len(recent_dates))])
    params = {f"p{i}": d for i, d in enumerate(recent_dates)}
    db = _query(f"""
        SELECT v.ts_code, v.trade_date, v.pe_ttm, v.pb, v.total_mv,
               d.pct_chg
        FROM stock_daily_basic v
        JOIN stock_daily d ON v.ts_code = d.ts_code AND v.trade_date = d.trade_date
        WHERE v.pe_ttm IS NOT NULL AND v.pb IS NOT NULL
          AND v.total_mv IS NOT NULL AND d.pct_chg IS NOT NULL
          AND v.trade_date IN ({placeholders})
    """, params)
    if len(db) == 0:
        return {"style": "neutral", "confidence": 0, "growth_stats": {}, "value_stats": {}, "history": []}

    db["pe_ttm"] = pd.to_numeric(db["pe_ttm"], errors="coerce")
    db["pb"] = pd.to_numeric(db["pb"], errors="coerce")
    db["total_mv"] = pd.to_numeric(db["total_mv"], errors="coerce")
    db["pct_chg"] = pd.to_numeric(db["pct_chg"], errors="coerce")
    db = db.dropna(subset=["pe_ttm", "pb", "total_mv", "pct_chg"])

    valid = db[(db["pe_ttm"] > 0) & (db["pb"] > 0) & (db["total_mv"] >= 200000)].copy()
    if len(valid) < 50:
        return {"style": "neutral", "confidence": 0, "growth_stats": {}, "value_stats": {}, "history": []}

    fina = _query("""
        SELECT f.ts_code, f.tr_yoy, f.netprofit_yoy
        FROM stock_fina_indicator f
        INNER JOIN (
            SELECT ts_code, MAX(end_date) as max_ed
            FROM stock_fina_indicator
            GROUP BY ts_code
        ) latest ON f.ts_code = latest.ts_code AND f.end_date = latest.max_ed
    """)

    latest_date = valid["trade_date"].max()
    latest = valid[valid["trade_date"] == latest_date].copy()

    if len(latest) < 50:
        return {"style": "neutral", "confidence": 0, "growth_stats": {}, "value_stats": {}, "history": []}

    if len(fina) > 0:
        fina["tr_yoy"] = pd.to_numeric(fina["tr_yoy"], errors="coerce")
        fina["netprofit_yoy"] = pd.to_numeric(fina["netprofit_yoy"], errors="coerce")
        latest = latest.merge(fina, on="ts_code", how="left")

    # ── P2.3: Composite PE/PB score so all stocks are included ──
    latest["pe_rank"] = latest["pe_ttm"].rank(pct=True)
    latest["pb_rank"] = latest["pb"].rank(pct=True)
    latest["composite"] = latest["pe_rank"] + latest["pb_rank"]
    composite_median = latest["composite"].median()

    growth_mask = latest["composite"] > composite_median
    value_mask = latest["composite"] <= composite_median

    if "tr_yoy" in latest.columns:
        growth_with_fina = growth_mask & (latest["tr_yoy"] > 0)
    else:
        growth_with_fina = growth_mask

    growth_stocks = latest[growth_with_fina]
    value_stocks = latest[value_mask]

    growth_stats = {
        "count": len(growth_stocks),
        "avg_pe": round(growth_stocks["pe_ttm"].mean(), 1) if len(growth_stocks) > 0 else 0,
        "avg_pb": round(growth_stocks["pb"].mean(), 2) if len(growth_stocks) > 0 else 0,
        "avg_pct_chg": round(growth_stocks["pct_chg"].mean(), 2) if len(growth_stocks) > 0 else 0,
    }
    value_stats = {
        "count": len(value_stocks),
        "avg_pe": round(value_stocks["pe_ttm"].mean(), 1) if len(value_stocks) > 0 else 0,
        "avg_pb": round(value_stocks["pb"].mean(), 2) if len(value_stocks) > 0 else 0,
        "avg_pct_chg": round(value_stocks["pct_chg"].mean(), 2) if len(value_stocks) > 0 else 0,
    }

    dates = sorted(valid["trade_date"].unique())
    recent_dates_hist = dates[-20:] if len(dates) >= 20 else dates

    history = []
    for td in recent_dates_hist:
        day_data = valid[valid["trade_date"] == td].copy()
        if len(day_data) < 50:
            continue
        # P2.3: composite PE/PB score
        day_data["pe_rank"] = day_data["pe_ttm"].rank(pct=True)
        day_data["pb_rank"] = day_data["pb"].rank(pct=True)
        day_data["composite"] = day_data["pe_rank"] + day_data["pb_rank"]
        comp_med = day_data["composite"].median()

        g_mask = day_data["composite"] > comp_med
        v_mask = day_data["composite"] <= comp_med

        g_ret = day_data[g_mask]["pct_chg"].mean() if g_mask.sum() > 0 else 0
        v_ret = day_data[v_mask]["pct_chg"].mean() if v_mask.sum() > 0 else 0
        hml = g_ret - v_ret

        history.append({
            "date": td,
            "growth_return": round(g_ret, 2) if g_ret is not None else None,
            "value_return": round(v_ret, 2) if v_ret is not None else None,
            "hml": round(hml, 2),
        })

    if len(history) >= 5:
        recent_hml = [h["hml"] for h in history[-5:]]
        avg_hml = np.mean(recent_hml)
        if avg_hml > 0.2:
            style = "growth"
            confidence = min(abs(avg_hml) / 1.0, 1.0)
        elif avg_hml < -0.2:
            style = "value"
            confidence = min(abs(avg_hml) / 1.0, 1.0)
        else:
            style = "balanced"
            confidence = 1.0 - min(abs(avg_hml) / 0.2, 1.0)
    else:
        style = "neutral"
        confidence = 0

    result = {
        "date": latest_date,
        "style": style,
        "confidence": round(confidence, 2),
        "growth_stats": growth_stats,
        "value_stats": value_stats,
        "history": history,
    }
    _precomputed_set(cache_key, result)
    return result


# ══════════════════════════════════════════════════
#  BARRA 汇总（直接读取缓存，无需重复计算）
# ══════════════════════════════════════════════════
def calc_barra_summary():
    size = calc_size_factors()
    style = calc_style_factors()
    ind = calc_industry_factors()
    mom = calc_momentum_factors()

    ind_warnings = len(ind.get("risk_warnings", []))
    stock_warnings = len(mom.get("high_risk", []))

    style_map = {
        "large_cap": "大盘占优",
        "small_cap": "小盘占优",
        "balanced": "大小均衡",
        "neutral": "数据不足",
    }
    gv_map = {
        "growth": "成长占优",
        "value": "价值占优",
        "balanced": "风格均衡",
        "neutral": "数据不足",
    }

    return {
        "date": size.get("date") or style.get("date") or "",
        "market_style": style_map.get(size.get("style", "neutral"), "数据不足"),
        "market_confidence": size.get("confidence", 0),
        "growth_value": gv_map.get(style.get("style", "neutral"), "数据不足"),
        "gv_confidence": style.get("confidence", 0),
        "industry_risk_count": ind_warnings,
        "stock_risk_count": stock_warnings,
    }
