"""因子引擎单元测试 — 适配 vectorized series API"""
import numpy as np
import pandas as pd
import pytest


class TestComputeFlowSeries:
    """测试 Flow (份额趋势) 系列计算"""

    def test_rising_shares_positive_flow(self):
        """持续增长的份额 → 正 Flow"""
        from src.analysis.factor_engine import _compute_flow_series

        shares = pd.Series([100, 102, 104, 106, 108, 110, 112, 114, 116, 118],
                           name="fd_share")
        result = _compute_flow_series(shares, lookback=5)
        # Last entry should be positive
        assert result[-1] > 0

    def test_declining_shares_negative_flow(self):
        """持续减少的份额 → 负 Flow"""
        from src.analysis.factor_engine import _compute_flow_series

        shares = pd.Series([120, 118, 116, 114, 112, 110, 108, 106, 104, 102],
                           name="fd_share")
        result = _compute_flow_series(shares, lookback=5)
        assert result[-1] < 0

    def test_insufficient_data_returns_nan(self):
        """数据不足 → NaN"""
        from src.analysis.factor_engine import _compute_flow_series

        shares = pd.Series([100, 102], name="fd_share")
        result = _compute_flow_series(shares, lookback=10)
        # all NaN since n < lookback + 1
        assert np.all(np.isnan(result))


class TestComputeMomSeries:
    """测试 Momentum (价格动量) 系列计算"""

    def test_rising_price_positive_mom(self):
        """价格上涨 → 正动量"""
        from src.analysis.factor_engine import _compute_mom_series

        closes = pd.Series([10.0, 10.5, 11.0, 11.5, 12.0, 12.5, 13.0, 13.5, 14.0, 14.5,
                            15.0, 15.5, 16.0, 16.5, 17.0, 17.5, 18.0, 18.5, 19.0, 19.5,
                            20.0], name="close")
        result = _compute_mom_series(closes, lookback=10)
        assert result[-1] > 0

    def test_falling_price_negative_mom(self):
        """价格下跌 → 负动量"""
        from src.analysis.factor_engine import _compute_mom_series

        closes = pd.Series([20.0, 19.5, 19.0, 18.5, 18.0, 17.5, 17.0, 16.5, 16.0, 15.5,
                            15.0, 14.5, 14.0, 13.5, 13.0, 12.5, 12.0, 11.5, 11.0, 10.5,
                            10.0], name="close")
        result = _compute_mom_series(closes, lookback=10)
        assert result[-1] < 0

    def test_insufficient_data_returns_nan(self):
        """数据不足 → NaN"""
        from src.analysis.factor_engine import _compute_mom_series

        closes = pd.Series([10.0, 11.0], name="close")
        result = _compute_mom_series(closes, lookback=20)
        # all NaN since n < lookback + 1
        assert np.all(np.isnan(result))


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


class TestComputeRSRSSeries:
    """测试 RSRS 系列计算"""

    def test_rising_trend_positive_rsrs(self):
        """低点抬升 + 高点创新高 → 正 RSRS (支撑走强)"""
        from src.analysis.factor_engine import _compute_rsrs_series

        lows = pd.Series([10.0, 10.2, 10.5, 10.8, 11.0, 11.3, 11.6, 12.0,
                          12.2, 12.5, 12.8, 13.0, 13.3, 13.6, 14.0, 14.2,
                          14.5, 14.8, 15.0, 15.3], name="low")
        highs = pd.Series([11.0, 11.3, 11.6, 12.0, 12.2, 12.5, 12.8, 13.0,
                           13.3, 13.6, 14.0, 14.2, 14.5, 14.8, 15.0, 15.3,
                           15.6, 16.0, 16.2, 16.5], name="high")
        result = _compute_rsrs_series(highs, lows, lookback=20)
        assert not np.isnan(result[-1])
        assert result[-1] > 0  # 上升趋势中 β > 0, RSRS > 0

    def test_correlated_high_low_positive_rsrs(self):
        """高点与低点同步变动 → 正 RSRS (强支撑/阻力结构)"""
        from src.analysis.factor_engine import _compute_rsrs_series

        lows = pd.Series([15.0, 14.8, 14.5, 14.2, 14.0, 13.7, 13.4, 13.0,
                          12.7, 12.4, 12.0, 11.7, 11.4, 11.0, 10.7, 10.4,
                          10.0, 9.7, 9.4, 9.0], name="low")
        highs = pd.Series([16.0, 15.7, 15.4, 15.0, 14.7, 14.4, 14.0, 13.7,
                           13.4, 13.0, 12.7, 12.4, 12.0, 11.7, 11.4, 11.0,
                           10.7, 10.4, 10.0, 9.7], name="high")
        result = _compute_rsrs_series(highs, lows, lookback=20)
        assert not np.isnan(result[-1])
        assert result[-1] > 0

    def test_anti_correlated_high_low_negative_rsrs(self):
        """高点与低点反向变动 → 负 RSRS (支撑/阻力结构不稳定)"""
        from src.analysis.factor_engine import _compute_rsrs_series

        lows = pd.Series([9.0, 9.2, 9.5, 9.8, 10.0, 10.2, 10.5, 10.8,
                          11.0, 11.2, 11.5, 11.8, 12.0, 12.2, 12.5, 12.8,
                          13.0, 13.2, 13.5, 13.8], name="low")
        highs = pd.Series([16.0, 15.8, 15.5, 15.2, 15.0, 14.7, 14.4, 14.0,
                           13.7, 13.4, 13.0, 12.7, 12.4, 12.0, 11.7, 11.4,
                           11.0, 10.7, 10.4, 10.0], name="high")
        result = _compute_rsrs_series(highs, lows, lookback=20)
        assert not np.isnan(result[-1])
        assert result[-1] < 0  # 高低反向 → β < 0 → RSRS < 0

    def test_insufficient_data_returns_nan(self):
        """数据不足 → NaN"""
        from src.analysis.factor_engine import _compute_rsrs_series

        highs = pd.Series([10.0, 11.0], name="high")
        lows = pd.Series([9.0, 10.0], name="low")
        result = _compute_rsrs_series(highs, lows, lookback=20)
        assert np.all(np.isnan(result))


class TestComputePresetFactors:
    """测试预设因子批量计算"""

    def test_short_preset_runs(self):
        """短期预设可以运行（依赖 DB，需要 conftest 的连接）"""
        from src.analysis.factor_engine import _compute_preset_factors
        # This test requires DB — skip if no DB connection
        try:
            n = _compute_preset_factors("optimized")
            assert n >= 0  # 0 if already computed, >0 if new
        except RuntimeError as e:
            if "not initialized" in str(e):
                pytest.skip("需要数据库连接")
            raise
