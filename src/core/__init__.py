"""
ATMstockMarket 核心模块
======================
提供数据库管理、交易日历、配置管理等基础功能
"""
from src.core.db_manager_postgresql import init_db_manager, get_db_manager, get_conn
from src.core.trading_calendar import (
    now_beijing,
    get_latest_trading_date,
    get_open_trade_dates,
    is_fresh,
    get_dates_to_fetch,
    verify_database,
)
from config.config import (
    get_pro,
    DATA_DIR,
    EXTERNAL_DATA_DIR,
    INDEX_ETF,
    SECTOR_ETF,
    LOOKBACK_DAYS,
    ANOMALY_STD_THRESHOLD,
)

__all__ = [
    "init_db_manager",
    "get_db_manager",
    "get_conn",
    "now_beijing",
    "get_latest_trading_date",
    "get_open_trade_dates",
    "is_fresh",
    "get_dates_to_fetch",
    "verify_database",
    "get_pro",
    "DATA_DIR",
    "EXTERNAL_DATA_DIR",
    "INDEX_ETF",
    "SECTOR_ETF",
    "LOOKBACK_DAYS",
    "ANOMALY_STD_THRESHOLD",
]
