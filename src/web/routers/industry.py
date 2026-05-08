import logging
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from src.web.services.cache import _cached_persistent
from src.web.services.db import get_conn, query, safe_json
from src.web.services.validators import validate_industry_name
from src.core.trading_calendar import now_beijing

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()


@router.get("/industry", response_class=HTMLResponse)
async def page_industry(request: Request):
    return templates.TemplateResponse("industry.html", {"request": request})


def _compute_industry_analysis():
    try:
        basic_check = query("SELECT COUNT(*) as cnt FROM stock_daily_basic")
        if len(basic_check) == 0 or basic_check.iloc[0]['cnt'] == 0:
            logger.warning("stock_daily_basic 表没有数据")
            return {
                "industries": [],
                "error": "暂无每日估值数据（PE/PB/市值）。请运行: python fetch_data.py --funda"
            }

        latest_daily_date = None
        latest_basic_date = None
        try:
            daily_date_row = query("SELECT MAX(trade_date) as max_date FROM stock_daily")
            if len(daily_date_row) > 0 and daily_date_row.iloc[0]['max_date']:
                latest_daily_date = daily_date_row.iloc[0]['max_date']

            basic_date_row = query("SELECT MAX(trade_date) as max_date FROM stock_daily_basic")
            if len(basic_date_row) > 0 and basic_date_row.iloc[0]['max_date']:
                latest_basic_date = basic_date_row.iloc[0]['max_date']
        except Exception as e:
            logger.error(f"获取最新日期失败: {e}")

        logger.info(f"行业分析 - 最新日线日期: {latest_daily_date}, 最新估值日期: {latest_basic_date}")

        if not latest_daily_date or not latest_basic_date:
            logger.warning(f"日期数据缺失 - daily: {latest_daily_date}, basic: {latest_basic_date}")
            return {
                "industries": [],
                "error": "数据日期缺失，请检查数据库"
            }

        level1_stats = query("""
            SELECT
                sw_level1,
                COUNT(DISTINCT ts_code) as stock_count
            FROM stock_info
            WHERE sw_level1 IS NOT NULL AND sw_level1 != ''
            GROUP BY sw_level1
            HAVING COUNT(DISTINCT ts_code) > 3
            ORDER BY stock_count DESC
        """)

        level3_stats = query("""
            SELECT
                sw_level1,
                sw_level2,
                sw_level3,
                COUNT(DISTINCT ts_code) as stock_count
            FROM stock_info
            WHERE sw_level3 IS NOT NULL AND sw_level3 != ''
            GROUP BY sw_level1, sw_level2, sw_level3
            HAVING COUNT(DISTINCT ts_code) > 3
            ORDER BY stock_count DESC
        """)

        if len(level3_stats) == 0:
            return {"industries": [], "error": "暂无行业数据，请先加载 ALLSYMBOL.csv"}

        industries = []
        for _, row in level3_stats.iterrows():
            level1_name = row['sw_level1']
            level2_name = row['sw_level2']
            level3_name = row['sw_level3']
            stock_count = row['stock_count']
            
            if stock_count <= 3:
                continue

            top_stocks = query("""
                SELECT
                    si.ts_code,
                    si.name,
                    si.sw_level2 as sub_industry,
                    sd.close,
                    sd.pct_chg,
                    sd.vol,
                    sd.amount,
                    sb.total_mv,
                    sb.pe_ttm,
                    sb.pb,
                    sb.turnover_rate
                FROM stock_info si
                LEFT JOIN stock_daily sd ON si.ts_code = sd.ts_code
                    AND sd.trade_date = (SELECT MAX(trade_date) FROM stock_daily)
                LEFT JOIN stock_daily_basic sb ON si.ts_code = sb.ts_code
                    AND sb.trade_date = (SELECT MAX(trade_date) FROM stock_daily_basic)
                WHERE si.sw_level3 = :p0
                ORDER BY sb.total_mv DESC NULLS LAST
                LIMIT 10
            """, {"p0": level3_name})

            avg_metrics = query("""
                SELECT
                    AVG(sb.total_mv) as avg_mv,
                    AVG(sb.pe_ttm) as avg_pe,
                    AVG(sb.pb) as avg_pb,
                    AVG(sb.turnover_rate) as avg_turnover,
                    SUM(sd.amount) as total_amount,
                    SUM(sd.vol) as total_vol
                FROM stock_info si
                LEFT JOIN stock_daily sd ON si.ts_code = sd.ts_code
                    AND sd.trade_date = (SELECT MAX(trade_date) FROM stock_daily)
                LEFT JOIN stock_daily_basic sb ON si.ts_code = sb.ts_code
                    AND sb.trade_date = (SELECT MAX(trade_date) FROM stock_daily_basic)
                WHERE si.sw_level3 = :p0
            """, {"p0": level3_name})

            avg_data = avg_metrics.iloc[0] if len(avg_metrics) > 0 else {}

            def safe_float_nullable(val):
                if val is None or pd.isna(val):
                    return None
                try:
                    f = float(val)
                    if pd.isna(f) or np.isinf(f):
                        return None
                    return f
                except:
                    return None

            industries.append({
                "industry": level3_name,
                "sw_level1": level1_name,
                "sw_level2": level2_name,
                "sw_level3": level3_name,
                "stock_count": stock_count,
                "top_stocks": safe_json(top_stocks),
                "avg_metrics": {
                    "avg_mv": safe_float_nullable(avg_data.get('avg_mv')),
                    "avg_pe": safe_float_nullable(avg_data.get('avg_pe')),
                    "avg_pb": safe_float_nullable(avg_data.get('avg_pb')),
                    "avg_turnover": safe_float_nullable(avg_data.get('avg_turnover')),
                    "total_amount": safe_float_nullable(avg_data.get('total_amount')),
                    "total_vol": safe_float_nullable(avg_data.get('total_vol'))
                }
            })

        industries_with_data = sum(1 for ind in industries
                                   if ind['avg_metrics']['avg_mv'] is not None)
        logger.info(f"行业分析完成 - 总行业数: {len(industries)}, 有市值数据的行业: {industries_with_data}")

        if industries_with_data == 0:
            logger.warning("所有行业都没有市值数据")
            return {
                "industries": industries,
                "level1_stats": safe_json(level1_stats),
                "warning": "行业数据已加载，但市值/PE/PB数据缺失。可能原因：\n1. stock_daily_basic 表数据不完整\n2. 数据日期不匹配\n3. 股票代码不匹配\n\n建议：运行 python fetch_data.py --funda 更新数据"
            }

        return {
            "industries": industries,
            "level1_stats": safe_json(level1_stats)
        }
    except Exception as e:
        logger.error(f"行业分析失败: {e}", exc_info=True)
        return {"industries": [], "error": str(e)}


