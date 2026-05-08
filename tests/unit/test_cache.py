"""
线程安全缓存测试
================
测试 ThreadSafeCache 类的功能
"""
import pytest
import time
import threading
from unittest.mock import Mock


class TestThreadSafeCache:
    """线程安全缓存测试"""
    
    def test_initialization(self):
        """测试初始化"""
        from src.web.services.cache import ThreadSafeCache
        cache = ThreadSafeCache(maxsize=100, default_ttl=60)
        assert cache._maxsize == 100
        assert cache._default_ttl == 60
        assert len(cache) == 0
    
    def test_set_and_get(self):
        """测试基本的设置和获取"""
        from src.web.services.cache import ThreadSafeCache
        cache = ThreadSafeCache()
        
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
    
    def test_get_nonexistent_key(self):
        """测试获取不存在的键"""
        from src.web.services.cache import ThreadSafeCache
        cache = ThreadSafeCache()
        
        assert cache.get("nonexistent") is None
    
    def test_overwrite_key(self):
        """测试覆盖已存在的键"""
        from src.web.services.cache import ThreadSafeCache
        cache = ThreadSafeCache()
        
        cache.set("key1", "value1")
        cache.set("key1", "value2")
        assert cache.get("key1") == "value2"
    
    def test_ttl_expiration(self):
        """测试 TTL 过期"""
        from src.web.services.cache import ThreadSafeCache
        cache = ThreadSafeCache()
        
        cache.set("key1", "value1", ttl=0.1)
        assert cache.get("key1") == "value1"
        
        time.sleep(0.15)
        assert cache.get("key1") is None
    
    def test_default_ttl(self):
        """测试默认 TTL"""
        from src.web.services.cache import ThreadSafeCache
        cache = ThreadSafeCache(default_ttl=0.1)
        
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        
        time.sleep(0.15)
        assert cache.get("key1") is None
    
    def test_lru_eviction(self):
        """测试 LRU 淘汰"""
        from src.web.services.cache import ThreadSafeCache
        cache = ThreadSafeCache(maxsize=3)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        
        assert len(cache) == 3
        
        cache.set("key4", "value4")
        
        assert len(cache) == 3
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"
    
    def test_lru_access_order(self):
        """测试 LRU 访问顺序"""
        from src.web.services.cache import ThreadSafeCache
        cache = ThreadSafeCache(maxsize=3)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        
        cache.get("key1")
        
        cache.set("key4", "value4")
        
        assert cache.get("key1") == "value1"
        assert cache.get("key2") is None
    
    def test_get_or_set_existing(self):
        """测试 get_or_set 已存在的键"""
        from src.web.services.cache import ThreadSafeCache
        cache = ThreadSafeCache()
        
        cache.set("key1", "value1")
        
        result = cache.get_or_set("key1", lambda: "new_value")
        assert result == "value1"
    
    def test_get_or_set_nonexistent(self):
        """测试 get_or_set 不存在的键"""
        from src.web.services.cache import ThreadSafeCache
        cache = ThreadSafeCache()
        
        result = cache.get_or_set("key1", lambda: "computed_value")
        assert result == "computed_value"
        assert cache.get("key1") == "computed_value"
    
    def test_invalidate_all(self):
        """测试清空所有缓存"""
        from src.web.services.cache import ThreadSafeCache
        cache = ThreadSafeCache()
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        cache.invalidate()
        
        assert len(cache) == 0
        assert cache.get("key1") is None
        assert cache.get("key2") is None
    
    def test_clear_expired(self):
        """测试清理过期条目"""
        from src.web.services.cache import ThreadSafeCache
        cache = ThreadSafeCache()
        
        cache.set("key1", "value1", ttl=0.1)
        cache.set("key2", "value2")
        
        time.sleep(0.15)
        
        cache.clear_expired()
        
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
    
    def test_concurrent_access(self):
        """测试并发访问"""
        from src.web.services.cache import ThreadSafeCache
        cache = ThreadSafeCache(maxsize=1000)
        
        def writer(start, count):
            for i in range(start, start + count):
                cache.set(f"key_{i}", f"value_{i}")
        
        def reader(start, count):
            for i in range(start, start + count):
                cache.get(f"key_{i}")
        
        threads = [
            threading.Thread(target=writer, args=(0, 100)),
            threading.Thread(target=writer, args=(100, 100)),
            threading.Thread(target=reader, args=(0, 100)),
            threading.Thread(target=reader, args=(100, 100)),
        ]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        assert len(cache) <= 1000
