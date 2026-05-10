"""配置模块单元测试
================
测试配置加载和环境变量处理"""
import os
import pytest
from unittest.mock import patch


class TestTushareToken:
    """Tushare Token 配置测试"""

    def test_token_from_env(self):
        """测试从环境变量加载 Token"""
        with patch.dict(os.environ, {"TUSHARE_TOKEN": "test_token_123"}):
            # Re-import to pick up env change
            import importlib
            import config.config as cfg
            importlib.reload(cfg)
            assert cfg.TUSHARE_TOKEN == "test_token_123"

    def test_token_default_empty(self):
        """测试默认 Token 为空"""
        with patch.dict(os.environ, {}, clear=True):
            # Remove TUSHARE_TOKEN from env if present
            os.environ.pop("TUSHARE_TOKEN", None)
            import importlib
            import config.config as cfg
            importlib.reload(cfg)
            assert cfg.TUSHARE_TOKEN == ""


class TestETFConfig:
    """ETF 字典配置测试"""

    def test_index_etf_contains_major_etfs(self):
        """测试指数 ETF 包含主要宽基"""
        from config.config import INDEX_ETF
        assert "510300.SH" in INDEX_ETF
        assert INDEX_ETF["510300.SH"] == "沪深300ETF"
        assert "510500.SH" in INDEX_ETF
        assert "510050.SH" in INDEX_ETF

    def test_sector_etf_contains_major_etfs(self):
        """测试行业 ETF 包含主要品种"""
        from config.config import SECTOR_ETF
        assert "512480.SH" in SECTOR_ETF
        assert SECTOR_ETF["512480.SH"] == "半导体ETF"
        assert "515030.SH" in SECTOR_ETF

    def test_etf_dicts_are_dicts(self):
        """测试 ETF 配置是字典类型"""
        from config.config import INDEX_ETF, SECTOR_ETF
        assert isinstance(INDEX_ETF, dict)
        assert isinstance(SECTOR_ETF, dict)
        assert len(INDEX_ETF) > 0
        assert len(SECTOR_ETF) > 0


class TestAnalysisParams:
    """分析参数配置测试"""

    def test_lookback_days(self):
        """测试回溯天数"""
        from config.config import LOOKBACK_DAYS
        assert LOOKBACK_DAYS == 260

    def test_anomaly_threshold(self):
        """测试异常检测阈值"""
        from config.config import ANOMALY_STD_THRESHOLD
        assert ANOMALY_STD_THRESHOLD == 2.0
        assert ANOMALY_STD_THRESHOLD > 0


class TestCacheConfig:
    """缓存配置测试"""

    def test_cache_defaults(self):
        """测试缓存默认值"""
        from config.config import CACHE_MAX_SIZE, CACHE_DEFAULT_TTL
        assert CACHE_MAX_SIZE > 0
        assert CACHE_DEFAULT_TTL > 0

    def test_redis_defaults(self):
        """测试 Redis 默认值"""
        from config.config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PREFIX
        assert REDIS_HOST == "localhost"
        assert REDIS_PORT == 6379
        assert REDIS_DB == 0
        assert REDIS_PREFIX == "atm:"

    def test_redis_from_env(self):
        """测试从环境变量加载 Redis 配置"""
        with patch.dict(os.environ, {
            "REDIS_HOST": "redis-server",
            "REDIS_PORT": "6380",
            "REDIS_DB": "2",
            "REDIS_PREFIX": "test:",
        }):
            import importlib
            import config.config as cfg
            importlib.reload(cfg)
            assert cfg.REDIS_HOST == "redis-server"
            assert cfg.REDIS_PORT == 6380
            assert cfg.REDIS_DB == 2
            assert cfg.REDIS_PREFIX == "test:"


class TestGetPro:
    """Tushare Pro 接口测试"""

    def test_get_pro_raises_without_token(self):
        """测试无 Token 时抛出异常"""
        from config.config import get_pro
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("TUSHARE_TOKEN", None)
            import importlib
            import config.config as cfg
            importlib.reload(cfg)
            with pytest.raises(ValueError, match="请先配置"):
                cfg.get_pro()

    def test_project_paths(self):
        """测试项目路径配置"""
        from config.config import PROJECT_ROOT, DATA_DIR, EXTERNAL_DATA_DIR
        assert PROJECT_ROOT.exists()
        assert "data" in str(DATA_DIR)
        assert "external" in str(EXTERNAL_DATA_DIR)
