"""Minimal telemetry endpoint for anonymous usage stats."""
import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/telemetry")
async def telemetry(request: Request):
    try:
        data = await request.json()
        path = data.get("path", "unknown")
        ref = data.get("ref", "")
        w = data.get("w", 0)
        ua = (data.get("ua", "") or "")[:60]
        logger.info(f"[TELEM] path={path} ref={ref} w={w} ua={ua}")
    except Exception:
        pass
    return JSONResponse({"ok": True})
