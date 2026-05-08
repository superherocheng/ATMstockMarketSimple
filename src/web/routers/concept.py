import logging
from collections import defaultdict
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.web.services.cache import _cached_persistent
from src.web.services.db import query, safe_json, safe_dict

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()


def _calculate_concept_heat(concept_id: int):
    """计算概念热度分数"""
    try:
        volume_change = query("""
            WITH latest_5days AS (
                SELECT DISTINCT trade_date FROM stock_daily
                ORDER BY trade_date DESC LIMIT 5
            ),
            prev_5days AS (
                SELECT DISTINCT trade_date FROM stock_daily
                ORDER BY trade_date DESC LIMIT 5 OFFSET 5
            ),
            recent_vol AS (
                SELECT SUM(sd.vol) as total_vol
                FROM stock_concept sc
                JOIN stock_daily sd ON sc.ts_code = sd.ts_code
                WHERE sc.concept_id = :p0 AND sd.trade_date IN (SELECT trade_date FROM latest_5days)
            ),
            prev_vol AS (
                SELECT SUM(sd.vol) as total_vol
                FROM stock_concept sc
                JOIN stock_daily sd ON sc.ts_code = sd.ts_code
                WHERE sc.concept_id = :p1 AND sd.trade_date IN (SELECT trade_date FROM prev_5days)
            )
            SELECT
                COALESCE(rv.total_vol, 0) as recent_vol,
                COALESCE(pv.total_vol, 0) as prev_vol
            FROM recent_vol rv, prev_vol pv
        """, {"p0": concept_id, "p1": concept_id})

        if len(volume_change) == 0:
            return 0

        recent_vol = float(volume_change.iloc[0]['recent_vol'] or 0)
        prev_vol = float(volume_change.iloc[0]['prev_vol'] or 0)

        volume_factor = 0
        if prev_vol > 0:
            volume_factor = min((recent_vol - prev_vol) / prev_vol * 100, 100)

        up_down_ratio = query("""
            WITH latest_date AS (
                SELECT MAX(trade_date) as max_date FROM stock_daily
            )
            SELECT
                SUM(CASE WHEN sd.pct_chg > 0 THEN 1 ELSE 0 END) as up_count,
                SUM(CASE WHEN sd.pct_chg < 0 THEN 1 ELSE 0 END) as down_count,
                COUNT(*) as total
            FROM stock_concept sc
            JOIN stock_daily sd ON sc.ts_code = sd.ts_code
            WHERE sc.concept_id = :p0 AND sd.trade_date = (SELECT max_date FROM latest_date)
        """, {"p0": concept_id})

        up_down_factor = 0
        if len(up_down_ratio) > 0:
            up_count = float(up_down_ratio.iloc[0]['up_count'] or 0)
            total = float(up_down_ratio.iloc[0]['total'] or 1)
            if total > 0:
                up_down_factor = (up_count / total) * 100

        leader_performance = query("""
            WITH latest_date AS (
                SELECT MAX(trade_date) as max_date FROM stock_daily
            ),
            top_gainers AS (
                SELECT sd.pct_chg
                FROM stock_concept sc
                JOIN stock_daily sd ON sc.ts_code = sd.ts_code
                WHERE sc.concept_id = :p0
                    AND sd.trade_date = (SELECT max_date FROM latest_date)
                    AND sd.pct_chg IS NOT NULL
                ORDER BY sd.pct_chg DESC
                LIMIT 3
            )
            SELECT AVG(pct_chg) as avg_pct FROM top_gainers
        """, {"p0": concept_id})

        leader_factor = 0
        if len(leader_performance) > 0:
            avg_pct = float(leader_performance.iloc[0]['avg_pct'] or 0)
            leader_factor = max(min(avg_pct * 10, 100), -100)

        # P2.5: leader_factor normalized to 0-100 range (removed +100 bias)
        leader_norm = (leader_factor + 100) / 2  # -100→0, +100→100

        heat_score = (
            volume_factor * 0.3 +
            up_down_factor * 0.3 +
            leader_norm * 0.4
        )

        return round(max(0, min(100, heat_score)), 2)
    except Exception:
        return 0


@router.get("/concept", response_class=HTMLResponse)
async def page_concept(request: Request):
    return templates.TemplateResponse("concept.html", {"request": request})


