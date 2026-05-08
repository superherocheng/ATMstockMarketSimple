import threading
import time as _time

from fastapi import Request
from fastapi.responses import JSONResponse


class RateLimiter:
    """简单的速率限制器（基于IP地址）"""

    def __init__(self, requests_per_minute: int = 60):
        self.rpm = requests_per_minute
        self.requests = {}
        self.lock = threading.Lock()

    def is_allowed(self, client_id: str) -> bool:
        now = _time.time()
        with self.lock:
            if client_id in self.requests:
                self.requests[client_id] = [
                    t for t in self.requests[client_id]
                    if now - t < 60
                ]
            if len(self.requests.get(client_id, [])) >= self.rpm:
                return False
            if client_id not in self.requests:
                self.requests[client_id] = []
            self.requests[client_id].append(now)
            return True


_rate_limiter = RateLimiter(requests_per_minute=60)


async def rate_limit_middleware(request: Request, call_next):
    """速率限制中间件"""
    if request.url.path.startswith("/api/"):
        client_id = request.client.host if request.client else "unknown"
        if not _rate_limiter.is_allowed(client_id):
            return JSONResponse(
                {"error": "请求过于频繁，请稍后再试", "retry_after": 60},
                status_code=429
            )
    return await call_next(request)


async def add_cache_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path

    if path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=86400"
        response.headers["Vary"] = "Accept-Encoding"
    elif path.startswith("/api/") and request.method == "GET":
        if "/fetch/" in path or "/update" in path or "/cache" in path:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        else:
            response.headers["Cache-Control"] = "public, max-age=300"
    elif path.startswith("/api/") and request.method == "POST":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"

    return response
