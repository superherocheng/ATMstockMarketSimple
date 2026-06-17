"""FastAPI router for the ETF Rotation Strategy page (中信期货轮动框架实时信号看板)."""
import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.web.services.cache import _cached_persistent

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()


@router.get("/rotation", response_class=HTMLResponse)
async def page_rotation(request: Request):
    """ETF 轮动策略页面（纯骨架，数据由前端 fetch /api/rotation/report）。"""
    return templates.TemplateResponse("rotation.html", {"request": request})


def _rotation_report_sync(preset_id: str):
    return _cached_persistent(
        f"rotation_report_{preset_id}",
        lambda: _build(preset_id),
        max_age_hours=4,
    )


def _build(preset_id: str):
    from src.analysis.rotation_strategy import build_rotation_report
    return build_rotation_report(preset_id)


@router.get("/api/rotation/report")
async def api_rotation_report(preset_id: str = "optimized"):
    """轮动策略完整报告（缓存 4 小时，数据更新时由 fetch 流水线失效）。"""
    return await asyncio.to_thread(_rotation_report_sync, preset_id)
