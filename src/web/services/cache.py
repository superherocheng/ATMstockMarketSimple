import json
import logging
import threading
import time as _time
from datetime import datetime

from sqlalchemy import text

from config.config import CACHE_MAX_SIZE, CACHE_DEFAULT_TTL
from src.core.trading_calendar import now_beijing

logger = logging.getLogger(__name__)

CACHE_CATEGORIES = {
    "overview": ["overview", "heatmap"],
    "etf": ["index_etf_*", "sector_etf_*", "sector_cards"],
    "stocks": ["stocks_volatility", "stocks_gainers", "stocks_fundamental", "stocks_lhb", "stocks_institute"],
    "stock_detail": ["stock_detail_*"],
    "barra": ["barra_industry", "barra_momentum", "barra_size", "barra_style"],
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


def _db_cache_get(key):
    from src.web.services.db import get_conn
    conn = None
    try:
        conn = get_conn()
        row = conn.execute(
            text("SELECT data_json FROM precomputed_cache WHERE cache_key=:key"),
            {"key": key}
        ).fetchone()
        if row:
            return json.loads(row[0])
        return None
    except Exception:
        return None
    finally:
        if conn:
            conn.close()


def _db_cache_set(key, data):
    from src.web.services.db import get_conn
    conn = None
    try:
        conn = get_conn()
        conn.execute(
            text("""INSERT INTO precomputed_cache (cache_key, updated_at, data_json)
               VALUES (:key, :updated_at, :data_json)
               ON CONFLICT (cache_key)
               DO UPDATE SET updated_at = EXCLUDED.updated_at, data_json = EXCLUDED.data_json"""),
            {"key": key, "updated_at": now_beijing().strftime("%Y%m%d%H%M%S"), "data_json": json.dumps(data, ensure_ascii=False, default=str)},
        )
        conn.commit()
    except Exception:
        pass
    finally:
        if conn:
            conn.close()


def _db_cache_invalidate(*categories):
    from src.web.services.db import get_conn
    conn = None
    try:
        conn = get_conn()
        if not categories:
            conn.execute(text("DELETE FROM precomputed_cache"))
        else:
            for cat in categories:
                for pattern in CACHE_CATEGORIES.get(cat, []):
                    if "*" in pattern:
                        conn.execute(
                            text("DELETE FROM precomputed_cache WHERE cache_key LIKE :pattern"),
                            {"pattern": pattern.replace("*", "%")},
                        )
                    else:
                        conn.execute(
                            text("DELETE FROM precomputed_cache WHERE cache_key=:pattern"),
                            {"pattern": pattern},
                        )
        conn.commit()
    except Exception:
        pass
    finally:
        if conn:
            conn.close()


def _is_data_stale(key, max_age_hours=6):
    from src.web.services.db import get_conn
    conn = None
    try:
        conn = get_conn()
        row = conn.execute(
            text("SELECT updated_at FROM precomputed_cache WHERE cache_key=:key"),
            {"key": key}
        ).fetchone()
        if not row:
            return True
        updated = datetime.strptime(row[0], "%Y%m%d%H%M%S")
        return (now_beijing() - updated).total_seconds() > max_age_hours * 3600
    except Exception:
        return True
    finally:
        if conn:
            conn.close()


def _cached_persistent(key, func, max_age_hours=6):
    from src.web.services.db import safe_dict
    try:
        mem = _cache_get(key)
        if mem is not None:
            return safe_dict(mem)
        if not _is_data_stale(key, max_age_hours):
            db_result = _db_cache_get(key)
            if db_result is not None:
                _cache_set(key, db_result)
                return safe_dict(db_result)
        result = func()
        result = safe_dict(result)
        _cache_set(key, result)
        _db_cache_set(key, result)
        return result
    except Exception as e:
        logger.error(f"_cached_persistent failed for key={key}: {e}", exc_info=True)
        return {"error": str(e)}
