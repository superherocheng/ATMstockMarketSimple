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
    return {"presets": list(PRESETS.values()), "default": "optimized"}


@router.get("/api/analysis/factor-distribution")
async def api_factor_distribution(preset_id: str = "optimized"):
    return _cached_persistent(
        f"analysis_factor_dist_{preset_id}",
        lambda: chart_builder.build_factor_distribution(preset_id),
        max_age_hours=4,
    )


@router.get("/api/analysis/ic-series")
async def api_ic_series(preset_id: str = "optimized"):
    return _cached_persistent(
        f"analysis_ic_series_{preset_id}",
        lambda: chart_builder.build_ic_series(preset_id),
        max_age_hours=4,
    )


@router.get("/api/analysis/quadrant-heatmap")
async def api_quadrant_heatmap(preset_id: str = "optimized"):
    return _cached_persistent(
        f"analysis_qheatmap_{preset_id}",
        lambda: chart_builder.build_quadrant_heatmap(preset_id),
        max_age_hours=4,
    )


@router.get("/api/analysis/group-returns")
async def api_group_returns(preset_id: str = "optimized"):
    return _cached_persistent(
        f"analysis_group_ret_{preset_id}",
        lambda: chart_builder.build_group_returns(preset_id),
        max_age_hours=4,
    )


@router.get("/api/analysis/rolling-icir")
async def api_rolling_icir(preset_id: str = "optimized", window: int = 60):
    return _cached_persistent(
        f"analysis_rolling_icir_{preset_id}_{window}",
        lambda: chart_builder.build_rolling_icir(preset_id, window),
        max_age_hours=4,
    )


@router.get("/api/analysis/ic-summary-all")
async def api_ic_summary_all():
    """Return IC summary for all presets for the homepage card."""
    from sqlalchemy import text
    from src.core.db_manager_postgresql import get_conn

    # Build lookup with preset config (label, description)
    preset_config = {}
    for pid, cfg in PRESETS.items():
        preset_config[pid] = {
            "label": cfg.get("label", pid),
            "desc": cfg.get("description", ""),
        }

    conn = get_conn()
    try:
        rows = conn.execute(text("""
            SELECT preset_id, forward_days,
                   ic_mean, ic_std, icir, ic_win_rate, sample_count
            FROM ic_summary ORDER BY preset_id, forward_days
        """)).fetchall()
    finally:
        conn.close()

    result = []
    for r in rows:
        rid = r[0]
        if rid not in preset_config:
            continue
        config = preset_config[rid]
        result.append({
            "preset_id": rid,
            "label": config["label"],
            "forward_days": r[1],
            "ic_mean": round(float(r[2]), 4) if r[2] is not None else None,
            "ic_std": round(float(r[3]), 4) if r[3] is not None else None,
            "icir": round(float(r[4]), 4) if r[4] is not None else None,
            "ic_win_rate": round(float(r[5]) * 100, 2) if r[5] is not None else None,
            "sample_count": r[6] if r[6] else 0,
        })

    return {"presets": result, "count": len(result)}


@router.get("/api/analysis/summary")
async def api_summary(preset_id: str = "optimized"):
    return _cached_persistent(
        f"analysis_summary_{preset_id}",
        lambda: chart_builder.build_summary(preset_id),
        max_age_hours=4,
    )


@router.get("/api/investment-recommendation")
async def api_investment_recommendation(preset_id: str = "optimized"):
    result = _cached_persistent(
        f"investment_rec_v2_{preset_id}",
        lambda: recommendation_engine.build_investment_recommendation(preset_id),
        max_age_hours=4,
    )

    # Task 2.2/3.1: Inject quality warnings
    if "error" not in result and "recommendations" in result:
        try:
            from src.analysis.financial_factor import load_latest_financial_factors
            qf = load_latest_financial_factors()
            non_zero = sum(1 for v in qf.values() if abs(v.get("f_quality", 0)) > 1e-10)
            if len(qf) > 0 and non_zero == 0:
                if "warnings" not in result:
                    result["warnings"] = []
                result["warnings"].append(
                    "Quality 因子数据为空：financial_factor 表无有效数据。"
                    "请先运行财务数据提取或触发 recompute-financial API。"
                )
        except Exception as exc:
            pass

    return result


@router.get("/api/market-timing")
async def api_market_timing():
    from src.analysis.market_timing import compute_market_timing
    return _cached_persistent(
        "market_timing",
        compute_market_timing,
        max_age_hours=4,
    )


@router.get("/api/analysis/financial-factors")
async def api_financial_factors():
    """Return latest financial quality factor data for all ETFs."""
    try:
        from src.analysis.financial_factor import load_latest_financial_factors
        factors = load_latest_financial_factors()
        return {"factors": factors, "count": len(factors)}
    except Exception as exc:
        logger.warning(f"Could not load financial factors: {exc}")
        return {"factors": {}, "count": 0, "error": str(exc)}


@router.post("/api/analysis/recompute-financial")
async def api_recompute_financial():
    """Trigger financial quality factor recomputation."""
    import threading

    def _run():
        try:
            from src.analysis.financial_factor import compute_and_persist
            logger.info("Starting financial factor recomputation")
            result = compute_and_persist()
            logger.info(f"Financial factor recomputation complete: {len(result)} ETFs")
        except Exception as e:
            logger.error(f"Financial factor recomputation failed: {e}")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"status": "started", "message": "Factor calculation started"}


@router.post("/api/analysis/recompute")
async def api_recompute(preset_id: str = None):
    """Trigger factor + IC recomputation in a background thread.

    V4: Now also triggers financial factor recomputation before factor_engine.
    """
    import threading

    def _run():
        try:
            logger.info(f"Starting analysis recomputation (preset={preset_id or 'all'})")
            # First compute financial factors (if available)
            try:
                from src.analysis.financial_factor import compute_and_persist
                finance_result = compute_and_persist()
                logger.info(f"Financial factors computed: {len(finance_result)} ETFs")
            except Exception as fe:
                logger.warning(f"Financial factor computation skipped: {fe}")
            # Then compute factor engine + IC
            factor_engine.compute_all_factors(preset_id)
            ic_analyzer.compute_all_ic(preset_id)
            logger.info("Analysis recomputation complete")
        except Exception as e:
            logger.error(f"Analysis recomputation failed: {e}")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"status": "started", "preset_id": preset_id or "all"}
