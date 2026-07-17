"""
ATMstockMarket Web Application
"""
import logging
import os
import sys
import hmac
from typing import Optional
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
STATIC_DIR = BASE_DIR / "static"
ENV_FILE = PROJECT_ROOT / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ── Suppress 404 scanner noise from uvicorn access logs ──
# External bots hit the public domain thousands of times/day.
# Filter out 4xx to keep logs clean for real debugging.
import re
_SCANNER_PATTERNS = re.compile(
    r'GET /(static/|api/|health|docs|redoc|openapi\.json)|'
    r'HEAD / HTTP'
)
class _AccessFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        if '"GET' in msg or '"POST' in msg or '"HEAD' in msg:
            # Allow API calls, health checks, and static files
            if _SCANNER_PATTERNS.search(msg):
                return True
            # Filter out 4xx responses
            if ' 4' in msg and '" "' in msg:
                return False
        return True

# Apply filter to uvicorn access logger
for name in ('uvicorn.access', 'uvicorn'):
    access_logger = logging.getLogger(name)
    access_logger.addFilter(_AccessFilter())
    access_logger.setLevel(logging.INFO)

from src.core.db_manager_postgresql import _ensure_db, close_db_manager
from starlette.middleware.gzip import GZipMiddleware
from src.web.services.middleware import rate_limit_middleware, add_cache_headers
from src.web.routers import overview, etf, fetch, analysis, telemetry

# ── 认证配置 ────────────────────────────────────────────────
# 从环境变量读取 API_TOKEN，None 表示不启用认证（内网访问模式）
API_TOKEN = os.environ.get("API_TOKEN")


# ── 统一响应模型 ────────────────────────────────────────────

class APIResponse(BaseModel):
    """统一 API 响应格式"""
    success: bool
    data: object = None
    error: str = None
    timestamp: str = None


# ── 认证装饰器 ──────────────────────────────────────────────

WRITE_ENDPOINT_PREFIXES = (
    "/api/fetch/",
    "/api/cache/invalidate",
    "/api/etf-share/update",
    "/api/analysis/recompute",
)


def auth_required(request: Request) -> Optional[str]:
    """
    检查请求的 Authorization header。
    如果 API_TOKEN 未设置（None），则跳过认证（内网模式）。
    返回 token 中的用户标识或 None（认证失败）。
    """
    if API_TOKEN is None:
        return "internal"  # 内网模式，无需认证

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[len("Bearer "):]
    if not hmac.compare_digest(token, API_TOKEN):
        return None
    return "api_user"


# ── CSRF 保护 ──────────────────────────────────────────────

def _get_allowed_origins(request: Request) -> list[str]:
    """获取允许的来源列表，包含本机地址"""
    host = request.headers.get("Host", "")
    origins = [
        f"http://{host}",
        f"https://{host}",
    ]
    # 添加常见本地地址
    for addr in ("localhost", "127.0.0.1", "0.0.0.0"):
        if addr not in host:
            origins.append(f"http://{addr}:{host.split(':')[-1]}" if ":" in host else f"http://{addr}:5656")
    return origins


def _check_csrf(request: Request) -> bool:
    """
    对 POST 请求执行简单的 CSRF 检查：
    1. 检查 Origin 或 Referer header 是否匹配允许的来源
    2. 如果两个 header 都不存在（如 curl、服务端调用），允许通过
       — 认证由后续 auth_middleware 的 Bearer Token 兜底
    """
    origin = request.headers.get("Origin", "")
    referer = request.headers.get("Referer", "")

    # 无浏览器头的请求（curl/服务端调用）跳过 CSRF，依赖 Token 认证
    if not origin and not referer:
        return True

    allowed = _get_allowed_origins(request)

    check_str = origin or referer
    for a in allowed:
        if check_str.startswith(a):
            return True
    return False


# ── 生命周期 ────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app):
    logger.info("ATMstockMarket Web服务启动中...")
    try:
        _ensure_db()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
    yield
    logger.info("ATMstockMarket Web服务关闭中...")
    try:
        close_db_manager()
        logger.info("数据库连接已关闭")
    except Exception as e:
        logger.error(f"关闭数据库连接时出错: {e}")


# ── 应用初始化 ──────────────────────────────────────────────

API_TAGS = [
    {"name": "Overview", "description": "概览页面和数据范围"},
    {"name": "ETF", "description": "ETF 行情和份额数据"},
    {"name": "Analysis", "description": "量化分析和投资建议"},
    {"name": "Fetch", "description": "数据获取和缓存管理"},
    {"name": "Telemetry", "description": "遥测与健康检查"},
]

app = FastAPI(
    title="ATMstockMarket",
    description="A股ETF量化监控平台",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/api/openapi.json",
    contact={"name": "ATMstockMarket Team"},
    license_info={"name": "MIT"},
)


# ── 认证中间件 ──────────────────────────────────────────────

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """检查写操作端点是否需要认证"""
    path = request.url.path
    method = request.method

    if method == "POST" and path.startswith("/api/") and not path.startswith("/api/openapi"):
        # 检查 CSRF（只针对 POST）
        if not _check_csrf(request):
            return JSONResponse(
                status_code=403,
                content=APIResponse(
                    success=False,
                    error="CSRF 验证失败：缺少或无效的 Origin/Referer header",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                ).model_dump(),
            )

        # 检查认证
        if path.startswith(WRITE_ENDPOINT_PREFIXES):
            user = auth_required(request)
            if user is None:
                return JSONResponse(
                    status_code=401,
                    content=APIResponse(
                        success=False,
                        error="未授权：请提供有效的 API Token（Authorization: Bearer <token>）",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    ).model_dump(),
                )

    response = await call_next(request)
    return response


# ── 全局异常处理器 ──────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """统一异常处理，所有异常返回统一的 APIResponse 格式"""
    logger.error("未捕获异常: %s | path=%s", exc, request.url.path, exc_info=True)
    status_code = 500
    error_msg = "服务器内部错误"
    if isinstance(exc, HTTPException):
        status_code = exc.status_code
        error_msg = exc.detail
    return JSONResponse(
        status_code=status_code,
        content=APIResponse(
            success=False,
            error=error_msg,
            timestamp=datetime.now(timezone.utc).isoformat(),
        ).model_dump(),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTPException 统一处理"""
    return JSONResponse(
        status_code=exc.status_code,
        content=APIResponse(
            success=False,
            error=exc.detail,
            timestamp=datetime.now(timezone.utc).isoformat(),
        ).model_dump(),
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=404,
        content=APIResponse(
            success=False,
            error="请求的资源不存在",
            timestamp=datetime.now(timezone.utc).isoformat(),
        ).model_dump(),
    )


app.add_middleware(GZipMiddleware, minimum_size=1000)
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(add_cache_headers)

# ── 静态文件 ────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(overview.router)
app.include_router(etf.router)
app.include_router(fetch.router)
app.include_router(analysis.router)

app.include_router(telemetry.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.web.app:app", host="0.0.0.0", port=5656, reload=False)