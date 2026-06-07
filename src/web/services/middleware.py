import threading
import time as _time

from fastapi import Request
from fastapi.responses import JSONResponse


class RateLimiter:
    """简单的速率限制器（基于IP地址），带定期过期IP清理"""

    def __init__(self, requests_per_minute: int = 60):
        self.rpm = requests_per_minute
        self.requests = {}
        self.lock = threading.Lock()
        self._check_count = 0
        self._cleanup_interval = 100  # 每100次检查触发一次清理
        self._start_periodic_cleanup()

    def _start_periodic_cleanup(self):
        """启动定时清理任务（每5分钟清理一次过期IP）"""
        timer = threading.Timer(300.0, self._periodic_cleanup)
        timer.daemon = True
        timer.start()

    def _periodic_cleanup(self):
        """定时清理所有过期IP记录"""
        self._cleanup()
        # 重新启动定时器
        timer = threading.Timer(300.0, self._periodic_cleanup)
        timer.daemon = True
        timer.start()

    def _cleanup(self):
        """清理所有过期IP记录（超过60秒无请求的条目）"""
        now = _time.time()
        with self.lock:
            expired_keys = [
                k for k, timestamps in list(self.requests.items())
                if all(now - t >= 60 for t in timestamps)
            ]
            for k in expired_keys:
                del self.requests[k]

    def is_allowed(self, client_id: str) -> bool:
        now = _time.time()
        with self.lock:
            self._check_count += 1
            if self._check_count % self._cleanup_interval == 0:
                self._cleanup()

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


_rate_limiter = RateLimiter(requests_per_minute=200)


async def rate_limit_middleware(request: Request, call_next):
    """速率限制中间件"""
    if request.url.path.startswith("/api/"):
        client_id = request.headers.get("X-Forwarded-For", "")
        if client_id:
            client_id = client_id.split(",")[0].strip()
        if not client_id:
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
