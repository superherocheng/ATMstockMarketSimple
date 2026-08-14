import asyncio
import logging

import pandas as pd
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.web.services.cache import _cached_persistent, _api_cache
from src.core.db_manager_postgresql import get_conn, query, safe_json, bind_inlist
from config.config import INDEX_ETF, SECTOR_ETF, DATA_DIR
from src.core.trading_calendar import now_beijing, get_latest_trading_date
from src.data_fetchers.tushare_fetcher import _apply_etf_adj

logger = logging.getLogger(__name__)

router = APIRouter()


async def _async_cached(cache_key, compute_fn, max_age_hours):
    """Run sync _cached_persistent in a thread to avoid blocking the event loop."""
    return await asyncio.to_thread(_cached_persistent, cache_key, compute_fn, max_age_hours)


def _compute_overview():
    result = {"index_etf": [], "sector_summary": []}
    cols = ["ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount", "pre_close", "pct_chg"]
    with get_conn() as conn:
        # ── Single query for all index ETFs ──
        index_codes = list(INDEX_ETF.keys())
        if index_codes:
            placeholders, params = bind_inlist(index_codes, prefix="idx_")
            rows_idx = conn.execute(
                text(f"""
                    WITH ranked AS (
                        SELECT *, ROW_NUMBER() OVER (
                            PARTITION BY ts_code ORDER BY trade_date DESC
                        ) as rn
                        FROM index_etf_daily
                        WHERE ts_code IN ({placeholders})
                    )
                    SELECT ts_code, trade_date, open, high, low, close, vol, amount, pre_close, pct_chg
                    FROM ranked WHERE rn = 1
                """),
                params,
            ).fetchall()
            if rows_idx:
                df_idx = pd.DataFrame(rows_idx, columns=cols)
                for ts_code, group in df_idx.groupby("ts_code"):
                    adj_group = _apply_etf_adj(group, ts_code)
                    for _, row in adj_group.iterrows():
                        d = row.to_dict()
                        d["name"] = INDEX_ETF.get(d["ts_code"], d["ts_code"])
                        d["pct_chg"] = d.get("pct_chg", 0) or 0
                        result["index_etf"].append(d)

        # ── Single query for all sector ETFs ──
        sector_codes = list(SECTOR_ETF.keys())
        if sector_codes:
            placeholders, params = bind_inlist(sector_codes, prefix="sec_")
            rows_sec = conn.execute(
                text(f"""
                    WITH ranked AS (
                        SELECT *, ROW_NUMBER() OVER (
                            PARTITION BY ts_code ORDER BY trade_date DESC
                        ) as rn
                        FROM sector_etf_daily
                        WHERE ts_code IN ({placeholders})
                    )
                    SELECT ts_code, trade_date, open, high, low, close, vol, amount, pre_close, pct_chg
                    FROM ranked WHERE rn = 1
                """),
                params,
            ).fetchall()
            if rows_sec:
                df_sec = pd.DataFrame(rows_sec, columns=cols)
                for ts_code, group in df_sec.groupby("ts_code"):
                    adj_group = _apply_etf_adj(group, ts_code)
                    for _, row in adj_group.iterrows():
                        d = row.to_dict()
                        d["name"] = SECTOR_ETF.get(d["ts_code"], d["ts_code"])
                        d["pct_chg"] = d.get("pct_chg", 0) or 0
                        result["sector_summary"].append(d)

        # ── Share data for all ETFs ──
        all_codes = index_codes + sector_codes
        share_data = {}
        if all_codes:
            placeholders, params = bind_inlist(all_codes, prefix="sh_")
            rows = conn.execute(
                text(f"""
                    WITH ranked AS (
                        SELECT ts_code, trade_date, fd_share,
                               ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) as rn
                        FROM etf_share
                        WHERE ts_code IN ({placeholders}) AND fd_share IS NOT NULL
                    )
                    SELECT ts_code, trade_date, fd_share FROM ranked WHERE rn <= 11
                """),
                params,
            ).fetchall()
            for row in rows:
                code = row[0]
                if code not in share_data:
                    share_data[code] = []
                share_data[code].append({
                    "date": str(row[1]),
                    "share": float(row[2])
                })

        def _add_share_info(items, name_map):
            for item in items:
                code = item["ts_code"]
                shares = share_data.get(code, [])
                if len(shares) >= 2:
                    latest = shares[0]["share"]
                    prev = shares[1]["share"]
                    item["share_change_qty"] = round(latest - prev, 2)
                    item["share_change_pct"] = round(((latest - prev) / prev * 100) if prev > 0 else 0, 4)
                    item["latest_share"] = latest
                    item["share_date"] = shares[0]["date"]
                    if len(shares) >= 11:
                        ten_ago = shares[10]["share"]
                        item["share_change_10d_qty"] = round(latest - ten_ago, 2)
                        item["share_change_10d_pct"] = round(((latest - ten_ago) / ten_ago * 100) if ten_ago > 0 else 0, 4)
                    else:
                        item["share_change_10d_qty"] = None
                        item["share_change_10d_pct"] = None
                elif len(shares) == 1:
                    item["share_change_qty"] = None
                    item["share_change_pct"] = None
                    item["share_change_10d_qty"] = None
                    item["share_change_10d_pct"] = None
                    item["latest_share"] = shares[0]["share"]
                    item["share_date"] = shares[0]["date"]
                else:
                    item["share_change_qty"] = None
                    item["share_change_pct"] = None
                    item["share_change_10d_qty"] = None
                    item["share_change_10d_pct"] = None
                    item["latest_share"] = None
                    item["share_date"] = None
            return items

        result["index_etf"] = _add_share_info(result["index_etf"], INDEX_ETF)
        result["sector_summary"] = _add_share_info(result["sector_summary"], SECTOR_ETF)
    return result


