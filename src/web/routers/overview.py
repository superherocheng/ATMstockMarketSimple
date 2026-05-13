import logging
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from src.web.services.cache import _cached_persistent, _api_cache
from src.core.db_manager_postgresql import get_conn, query, safe_json
from config.config import INDEX_ETF, SECTOR_ETF, DATA_DIR
from src.core.trading_calendar import now_beijing, get_latest_trading_date

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()


def _compute_overview():
    conn = get_conn()
    result = {"index_etf": [], "sector_summary": []}
    cols = ["ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount", "pre_close", "pct_chg"]
    try:
        # ── Single query for all index ETFs ──
        index_codes = list(INDEX_ETF.keys())
        if index_codes:
            placeholders = ",".join([f":idx_{i}" for i in range(len(index_codes))])
            params = {f"idx_{i}": c for i, c in enumerate(index_codes)}
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
            for row in rows_idx:
                d = dict(zip(cols, row))
                d["name"] = INDEX_ETF.get(d["ts_code"], d["ts_code"])
                d["pct_chg"] = d.get("pct_chg", 0) or 0
                result["index_etf"].append(d)

        # ── Single query for all sector ETFs ──
        sector_codes = list(SECTOR_ETF.keys())
        if sector_codes:
            placeholders = ",".join([f":sec_{i}" for i in range(len(sector_codes))])
            params = {f"sec_{i}": c for i, c in enumerate(sector_codes)}
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
            for row in rows_sec:
                d = dict(zip(cols, row))
                d["name"] = SECTOR_ETF.get(d["ts_code"], d["ts_code"])
                d["pct_chg"] = d.get("pct_chg", 0) or 0
                result["sector_summary"].append(d)
    finally:
        conn.close()
    return result


def _compute_heatmap():
    conn = get_conn()
    result = []
    try:
        sector_codes = list(SECTOR_ETF.keys())
        if sector_codes:
            placeholders = ",".join([f":c_{i}" for i in range(len(sector_codes))])
            params = {f"c_{i}": c for i, c in enumerate(sector_codes)}
            rows = conn.execute(
                text(f"""
                    WITH ranked AS (
                        SELECT ts_code, pct_chg,
                               ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) as rn
                        FROM sector_etf_daily
                        WHERE ts_code IN ({placeholders})
                    )
                    SELECT ts_code, pct_chg FROM ranked WHERE rn = 1
                """),
                params,
            ).fetchall()
            for row in rows:
                code = row[0]
                pct = row[1] or 0
                result.append({
                    "name": SECTOR_ETF.get(code, code),
                    "ts_code": code,
                    "pct_chg": round(float(pct), 2)
                })
    finally:
        conn.close()
    return result


def validate_analysis_data():
    """验证分析数据的完整性"""
    conn = None
    try:
        conn = get_conn()

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
        return {
            "status": "ERROR",
            "error": str(e),
            "checks": {}
        }
    finally:
        if conn:
            conn.close()


@router.get("/", response_class=HTMLResponse)
async def page_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/api/overview")
async def api_overview():
    return _cached_persistent("overview", _compute_overview, max_age_hours=4)


@router.get("/api/heatmap")
async def api_heatmap():
    return _cached_persistent("heatmap", _compute_heatmap, max_age_hours=4)


@router.get("/api/analysis/validate")
async def api_validate_analysis():
    """验证分析数据的完整性"""
    return validate_analysis_data()


@router.get("/health")
async def health_check():
    """健康检查端点"""
    checks = {
        "status": "healthy",
        "timestamp": now_beijing().isoformat(),
        "version": "13.0.0",
        "checks": {}
    }

    try:
        conn = get_conn()
        conn.execute(text("SELECT 1")).fetchone()
        checks["checks"]["database"] = {"status": "ok"}
    except Exception as e:
        checks["checks"]["database"] = {"status": "error", "message": str(e)}
        checks["status"] = "unhealthy"

    try:
        latest = get_latest_trading_date()
        db_max = query("SELECT MAX(trade_date) as max_date FROM stock_daily")
        if len(db_max) > 0:
            db_max_date = db_max.iloc[0]['max_date']
            is_fresh = db_max_date and latest and db_max_date >= latest
            checks["checks"]["data_freshness"] = {
                "status": "ok" if is_fresh else "stale",
                "latest_trading_date": latest,
                "db_max_date": db_max_date
            }
        else:
            checks["checks"]["data_freshness"] = {"status": "no_data"}
    except Exception as e:
        checks["checks"]["data_freshness"] = {"status": "error", "message": str(e)}

    checks["checks"]["cache"] = {
        "status": "ok",
        "memory_cache_size": len(_api_cache._cache) if hasattr(_api_cache, '_cache') else 0
    }

    if checks["status"] != "healthy":
        return JSONResponse(checks, status_code=503)
    return checks


def _compute_data_range():
    """查询数据库中各数据表的日期范围和记录数"""
    conn = None
    try:
        conn = get_conn()

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

                tables_info[table_name] = {
                    "display_name": display_name, "exists": True,
                    "count": count, "min_date": min_date, "max_date": max_date,
                }
            except Exception as e:
                tables_info[table_name] = {
                    "display_name": display_name, "exists": False,
                    "count": 0, "min_date": None, "max_date": None, "error": str(e),
                }

        return tables_info
    finally:
        if conn:
            conn.close()


@router.get("/api/data-range")
async def api_data_range():
    """查询数据库中各数据表的日期范围和记录数（缓存5分钟）"""
    from src.web.services.cache import _cached_persistent
    return _cached_persistent("data_range", _compute_data_range, max_age_hours=0.083)
