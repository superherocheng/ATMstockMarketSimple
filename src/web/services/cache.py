import json
import logging
import threading
import time as _time

from config.config import CACHE_MAX_SIZE, CACHE_DEFAULT_TTL

logger = logging.getLogger(__name__)

CACHE_CATEGORIES = {
    "overview": ["overview", "heatmap"],
    "etf": ["index_etf_*", "sector_etf_*", "sector_cards"],
}


class ThreadSafeCache:
    """线程安全的缓存类，支持 maxsize 和 TTL"""

    def __init__(self, maxsize: int = 1000, default_ttl: float = None):
        self._cache = {}
        self._access_order = []
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
                if key in self._access_order:
                    self._access_order.remove(key)
                return None
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            return value

    def set(self, key, value, ttl: float = None):
        with self._lock:
            expire_at = None
            if ttl is not None:
                expire_at = _time.time() + ttl
            elif self._default_ttl is not None:
                expire_at = _time.time() + self._default_ttl

            if key in self._cache:
                if key in self._access_order:
                    self._access_order.remove(key)
            elif len(self._cache) >= self._maxsize:
                self._evict_lru()

            self._cache[key] = (value, expire_at)
            self._access_order.append(key)

    def get_or_set(self, key, func, *args, ttl: float = None, **kwargs):
        with self._lock:
            entry = self._cache.get(key)
            if entry is not None:
                value, expire_at = entry
                if expire_at is None or _time.time() <= expire_at:
                    if key in self._access_order:
                        self._access_order.remove(key)
                    self._access_order.append(key)
                    return value

            result = func(*args, **kwargs)
            self.set(key, result, ttl=ttl)
            return result

    def _evict_lru(self):
        if self._access_order:
            lru_key = self._access_order.pop(0)
            self._cache.pop(lru_key, None)

    def invalidate(self, *categories):
        with self._lock:
            if not categories:
                self._cache.clear()
                self._access_order.clear()
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
                if k in self._access_order:
                    self._access_order.remove(k)

    def clear_expired(self):
        with self._lock:
            now = _time.time()
            expired_keys = [
                k for k, (_, expire_at) in self._cache.items()
                if expire_at is not None and now > expire_at
            ]
            for k in expired_keys:
                self._cache.pop(k, None)
                if k in self._access_order:
                    self._access_order.remove(k)

    def __len__(self):
        return len(self._cache)


_api_cache = ThreadSafeCache(maxsize=CACHE_MAX_SIZE, default_ttl=CACHE_DEFAULT_TTL)


def _cache_get(key):
    return _api_cache.get(key)


def _cache_set(key, value):
    _api_cache.set(key, value)


def _cache_invalidate(*categories):
    _api_cache.invalidate(*categories)


def _cached(key, func, *args, **kwargs):
    return _api_cache.get_or_set(key, func, *args, **kwargs)


def _cached_persistent(key, func, max_age_hours=6):
    """Cache with in-memory LRU only (no DB tier)."""
    from src.core.db_manager_postgresql import safe_dict
    try:
        result = _api_cache.get(key)
        if result is not None:
            return safe_dict(result)
        result = func()
        result = safe_dict(result)
        _api_cache.set(key, result)
        return result
    except Exception as e:
        logger.error(f"_cached_persistent failed for key={key}: {e}", exc_info=True)
        return {"error": str(e)}