def _compute_heatmap():
    result = []
    with get_conn() as conn:
        sector_codes = list(SECTOR_ETF.keys())
        if sector_codes:
            placeholders, params = bind_inlist(sector_codes, prefix="c_")
            rows = conn.execute(
                text(f"""
                    WITH ranked AS (
                        SELECT ts_code, pct_chg, amount,
                               ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) as rn
                        FROM sector_etf_daily
                        WHERE ts_code IN ({placeholders})
                    )
                    SELECT ts_code, pct_chg, amount FROM ranked WHERE rn = 1
                """),
                params,
            ).fetchall()
            for row in rows:
                code = row[0]
                pct = row[1] or 0
                result.append({
                    "name": SECTOR_ETF.get(code, code),
                    "ts_code": code,
                    "pct_chg": round(float(pct), 2),
                    # 最新成交额（tushare 千元）— treemap 面积维度
                    "amount": round(float(row[2]), 2) if row[2] is not None else None,
                })
    return result


def validate_analysis_data():
    """验证分析数据的完整性"""
    try:
        with get_conn() as conn:
            checks = {}

            try:
                stock_count = conn.execute(text("SELECT COUNT(*) FROM stock_basic")).fetchone()[0]
                checks["stock_basic"] = {"exists": True, "count": stock_count}
            except Exception:
                checks["stock_basic"] = {"exists": False, "count": 0}

            try:
                concept_count = conn.execute(text("SELECT COUNT(*) FROM concept_dict")).fetchone()[0]
                stock_concept_count = conn.execute(text("SELECT COUNT(*) FROM stock_concept")).fetchone()[0]
                checks["concept"] = {
                    "exists": True,
                    "concept_count": concept_count,
                    "relation_count": stock_concept_count
                }
            except Exception:
                checks["concept"] = {"exists": False, "concept_count": 0, "relation_count": 0}

            try:
                industry_count = conn.execute(text("""
                    SELECT COUNT(DISTINCT sw_level1) FROM stock_info
                    WHERE sw_level1 IS NOT NULL AND sw_level1 != ''
                """)).fetchone()[0]
                checks["industry"] = {"exists": True, "industry_count": industry_count}
            except Exception:
                checks["industry"] = {"exists": False, "industry_count": 0}

            try:
                latest_trade = conn.execute(text("SELECT MAX(trade_date) FROM stock_daily")).fetchone()[0]
                checks["stock_daily"] = {"exists": True, "latest_date": latest_trade}
            except Exception:
                checks["stock_daily"] = {"exists": False, "latest_date": None}

            overall_status = "OK"
            if not checks["stock_basic"]["exists"] or checks["stock_basic"]["count"] == 0:
                overall_status = "ERROR"
            elif not checks["stock_daily"]["exists"]:
                overall_status = "ERROR"
            elif not checks["concept"]["exists"] and not checks["industry"]["exists"]:
                overall_status = "WARNING"

            return {
                "status": overall_status,
                "checks": checks
            }
    except Exception as e:
        logger.error("Validation failed: %s", e, exc_info=True)
        return {
            "status": "ERROR",
            "error": "Internal validation error",
            "checks": {}
        }


@router.get("/api/overview")
async def api_overview():
    return await _async_cached("overview", _compute_overview, max_age_hours=4)