def _compute_concept_analysis():
    try:
        concept_stats = query("""
            SELECT
                cd.concept_id,
                cd.concept_name,
                COUNT(DISTINCT sc.ts_code) as stock_count
            FROM concept_dict cd
            LEFT JOIN stock_concept sc ON cd.concept_id = sc.concept_id
            GROUP BY cd.concept_id, cd.concept_name
            HAVING COUNT(DISTINCT sc.ts_code) > 3
            ORDER BY stock_count DESC
            LIMIT 50
        """)

        if len(concept_stats) == 0:
            return {"concepts": [], "error": "暂无概念数据，请先加载 ALLSYMBOL.csv"}

        concept_ids = concept_stats['concept_id'].tolist()

        placeholders = ",".join([f":p{i}" for i in range(len(concept_ids))])
        params = {f"p{i}": v for i, v in enumerate(concept_ids)}
        all_top_stocks = query(f"""
            WITH latest_date AS (
                SELECT MAX(trade_date) as max_date FROM stock_daily
            ),
            latest_basic_date AS (
                SELECT trade_date
                FROM stock_daily_basic
                GROUP BY trade_date
                HAVING COUNT(*) > 1000
                ORDER BY trade_date DESC
                LIMIT 1
            ),
            ranked_stocks AS (
                SELECT
                    sc.concept_id,
                    si.ts_code,
                    si.name,
                    si.sw_level1 as industry,
                    sd.close,
                    sd.pct_chg,
                    sd.vol,
                    sd.amount,
                    sb.total_mv,
                    sb.pe_ttm,
                    sb.pb,
                    sb.turnover_rate,
                    ROW_NUMBER() OVER (PARTITION BY sc.concept_id ORDER BY sb.total_mv DESC NULLS LAST) as rn
                FROM stock_concept sc
                JOIN stock_info si ON sc.ts_code = si.ts_code
                LEFT JOIN stock_daily sd ON si.ts_code = sd.ts_code
                    AND sd.trade_date = (SELECT max_date FROM latest_date)
                LEFT JOIN stock_daily_basic sb ON si.ts_code = sb.ts_code
                JOIN latest_basic_date lbd ON sb.trade_date = lbd.trade_date
                WHERE sc.concept_id IN ({placeholders})
            )
            SELECT * FROM ranked_stocks WHERE rn <= 10
        """, params)

        heat_data = query(f"""
            WITH latest_5days AS (
                SELECT DISTINCT trade_date FROM stock_daily
                ORDER BY trade_date DESC LIMIT 5
            ),
            prev_5days AS (
                SELECT DISTINCT trade_date FROM stock_daily
                ORDER BY trade_date DESC LIMIT 5 OFFSET 5
            ),
            latest_date AS (
                SELECT MAX(trade_date) as max_date FROM stock_daily
            )
            SELECT
                sc.concept_id,
                SUM(CASE WHEN sd.trade_date IN (SELECT trade_date FROM latest_5days) THEN sd.vol ELSE 0 END) as recent_vol,
                SUM(CASE WHEN sd.trade_date IN (SELECT trade_date FROM prev_5days) THEN sd.vol ELSE 0 END) as prev_vol,
                SUM(CASE WHEN sd.trade_date = (SELECT max_date FROM latest_date) AND sd.pct_chg > 0 THEN 1 ELSE 0 END) as up_count,
                SUM(CASE WHEN sd.trade_date = (SELECT max_date FROM latest_date) AND sd.pct_chg < 0 THEN 1 ELSE 0 END) as down_count,
                COUNT(CASE WHEN sd.trade_date = (SELECT max_date FROM latest_date) THEN 1 END) as total_count,
                AVG(CASE WHEN sd.trade_date = (SELECT max_date FROM latest_date) THEN sd.pct_chg END) as avg_pct
            FROM stock_concept sc
            LEFT JOIN stock_daily sd ON sc.ts_code = sd.ts_code
            WHERE sc.concept_id IN ({placeholders})
            GROUP BY sc.concept_id
        """, params)

        stocks_by_concept = defaultdict(list)
        if len(all_top_stocks) > 0:
            for _, row in all_top_stocks.iterrows():
                stocks_by_concept[row['concept_id']].append(safe_dict({
                    'ts_code': row['ts_code'],
                    'name': row['name'],
                    'industry': row['industry'],
                    'close': row['close'],
                    'pct_chg': row['pct_chg'],
                    'vol': row['vol'],
                    'amount': row['amount'],
                    'total_mv': row['total_mv'],
                    'pe_ttm': row['pe_ttm'],
                    'pb': row['pb'],
                    'turnover_rate': row['turnover_rate']
                }))

        heat_scores = {}
        if len(heat_data) > 0:
            for _, row in heat_data.iterrows():
                concept_id = row['concept_id']
                recent_vol = float(row['recent_vol'] or 0)
                prev_vol = float(row['prev_vol'] or 0)
                up_count = float(row['up_count'] or 0)
                total_count = float(row['total_count'] or 1)
                avg_pct = float(row['avg_pct'] or 0)

                volume_factor = 0
                if prev_vol > 0:
                    volume_factor = min((recent_vol - prev_vol) / prev_vol * 100, 100)

                up_down_factor = (up_count / total_count) * 100 if total_count > 0 else 0

                leader_factor = max(min(avg_pct * 10, 100), -100)
                leader_norm = (leader_factor + 100) / 2  # -100→0, +100→100

                heat_score = (
                    volume_factor * 0.3 +
                    up_down_factor * 0.3 +
                    leader_norm * 0.4
                )
                heat_scores[concept_id] = round(max(0, min(100, heat_score)), 2)

        concepts = []
        for _, row in concept_stats.iterrows():
            concept_id = row['concept_id']
            concepts.append({
                "concept_id": concept_id,
                "concept_name": row['concept_name'],
                "stock_count": row['stock_count'],
                "heat_score": heat_scores.get(concept_id, 0),
                "top_stocks": stocks_by_concept.get(concept_id, [])[:10]
            })

        return safe_dict({"concepts": concepts})
    except Exception as e:
        logger.error(f"概念分析失败: {e}", exc_info=True)
        return {"concepts": [], "error": str(e)}


