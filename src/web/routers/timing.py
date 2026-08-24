"""择时仪表盘路由：温度计 / 轮动矩阵 / 日历热力图 / 底部定位器。

缓存键分别落在 analysis_* / rotation_* 类别下，数据刷新后自动失效。
"""
import asyncio
import logging

from fastapi import APIRouter

from src.web.services.cache import _cached_persistent

logger = logging.getLogger(__name__)

router = APIRouter()


async def _async_cached(cache_key, compute_fn, max_age_hours):
    return await asyncio.to_thread(_cached_persistent, cache_key, compute_fn, max_age_hours)


@router.get("/api/timing/thermometer")
async def api_timing_thermometer():
    """大盘温度计：估值分位 / 趋势状态 / 恐慌仪表 / 波动状态 / 家族份额流 + 仓位合成。"""
    from src.analysis.timing_dashboard import build_thermometer
    return await _async_cached("analysis_timing_thermometer", build_thermometer, 1.0)


@router.get("/api/timing/rotation")
async def api_timing_rotation(preset_id: str = "optimized"):
    """轮动仪表（中信期货双指标框架）：市场情绪 × 轮动强度 → 3×3 决策矩阵。"""
    from src.analysis.rotation_strategy import build_rotation_report
    return await _async_cached(
        f"rotation_report_v1_{preset_id}",
        lambda: build_rotation_report(preset_id),
        1.0,
    )


@router.get("/api/timing/calendar")
async def api_timing_calendar():
    """日历热力图：月度 × ETF 历史平均收益（附有效日历窗口标注）。"""
    from src.analysis.timing_dashboard import build_calendar
    return await _async_cached("analysis_timing_calendar", build_calendar, 6.0)


@router.get("/api/timing/locator")
async def api_timing_locator():
    """底部定位器：深跌 + 家族份额逆势流入的历史事件与当前状态。"""
    from src.analysis.timing_dashboard import build_locator
    return await _async_cached("analysis_timing_locator", build_locator, 1.0)
