"""FastAPI router for the analysis module.

Analysis-page factor/IC visualization endpoints (presets, factor-distribution,
ic-series, quadrant-heatmap, group-returns, rolling-icir, summary, ic-summary-all)
and /api/analysis/recompute were removed together with the analysis page
(2026-07-18). Remaining here: investment-recommendation, market-timing,
holding-history (distinct features, not part of the factor-analysis page).
"""
import asyncio
import logging

from fastapi import APIRouter

from src.web.services.cache import _cached_persistent
from src.analysis import recommendation_engine

logger = logging.getLogger(__name__)

router = APIRouter()


async def _async_cached(cache_key, compute_fn, max_age_hours):
    """Run sync _cached_persistent in a thread to avoid blocking the event loop."""
    return await asyncio.to_thread(_cached_persistent, cache_key, compute_fn, max_age_hours)


@router.get("/api/investment-recommendation")
async def api_investment_recommendation(preset_id: str = "optimized"):
    return await asyncio.to_thread(_investment_recommendation_sync, preset_id)


def _investment_recommendation_sync(preset_id):
    """Sync implementation of investment recommendation, run in a thread."""
    result = _cached_persistent(
        f"investment_rec_v2_{preset_id}",
        lambda: recommendation_engine.build_investment_recommendation(preset_id),
        max_age_hours=4,
    )

    # ── Dynamically compute change_action (always fresh, never cached) ──
    if "error" not in result and "recommendations" in result and result["recommendations"]:
        try:
            recs = result.get("recommendations", [])
            rec_date = result.get("date", "")
            if recs and rec_date:
                recommendation_engine.enrich_change_actions(preset_id, recs, rec_date)
        except Exception as exc:
            logger.warning("Failed to enrich change actions: %s", exc)

    return result


@router.get("/api/market-timing")
async def api_market_timing():
    from src.analysis.market_timing import compute_market_timing
    return await _async_cached(
        "market_timing",
        compute_market_timing,
        max_age_hours=4,
    )


@router.get("/api/analysis/holding-history")
async def api_holding_history(preset_id: str = "optimized", days: int = 15):
    """Return the last N days of holding history.

    Each entry contains date and positions with code, name, quadrant,
    factor score, position ratio, strategy, and change action.
    """
    return await asyncio.to_thread(
        recommendation_engine.load_holding_history, preset_id, days
    )