@router.get("/api/industry/analysis")
async def api_industry_analysis():
    return _cached_persistent("industry_analysis", _compute_industry_analysis, max_age_hours=4)


def _compute_industry_detail(industry_name: str):
    try:
        all_stocks = query("""
            SELECT
                si.ts_code,
                si.name,
                si.sw_level2 as sub_industry,
                si.sw_level3 as tertiary_industry,
                sd.close,
                sd.pct_chg,
                sd.vol,
                sd.amount,
                sb.total_mv,
                sb.pe_ttm,
                sb.pb,
                sb.turnover_rate
            FROM stock_info si
            LEFT JOIN stock_daily sd ON si.ts_code = sd.ts_code
                AND sd.trade_date = (SELECT MAX(trade_date) FROM stock_daily)
            LEFT JOIN stock_daily_basic sb ON si.ts_code = sb.ts_code
                AND sb.trade_date = (SELECT MAX(trade_date) FROM stock_daily_basic)
            WHERE si.sw_level1 = :p0
            ORDER BY sb.total_mv DESC NULLS LAST
        """, {"p0": industry_name})

        volume_data = query("""
            SELECT
                sd.trade_date,
                SUM(sd.amount) as total_amount,
                SUM(sd.vol) as total_vol,
                COUNT(DISTINCT sd.ts_code) as stock_count
            FROM stock_info si
            JOIN stock_daily sd ON si.ts_code = sd.ts_code
            WHERE si.sw_level1 = :p0
            GROUP BY sd.trade_date
            ORDER BY sd.trade_date DESC
            LIMIT 60
        """, {"p0": industry_name})

        sub_industry_stats = query("""
            SELECT
                si.sw_level2 as sub_industry,
                COUNT(DISTINCT si.ts_code) as stock_count,
                AVG(sb.total_mv) as avg_mv,
                AVG(sb.pe_ttm) as avg_pe
            FROM stock_info si
            LEFT JOIN stock_daily_basic sb ON si.ts_code = sb.ts_code
                AND sb.trade_date = (SELECT MAX(trade_date) FROM stock_daily_basic)
            WHERE si.sw_level1 = :p0 AND si.sw_level2 IS NOT NULL AND si.sw_level2 != ''
            GROUP BY si.sw_level2
            ORDER BY stock_count DESC
        """, {"p0": industry_name})

        return {
            "industry": industry_name,
            "stocks": safe_json(all_stocks),
            "volume_history": safe_json(volume_data.iloc[::-1]),
            "sub_industries": safe_json(sub_industry_stats)
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/industry/{industry_name}")
async def api_industry_detail(industry_name: str):
    if not validate_industry_name(industry_name):
        return JSONResponse(
            {"error": "无效的行业名称"},
            status_code=400
        )

    return _cached_persistent(f"industry_{industry_name}", lambda: _compute_industry_detail(industry_name), max_age_hours=4)
