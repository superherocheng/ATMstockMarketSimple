"""
ATMstockMarket — 两级缓存系统
=============================
Redis（主）+ 内存 LRU（快速回退）

结构：
  get(key)        → Redis → 内存 → None
  set(key, val)   → Redis + 内存
  invalidate()    → Redis + 内存
"""
import json
import logging
import threading
import time as _time
from collections import OrderedDict

from config.config import (
    CACHE_MAX_SIZE, CACHE_DEFAULT_TTL,
    REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PREFIX,
)

logger = logging.getLogger(__name__)

# ── 可选 Redis 客户端 ───────────────────────────────────────
_redis_client = None
_redis_available = False
_last_redis_check = 0.0
_REDIS_CHECK_INTERVAL = 30  # 每30秒检查一次Redis连接


def _ensure_redis():
    """尝试建立或恢复 Redis 连接，失败时不抛出异常"""
    global _redis_client, _redis_available, _last_redis_check
    now = _time.time()
    if now - _last_redis_check < _REDIS_CHECK_INTERVAL:
        return _redis_client if _redis_available else None
    _last_redis_check = now

    if _redis_client is not None:
        try:
            _redis_client.ping()
            _redis_available = True
            return _redis_client
        except Exception:
            # 连接已断开，尝试重连
            _redis_client = None
            _redis_available = False
            logger.warning("Redis 连接断开，尝试重连...")

    try:
        import redis
        _redis_client = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
            socket_connect_timeout=1, socket_timeout=2,
            decode_responses=True,
        )
        _redis_client.ping()
        _redis_available = True
        logger.info("Redis 缓存已连接 %s:%s/%s", REDIS_HOST, REDIS_PORT, REDIS_DB)
    except Exception as e:
        _redis_client = None
        _redis_available = False
        logger.warning("Redis 不可用，回退到内存缓存: %s", e)
    return _redis_client if _redis_available else None


def _get_redis():
    """获取 Redis 客户端（带健康检查，30秒间隔）"""
    return _ensure_redis()


def _redis_key(key):
    return REDIS_PREFIX + key


def _redis_get(key):
    r = _get_redis()
    if r is None:
        return None
    try:
        val = r.get(_redis_key(key))
        if val is not None:
            return json.loads(val)
    except Exception:
        pass
    return None


def _redis_set(key, value, ttl=None):
    r = _get_redis()
    if r is None:
        return
    try:
        r.setex(_redis_key(key), ttl or CACHE_DEFAULT_TTL, json.dumps(value, default=str))
    except Exception as e:
        logger.warning("Redis set 失败 (%s): %s", key, e)


def _redis_delete(pattern):
    """删除匹配 pattern* 的所有 Redis 键（使用 SCAN 代替 KEYS）"""
    r = _get_redis()
    if r is None:
        return
    try:
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor, match=_redis_key(pattern) + "*", count=100)
            if keys:
                r.delete(*keys)
            if cursor == 0:
                break
    except Exception:
        pass


# ── 内存 LRU 缓存 ──────────────────────────────────────────

CACHE_CATEGORIES = {
    "overview": ["overview"],
    "etf": ["index_etf_*", "sector_etf_*", "sector_cards", "share_std_*"],
    "analysis": ["analysis_*", "investment_rec_v2_*", "investment_recommendation"],
}


class ThreadSafeCache:
    """线程安全的内存 LRU 缓存，支持 TTL（OrderedDict 实现 O(1) 操作）"""

    def __init__(self, maxsize: int = 1000, default_ttl: float = None):
        self._cache = OrderedDict()
        self._lock = threading.RLock()
        self._maxsize = maxsize
        self._default_ttl = default_ttl

    def get(self, key):
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            value, expire_at = entry
            if expire_at is not None and _time.time() > expire_at:
                self._cache.pop(key, None)
                return None
            self._cache.move_to_end(key)
            return value

    def set(self, key, value, ttl: float = None):
        with self._lock:
            expire_at = None
            if ttl is not None:
                expire_at = _time.time() + ttl
            elif self._default_ttl is not None:
                expire_at = _time.time() + self._default_ttl
            if key in self._cache:
                self._cache.pop(key)
            elif len(self._cache) >= self._maxsize:
                self._evict_lru()
            self._cache[key] = (value, expire_at)
            self._cache.move_to_end(key)

    def get_or_set(self, key, func, *args, ttl: float = None, **kwargs):
        with self._lock:
            entry = self._cache.get(key)
            if entry is not None:
                value, expire_at = entry
                if expire_at is None or _time.time() <= expire_at:
                    self._cache.move_to_end(key)
                    return value
            result = func(*args, **kwargs)
            self.set(key, result, ttl=ttl)
            return result

    def _evict_lru(self):
        if self._cache:
            self._cache.popitem(last=False)

    def invalidate(self, *categories):
        with self._lock:
            if not categories:
                self._cache.clear()
                return
            keys_to_delete = set()
            for cat in categories:
                for pattern in CACHE_CATEGORIES.get(cat, []):
                    if "*" in pattern:
                        prefix = pattern.rstrip("*")
                        keys_to_delete.update(k for k in self._cache if k.startswith(prefix))
                    else:
                        keys_to_delete.add(pattern)
            for k in keys_to_delete:
                self._cache.pop(k, None)

    def clear_expired(self):
        with self._lock:
            now = _time.time()
            expired_keys = [
                k for k, (_, expire_at) in self._cache.items()
                if expire_at is not None and now > expire_at
            ]
            for k in expired_keys:
                self._cache.pop(k, None)

    def __len__(self):
        return len(self._cache)


_api_cache = ThreadSafeCache(maxsize=CACHE_MAX_SIZE, default_ttl=CACHE_DEFAULT_TTL)


# ── 公开 API ───────────────────────────────────────────────

def _cache_get(key):
    """两级缓存读：Redis → 内存"""
    # 优先读 Redis
    val = _redis_get(key)
    if val is not None:
        _api_cache.set(key, val)
        return val
    # 回退到内存
    return _api_cache.get(key)


def _cache_set(key, value, ttl=None):
    """两级缓存写：Redis + 内存"""
    _redis_set(key, value, ttl=ttl or CACHE_DEFAULT_TTL)
    _api_cache.set(key, value, ttl=ttl)


def _cache_invalidate(*categories):
    """两级缓存清除"""
    if not categories:
        _redis_delete("")
        _api_cache.invalidate()
    else:
        for cat in categories:
            for pattern in CACHE_CATEGORIES.get(cat, []):
                _redis_delete(pattern.rstrip("*"))
        _api_cache.invalidate(*categories)


def _cached(key, func, *args, ttl=None, **kwargs):
    """get_or_set：Redis → 内存 → 计算"""
    val = _cache_get(key)
    if val is not None:
        return val
    result = func(*args, **kwargs)
    _cache_set(key, result, ttl=ttl)
    return result


def _cached_persistent(key, func, max_age_hours=6):
    """持久化缓存的快捷方法（两级缓存）"""
    from src.core.db_manager_postgresql import safe_dict
    ttl_sec = int(max_age_hours * 3600)
    try:
        val = _cache_get(key)
        if val is not None:
            return safe_dict(val)
        result = func()
        result = safe_dict(result)
        _cache_set(key, result, ttl=ttl_sec)
        return result
    except Exception as e:
        logger.error("_cached_persistent failed for key=%s: %s", key, e, exc_info=True)
        return {"error": str(e)}
