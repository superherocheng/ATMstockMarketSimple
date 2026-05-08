import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.web.services.cache import _cached_persistent
from src.analytics import barra as barra_mod

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()


@router.get("/barra", response_class=HTMLResponse)
async def page_barra(request: Request):
    return templates.TemplateResponse("barra.html", {"request": request})


@router.get("/api/barra/summary")
async def api_barra_summary():
    try:
        return _cached_persistent("barra_summary", barra_mod.calc_barra_summary, max_age_hours=4)
    except Exception as e:
        return {"error": str(e), "date": "", "market_style": "数据不足",
                "market_confidence": 0, "growth_value": "数据不足",
                "gv_confidence": 0, "industry_risk_count": 0, "stock_risk_count": 0}


@router.get("/api/barra/industry")
async def api_barra_industry():
    try:
        return _cached_persistent("barra_industry", barra_mod.calc_industry_factors, max_age_hours=4)
    except Exception as e:
        return {"error": str(e), "industries": [], "risk_warnings": []}


@router.get("/api/barra/momentum")
async def api_barra_momentum():
    try:
        return _cached_persistent("barra_momentum", barra_mod.calc_momentum_factors, max_age_hours=4)
    except Exception as e:
        return {"error": str(e), "stocks": [], "high_risk": []}


@router.get("/api/barra/size")
async def api_barra_size():
    try:
        return _cached_persistent("barra_size", barra_mod.calc_size_factors, max_age_hours=4)
    except Exception as e:
        return {"error": str(e), "style": "neutral", "confidence": 0,
                "size_groups": [], "history": []}


@router.get("/api/barra/style")
async def api_barra_style():
    try:
        return _cached_persistent("barra_style", barra_mod.calc_style_factors, max_age_hours=4)
    except Exception as e:
        return {"error": str(e), "style": "neutral", "confidence": 0,
                "growth_stats": {}, "value_stats": {}, "history": []}