@router.get("/api/concept/analysis")
async def api_concept_analysis():
    return _cached_persistent("concept_analysis", _compute_concept_analysis, max_age_hours=4)


def _compute_concept_list():
    try:
        concept_stats = query("""
            SELECT
                cd.concept_id,
                cd.concept_name,
                COUNT(DISTINCT sc.ts_code) as stock_count
            FROM concept_dict cd
            LEFT JOIN stock_concept sc ON cd.concept_id = sc.concept_id
            GROUP BY cd.concept_id, cd.concept_name
            HAVING COUNT(DISTINCT sc.ts_code) > 3
            ORDER BY stock_count DESC
            LIMIT 50
        """)

        if len(concept_stats) == 0:
            return {"concepts": [], "error": "暂无概念数据，请先加载 ALLSYMBOL.csv"}

        concepts = []
        for _, row in concept_stats.iterrows():
            concepts.append({
                "concept_id": row['concept_id'],
                "concept_name": row['concept_name'],
                "stock_count": row['stock_count']
            })

        return {"concepts": concepts}
    except Exception as e:
        return {"concepts": [], "error": str(e)}


@router.get("/api/concept/list")
async def api_concept_list():
    return _cached_persistent("concept_list", _compute_concept_list, max_age_hours=4)


def _compute_concept_details():
    """P1.2: Batched top-stocks query (50 N+1 → 1 query)."""
    try:
        concept_stats = query("""
            SELECT
                cd.concept_id,
                cd.concept_name,
                COUNT(DISTINCT sc.ts_code) as stock_count
            FROM concept_dict cd
            LEFT JOIN stock_concept sc ON cd.concept_id = sc.concept_id
            GROUP BY cd.concept_id, cd.concept_name
            HAVING COUNT(DISTINCT sc.ts_code) > 3
            ORDER BY stock_count DESC
            LIMIT 50
        """)

        if len(concept_stats) == 0:
            return {"concepts": [], "error": "暂无概念数据"}

        concept_ids = concept_stats['concept_id'].tolist()
        placeholders = ",".join([f":p{i}" for i in range(len(concept_ids))])
        params = {f"p{i}": v for i, v in enumerate(concept_ids)}

        # ── Single batched query for all top stocks ──
        all_top_stocks = query(f"""
            WITH latest_date AS (
                SELECT MAX(trade_date) as max_date FROM stock_daily
            ),
            latest_basic_date AS (
                SELECT MAX(trade_date) as max_date FROM stock_daily_basic
            ),
            ranked AS (
                SELECT
                    sc.concept_id, si.ts_code, si.name,
                    si.sw_level1 as industry,
                    sd.close, sd.pct_chg, sd.vol, sd.amount,
                    sb.total_mv, sb.pe_ttm, sb.pb, sb.turnover_rate,
                    ROW_NUMBER() OVER (PARTITION BY sc.concept_id ORDER BY sb.total_mv DESC NULLS LAST) as rn
                FROM stock_concept sc
                JOIN stock_info si ON sc.ts_code = si.ts_code
                LEFT JOIN stock_daily sd ON si.ts_code = sd.ts_code
                    AND sd.trade_date = (SELECT max_date FROM latest_date)
                LEFT JOIN stock_daily_basic sb ON si.ts_code = sb.ts_code
                    AND sb.trade_date = (SELECT max_date FROM latest_basic_date)
                WHERE sc.concept_id IN ({placeholders})
            )
            SELECT concept_id, ts_code, name, industry,
                   close, pct_chg, vol, amount,
                   total_mv, pe_ttm, pb, turnover_rate
            FROM ranked WHERE rn <= 10
        """, params)

        stocks_by_concept = {}
        if len(all_top_stocks) > 0:
            for _, row in all_top_stocks.iterrows():
                cid = row['concept_id']
                if cid not in stocks_by_concept:
                    stocks_by_concept[cid] = []
                stocks_by_concept[cid].append(safe_dict({
                    'ts_code': row['ts_code'], 'name': row['name'],
                    'industry': row['industry'], 'close': row['close'],
                    'pct_chg': row['pct_chg'], 'vol': row['vol'],
                    'amount': row['amount'], 'total_mv': row['total_mv'],
                    'pe_ttm': row['pe_ttm'], 'pb': row['pb'],
                    'turnover_rate': row['turnover_rate']
                }))

        concepts = []
        for _, row in concept_stats.iterrows():
            cid = row['concept_id']
            concepts.append({
                "concept_id": cid,
                "top_stocks": safe_json(pd.DataFrame(stocks_by_concept.get(cid, [])))
            })

        return {"concepts": concepts}
    except Exception as e:
        return {"concepts": [], "error": str(e)}


