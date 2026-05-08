"""
ATMstockMarket 测试配置
=======================
提供测试fixtures和共享配置
"""
import pytest
from pathlib import Path
import sys

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def sample_ts_codes():
    """示例股票代码"""
    return [
        "600000.SH",  # 浦发银行
        "000001.SZ",  # 平安银行
        "000002.SZ",  # 万科A
    ]


@pytest.fixture
def sample_etf_codes():
    """示例ETF代码"""
    return {
        "510300.SH": "沪深300ETF",
        "510500.SH": "中证500ETF",
        "510050.SH": "上证50ETF",
    }
