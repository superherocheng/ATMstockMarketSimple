"""FastAPI router for the analysis module."""
import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.web.services.cache import _cached_persistent
from src.analysis.presets import PRESETS, get_preset, all_preset_ids
from src.analysis import factor_engine, ic_analyzer, chart_builder, recommendation_engine

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()


@router.get("/analysis", response_class=HTMLResponse)
async def page_analysis(request: Request):
    return templates.TemplateResponse("analysis.html", {"request": request})


@router.get("/analysis/tech-notes", response_class=HTMLResponse)
async def page_tech_notes(request: Request):
    return templates.TemplateResponse("tech_notes.html", {"request": request})


@router.get("/analysis/investment-recommendation", response_class=HTMLResponse)
async def page_investment_recommendation(request: Request):
    return templates.TemplateResponse("investment_recommendation.html", {"request": request})


@router.get("/api/analysis/presets")
async def api_presets():
    return {"presets": list(PRESETS.values()), "default": "short"}


@router.get("/api/analysis/factor-distribution")
async def api_factor_distribution(preset_id: str = "short"):
    return _cached_persistent(
        f"analysis_factor_dist_{preset_id}",
        lambda: chart_builder.build_factor_distribution(preset_id),
        max_age_hours=4,
    )


@router.get("/api/analysis/ic-series")
async def api_ic_series(preset_id: str = "short"):
    return _cached_persistent(
        f"analysis_ic_series_{preset_id}",
        lambda: chart_builder.build_ic_series(preset_id),
        max_age_hours=4,
    )


@router.get("/api/analysis/quadrant-heatmap")
async def api_quadrant_heatmap(preset_id: str = "short"):
    return _cached_persistent(
        f"analysis_qheatmap_{preset_id}",
        lambda: chart_builder.build_quadrant_heatmap(preset_id),
        max_age_hours=4,
    )


@router.get("/api/analysis/group-returns")
async def api_group_returns(preset_id: str = "short"):
    return _cached_persistent(
        f"analysis_group_ret_{preset_id}",
        lambda: chart_builder.build_group_returns(preset_id),
        max_age_hours=4,
    )


@router.get("/api/analysis/rolling-icir")
async def api_rolling_icir(preset_id: str = "short", window: int = 60):
    return _cached_persistent(
        f"analysis_rolling_icir_{preset_id}_{window}",
        lambda: chart_builder.build_rolling_icir(preset_id, window),
        max_age_hours=4,
    )


@router.get("/api/analysis/weight-recommendation")
async def api_weight_recommendation(preset_id: str = "short"):
    return _cached_persistent(
        f"analysis_weight_rec_{preset_id}",
        lambda: chart_builder.build_weight_recommendation(preset_id),
        max_age_hours=4,
    )


@router.get("/api/analysis/summary")
async def api_summary(preset_id: str = "short"):
    return _cached_persistent(
        f"analysis_summary_{preset_id}",
        lambda: chart_builder.build_summary(preset_id),
        max_age_hours=4,
    )


@router.get("/api/investment-recommendation")
async def api_investment_recommendation(preset_id: str = "short"):
    return _cached_persistent(
        f"investment_rec_v2_{preset_id}",
        lambda: recommendation_engine.build_investment_recommendation(preset_id),
        max_age_hours=4,
    )


@router.get("/api/market-timing")
async def api_market_timing():
    from src.analysis.market_timing import compute_market_timing
    return _cached_persistent(
        "market_timing",
        compute_market_timing,
        max_age_hours=4,
    )


@router.post("/api/analysis/recompute")
async def api_recompute(preset_id: str = None):
    """Trigger factor + IC recomputation in a background thread."""
    import threading

    def _run():
        try:
            logger.info(f"Starting analysis recomputation (preset={preset_id or 'all'})")
            factor_engine.compute_all_factors(preset_id)
            ic_analyzer.compute_all_ic(preset_id)
            logger.info("Analysis recomputation complete")
        except Exception as e:
            logger.error(f"Analysis recomputation failed: {e}")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"status": "started", "preset_id": preset_id or "all"}
