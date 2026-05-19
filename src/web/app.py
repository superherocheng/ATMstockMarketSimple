"""
ATMstockMarket Web Application
"""
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)



logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

from src.core.db_manager_postgresql import _ensure_db, close_db_manager
from starlette.middleware.gzip import GZipMiddleware
from src.web.services.middleware import rate_limit_middleware, add_cache_headers
from src.web.routers import overview, etf, fetch, analysis, telemetry


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


app = FastAPI(title="ATMstockMarket", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(add_cache_headers)

app.include_router(overview.router)
app.include_router(etf.router)
app.include_router(fetch.router)
app.include_router(analysis.router)

app.include_router(telemetry.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.web.app:app", host="0.0.0.0", port=8000, reload=False)
