"""因子引擎单元测试"""
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock


class TestComputeFlow:
    """测试 Flow (份额趋势) 计算"""

    def test_rising_shares_positive_flow(self):
        """持续增长的份额 → 正 Flow"""
        from src.analysis.factor_engine import _compute_flow

        shares = pd.Series([100, 102, 104, 106, 108, 110, 112, 114, 116, 118],
                           name="fd_share")
        flow = _compute_flow(shares, lookback=10)
        assert flow > 0

    def test_declining_shares_negative_flow(self):
        """持续减少的份额 → 负 Flow"""
        from src.analysis.factor_engine import _compute_flow

        shares = pd.Series([120, 118, 116, 114, 112, 110, 108, 106, 104, 102],
                           name="fd_share")
        flow = _compute_flow(shares, lookback=10)
        assert flow < 0

    def test_insufficient_data_returns_nan(self):
        """数据不足 → NaN"""
        from src.analysis.factor_engine import _compute_flow

        shares = pd.Series([100, 102], name="fd_share")
        flow = _compute_flow(shares, lookback=10)
        assert pd.isna(flow)


class TestComputeMom:
    """测试 Momentum (价格动量) 计算"""

    def test_rising_price_positive_mom(self):
        """价格上涨 → 正动量"""
        from src.analysis.factor_engine import _compute_mom

        closes = pd.Series([10.0, 10.5, 11.0, 11.5, 12.0, 12.5, 13.0, 13.5, 14.0, 14.5,
                            15.0, 15.5, 16.0, 16.5, 17.0, 17.5, 18.0, 18.5, 19.0, 19.5,
                            20.0], name="close")
        mom = _compute_mom(closes, lookback=20)
        assert mom > 0

    def test_falling_price_negative_mom(self):
        """价格下跌 → 负动量"""
        from src.analysis.factor_engine import _compute_mom

        closes = pd.Series([20.0, 19.5, 19.0, 18.5, 18.0, 17.5, 17.0, 16.5, 16.0, 15.5,
                            15.0, 14.5, 14.0, 13.5, 13.0, 12.5, 12.0, 11.5, 11.0, 10.5,
                            10.0], name="close")
        mom = _compute_mom(closes, lookback=20)
        assert mom < 0

    def test_insufficient_data_returns_nan(self):
        """数据不足 → NaN"""
        from src.analysis.factor_engine import _compute_mom

        closes = pd.Series([10.0, 11.0], name="close")
        mom = _compute_mom(closes, lookback=20)
        assert pd.isna(mom)


class TestCrossSectionalZscore:
    """测试横截面 Z-score"""

    def test_zscore_basic(self):
        """基本 Z-score 计算"""
        from src.analysis.factor_engine import _cross_sectional_zscore

        values = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        z = _cross_sectional_zscore(values)
        assert len(z) == 5
        assert abs(z.mean()) < 1e-10

    def test_zero_std_returns_zero(self):
        """标准差为零 → 全部返回 0"""
        from src.analysis.factor_engine import _cross_sectional_zscore

        values = pd.Series([3.0, 3.0, 3.0])
        z = _cross_sectional_zscore(values)
        assert (z == 0).all()


class TestQuadrantClassification:
    """测试四象限分类"""

    def test_q1_strong(self):
        from src.analysis.factor_engine import _classify_quadrant
        assert _classify_quadrant(0.5, 0.5) == 1

    def test_q2_lurk(self):
        from src.analysis.factor_engine import _classify_quadrant
        assert _classify_quadrant(0.5, -0.5) == 2

    def test_q3_exit(self):
        from src.analysis.factor_engine import _classify_quadrant
        assert _classify_quadrant(-0.5, -0.5) == 3

    def test_q4_risk(self):
        from src.analysis.factor_engine import _classify_quadrant
        assert _classify_quadrant(-0.5, 0.5) == 4


class TestComputeFactorsForDate:
    """测试单日因子计算集成"""

    def test_returns_dataframe_with_expected_columns(self):
        from src.analysis.factor_engine import compute_factors_for_date

        n = 30
        dates = pd.date_range("2025-01-01", periods=n, freq="D")
        kline_data = []
        share_data = []
        for code in ["A", "B", "C"]:
            for i, d in enumerate(dates):
                price = 10.0 + i * 0.1
                kline_data.append({"ts_code": code, "trade_date": d, "close": price,
                                   "pct_chg": 1.0})
                share_data.append({"ts_code": code, "trade_date": d, "fd_share": 1000 + i * 10})

        kline_df = pd.DataFrame(kline_data)
        share_df = pd.DataFrame(share_data)
        preset = {"flow_lookback": 10, "mom_lookback": 20}

        result = compute_factors_for_date(kline_df, share_df, dates[-1], preset)
        assert isinstance(result, pd.DataFrame)
        assert "etf_code" in result.columns
        assert "flow" in result.columns
        assert "mom" in result.columns
        assert "z_flow" in result.columns
        assert "z_mom" in result.columns
        assert "factor" in result.columns
        assert "quadrant" in result.columns
        assert len(result) == 3
