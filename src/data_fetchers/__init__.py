"""
ATMstockMarket 数据获取模块
==========================
提供 Tushare、AKShare 等数据源的统一接口
"""
from src.data_fetchers.tushare_fetcher import (
    init_db,
    fetch_index_etf,
    fetch_sector_etf,
    fetch_stock_list,
    fetch_stock_daily,
    fetch_daily_basic,
    fetch_fina_indicator,
)
from src.data_fetchers.external_loader import load_csv_data, extract_and_load_data
__all__ = [
    "init_db",
    "fetch_index_etf",
    "fetch_sector_etf",
    "fetch_stock_list",
    "fetch_stock_daily",
    "fetch_daily_basic",
    "fetch_fina_indicator",
]
