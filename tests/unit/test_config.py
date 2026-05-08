"""
配置模块单元测试
================
测试配置加载和环境变量处理
"""
import pytest
import os
from unittest.mock import patch


class TestDatabaseConfig:
    """数据库配置测试"""
    
    def test_default_values(self):
        """测试默认值"""
        from config.config import DatabaseConfig
        config = DatabaseConfig()
        assert config.threads == 4
        assert config.memory_limit == '2GB'
        assert config.temp_directory is None
    
    def test_from_env(self):
        """测试从环境变量加载"""
        from config.config import DatabaseConfig
        with patch.dict(os.environ, {
            'DB_THREADS': '8',
            'DB_MEMORY_LIMIT': '4GB',
            'DB_TEMP_DIRECTORY': '/tmp/duckdb'
        }):
            config = DatabaseConfig.from_env()
            assert config.threads == 8
            assert config.memory_limit == '4GB'
            assert config.temp_directory == '/tmp/duckdb'


class TestFetcherConfig:
    """数据获取配置测试"""
    
    def test_default_values(self):
        """测试默认值"""
        from config.config import FetcherConfig
        config = FetcherConfig()
        assert config.retry_max == 3
        assert config.throttle_sec == 0.35
        assert config.write_batch == 10
        assert config.concurrency == 4
    
    def test_from_env(self):
        """测试从环境变量加载"""
        from config.config import FetcherConfig
        with patch.dict(os.environ, {
            'RETRY_MAX': '5',
            'API_THROTTLE_SEC': '0.5',
            'WRITE_BATCH': '20',
            'FETCH_CONCURRENCY': '8'
        }):
            config = FetcherConfig.from_env()
            assert config.retry_max == 5
            assert config.throttle_sec == 0.5
            assert config.write_batch == 20
            assert config.concurrency == 8


class TestAnalysisConfig:
    """分析配置测试"""
    
    def test_default_values(self):
        """测试默认值"""
        from config.config import AnalysisConfig
        config = AnalysisConfig()
        assert config.anomaly_std_threshold == 2.0
        assert config.lookback_days == 260
        assert config.volatility_window == 20
    
    def test_from_env(self):
        """测试从环境变量加载"""
        from config.config import AnalysisConfig
        with patch.dict(os.environ, {
            'ANOMALY_STD': '3.0',
            'LOOKBACK_DAYS': '365',
            'VOLATILITY_WINDOW': '30'
        }):
            config = AnalysisConfig.from_env()
            assert config.anomaly_std_threshold == 3.0
            assert config.lookback_days == 365
            assert config.volatility_window == 30


class TestRateLimitConfig:
    """速率限制配置测试"""
    
    def test_default_values(self):
        """测试默认值"""
        from config.config import RateLimitConfig
        config = RateLimitConfig()
        assert config.enabled == True
        assert config.requests_per_minute == 60
    
    def test_from_env(self):
        """测试从环境变量加载"""
        from config.config import RateLimitConfig
        with patch.dict(os.environ, {
            'RATE_LIMIT_ENABLED': 'false',
            'RATE_LIMIT_RPM': '120'
        }):
            config = RateLimitConfig.from_env()
            assert config.enabled == False
            assert config.requests_per_minute == 120


class TestAppConfig:
    """应用总配置测试"""
    
    def test_from_env(self):
        """测试从环境变量加载完整配置"""
        from config.config import AppConfig
        with patch.dict(os.environ, {
            'TUSHARE_TOKEN': 'test_token_123',
            'DB_THREADS': '6',
            'API_THROTTLE_SEC': '0.4',
            'ANOMALY_STD': '2.5',
            'RATE_LIMIT_RPM': '100'
        }):
            config = AppConfig.from_env()
            assert config.tushare_token == 'test_token_123'
            assert config.database.threads == 6
            assert config.fetcher.throttle_sec == 0.4
            assert config.analysis.anomaly_std_threshold == 2.5
            assert config.rate_limit.requests_per_minute == 100
    
    def test_etf_dictionaries(self):
        """测试ETF字典配置"""
        from config.config import AppConfig
        config = AppConfig(tushare_token='test')
        
        assert '510300.SH' in config.index_etf
        assert config.index_etf['510300.SH'] == '沪深300ETF'
        
        assert '512480.SH' in config.sector_etf
        assert config.sector_etf['512480.SH'] == '半导体ETF'


class TestGetConfig:
    """配置单例测试"""
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        from config.config import get_config
        import config.config as config_module
        
        # 重置单例
        config_module._config = None
        
        config1 = get_config()
        config2 = get_config()
        
        assert config1 is config2