@router.get("/api/concept/details")
async def api_concept_details():
    return _cached_persistent("concept_details", _compute_concept_details, max_age_hours=4)


def _compute_concept_charts():
    """P1.2: Reuse batched heat scores from _compute_concept_analysis
    instead of calling _calculate_concept_heat() for each concept (150+ queries → 0 extra)."""
    try:
        analysis = _compute_concept_analysis()
        all_concepts = analysis.get("concepts", [])
        concepts = []
        for c in all_concepts:
            concepts.append({
                "concept_id": c["concept_id"],
                "concept_name": c["concept_name"],
                "stock_count": c["stock_count"],
                "heat_score": c.get("heat_score", 0)
            })
        return {"concepts": concepts}
    except Exception as e:
        return {"concepts": [], "error": str(e)}


@router.get("/api/concept/charts")
async def api_concept_charts():
    return _cached_persistent("concept_charts", _compute_concept_charts, max_age_hours=4)


def _compute_concept_detail(concept_id: int):
    try:
        concept_info = query("""
            SELECT concept_id, concept_name
            FROM concept_dict
            WHERE concept_id = :p0
        """, {"p0": concept_id})

        if len(concept_info) == 0:
            return {"error": "概念不存在"}

        concept_name = concept_info.iloc[0]['concept_name']

        all_stocks = query("""
            SELECT
                si.ts_code,
                si.name,
                si.sw_level1 as industry,
                sd.close,
                sd.pct_chg,
                sd.vol,
                sd.amount,
                sb.total_mv,
                sb.pe_ttm,
                sb.pb,
                sb.turnover_rate
            FROM stock_concept sc
            JOIN stock_info si ON sc.ts_code = si.ts_code
            LEFT JOIN stock_daily sd ON si.ts_code = sd.ts_code
                AND sd.trade_date = (SELECT MAX(trade_date) FROM stock_daily)
            LEFT JOIN stock_daily_basic sb ON si.ts_code = sb.ts_code
                AND sb.trade_date = (SELECT MAX(trade_date) FROM stock_daily_basic)
            WHERE sc.concept_id = :p0
            ORDER BY sb.total_mv DESC NULLS LAST
        """, {"p0": concept_id})

        volume_data = query("""
            SELECT
                sd.trade_date,
                SUM(sd.amount) as total_amount,
                SUM(sd.vol) as total_vol,
                COUNT(DISTINCT sd.ts_code) as stock_count
            FROM stock_concept sc
            JOIN stock_daily sd ON sc.ts_code = sd.ts_code
            WHERE sc.concept_id = :p0
            GROUP BY sd.trade_date
            ORDER BY sd.trade_date DESC
            LIMIT 60
        """, {"p0": concept_id})

        return {
            "concept_id": concept_id,
            "concept_name": concept_name,
            "stocks": safe_json(all_stocks),
            "volume_history": safe_json(volume_data.iloc[::-1])
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/concept/{concept_id}")
async def api_concept_detail(concept_id: int):
    return _cached_persistent(f"concept_{concept_id}", lambda: _compute_concept_detail(concept_id), max_age_hours=4)