@router.get("/api/heatmap")
async def api_heatmap():
    # v2: 加了 amount 字段（treemap 用），换 key 绕开旧缓存条目
    return await _async_cached("heatmap_v2", _compute_heatmap, max_age_hours=4)


@router.get("/api/analysis/validate")
async def api_validate_analysis():
    """验证分析数据的完整性"""
    return await asyncio.to_thread(validate_analysis_data)


@router.get("/health")
async def health_check():
    """健康检查端点"""
    return await asyncio.to_thread(_health_check_sync)


def _health_check_sync():
    """Sync implementation of health check, run in a thread."""
    checks = {
        "status": "healthy",
        "timestamp": now_beijing().isoformat(),
        "version": "16.0.0",
        "checks": {}
    }

    try:
        with get_conn() as conn:
            conn.execute(text("SELECT 1")).fetchone()
        checks["checks"]["database"] = {"status": "ok"}
    except Exception as e:
        logger.error("Database health check failed: %s", e, exc_info=True)
        checks["checks"]["database"] = {"status": "error", "message": "Database connection failed"}
        checks["status"] = "unhealthy"

    try:
        latest = get_latest_trading_date()
        db_max = query("SELECT MAX(trade_date) as max_date FROM stock_daily")
        if len(db_max) > 0:
            db_max_val = db_max.iloc[0]['max_date']
            # Convert to YYYYMMDD string for safe string comparison
            if hasattr(db_max_val, 'strftime'):
                db_max_str = db_max_val.strftime("%Y%m%d")
            else:
                db_max_str = str(db_max_val).replace("-", "")
            is_fresh = db_max_str and latest and db_max_str >= latest
            checks["checks"]["data_freshness"] = {
                "status": "ok" if is_fresh else "stale",
                "latest_trading_date": latest,
                "db_max_date": db_max_str
            }
        else:
            checks["checks"]["data_freshness"] = {"status": "no_data"}
    except Exception as e:
        logger.error("Data freshness check failed: %s", e, exc_info=True)
        checks["checks"]["data_freshness"] = {"status": "error", "message": "Data freshness check failed"}

    checks["checks"]["cache"] = {
        "status": "ok",
        "memory_cache_size": len(_api_cache._cache) if hasattr(_api_cache, '_cache') else 0
    }

    if checks["status"] != "healthy":
        return JSONResponse(checks, status_code=503)
    return checks


def _compute_data_range():
    """查询数据库中各数据表的日期范围和记录数"""
    with get_conn() as conn:
        tables_info = {}
        table_configs = [
            ("index_etf_daily", "指数ETF日线", True, "trade_date"),
            ("etf_share", "ETF份额", True, "trade_date"),
            ("sector_etf_daily", "行业ETF日线", True, "trade_date"),
        ]

        for table_name, display_name, has_date, date_col in table_configs:
            try:
                count_row = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).fetchone()
                count = count_row[0] if count_row else 0

                min_date, max_date = None, None
                if count > 0 and has_date and date_col:
                    try:
                        date_row = conn.execute(text(f"SELECT MIN({date_col}), MAX({date_col}) FROM {table_name}")).fetchone()
                        if date_row:
                            min_date, max_date = date_row[0], date_row[1]
                    except Exception:
                        pass

                # Normalise date values to strings for JSON safety
                min_date_str = str(min_date) if min_date else None
                max_date_str = str(max_date) if max_date else None
                tables_info[table_name] = {
                    "display_name": display_name, "exists": True,
                    "count": count, "min_date": min_date_str, "max_date": max_date_str,
                }
            except Exception as e:
                tables_info[table_name] = {
                    "display_name": display_name, "exists": False,
                    "count": 0, "min_date": None, "max_date": None, "error": str(e),
                }

        # Cap etf_share max_date at last trading day
        if "etf_share" in tables_info and tables_info["etf_share"].get("max_date"):
            try:
                trading_row = conn.execute(text(
                    "SELECT MAX(trade_date) FROM sector_etf_daily"
                )).fetchone()
                if trading_row and trading_row[0]:
                    last_trading_date = str(trading_row[0])
                    share_max = str(tables_info["etf_share"]["max_date"])
                    if share_max > last_trading_date:
                        tables_info["etf_share"]["max_date"] = last_trading_date
                        import logging
                        logging.getLogger(__name__).info(
                            f"Capped etf_share max_date from {share_max} to {last_trading_date}"
                        )
            except Exception:
                pass

        return tables_info


@router.get("/api/data-range")
async def api_data_range():
    """查询数据库中各数据表的日期范围和记录数（缓存5分钟）"""
    return await _async_cached("data_range", _compute_data_range, max_age_hours=0.083)
