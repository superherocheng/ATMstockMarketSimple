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


class TestComputeRSRS:
    """测试 RSRS 计算"""

    def test_rising_trend_positive_rsrs(self):
        """低点抬升 + 高点创新高 → 正 RSRS (支撑走强)"""
        from src.analysis.factor_engine import _compute_rsrs

        # 有趋势: 低点(支持位)和 高点(阻力位)同步上升
        lows = pd.Series([10.0, 10.2, 10.5, 10.8, 11.0, 11.3, 11.6, 12.0,
                          12.2, 12.5, 12.8, 13.0, 13.3, 13.6, 14.0, 14.2,
                          14.5, 14.8, 15.0, 15.3], name="low")
        highs = pd.Series([11.0, 11.3, 11.6, 12.0, 12.2, 12.5, 12.8, 13.0,
                           13.3, 13.6, 14.0, 14.2, 14.5, 14.8, 15.0, 15.3,
                           15.6, 16.0, 16.2, 16.5], name="high")
        rsrs = _compute_rsrs(highs, lows, lookback=20)
        assert not pd.isna(rsrs)
        assert rsrs > 0  # 上升趋势中 β > 0, RSRS > 0

    def test_correlated_high_low_positive_rsrs(self):
        """高点与低点同步变动 → 正 RSRS (强支撑/阻力结构)"""
        from src.analysis.factor_engine import _compute_rsrs

        # 低点和高点同步下降: 协方差正, 趋势结构稳定
        lows = pd.Series([15.0, 14.8, 14.5, 14.2, 14.0, 13.7, 13.4, 13.0,
                          12.7, 12.4, 12.0, 11.7, 11.4, 11.0, 10.7, 10.4,
                          10.0, 9.7, 9.4, 9.0], name="low")
        highs = pd.Series([16.0, 15.7, 15.4, 15.0, 14.7, 14.4, 14.0, 13.7,
                           13.4, 13.0, 12.7, 12.4, 12.0, 11.7, 11.4, 11.0,
                           10.7, 10.4, 10.0, 9.7], name="high")
        rsrs = _compute_rsrs(highs, lows, lookback=20)
        assert not pd.isna(rsrs)
        # 高低同步, 正相关 → RSRS > 0
        assert rsrs > 0

    def test_anti_correlated_high_low_negative_rsrs(self):
        """高点与低点反向变动 → 负 RSRS (支撑/阻力结构不稳定)"""
        from src.analysis.factor_engine import _compute_rsrs

        # 低点抬升但高点下降: 协方差负 → 支撑阻力结构在收缩
        lows = pd.Series([9.0, 9.2, 9.5, 9.8, 10.0, 10.2, 10.5, 10.8,
                          11.0, 11.2, 11.5, 11.8, 12.0, 12.2, 12.5, 12.8,
                          13.0, 13.2, 13.5, 13.8], name="low")
        highs = pd.Series([16.0, 15.8, 15.5, 15.2, 15.0, 14.7, 14.4, 14.0,
                           13.7, 13.4, 13.0, 12.7, 12.4, 12.0, 11.7, 11.4,
                           11.0, 10.7, 10.4, 10.0], name="high")
        rsrs = _compute_rsrs(highs, lows, lookback=20)
        assert not pd.isna(rsrs)
        assert rsrs < 0  # 高低反向 → β < 0 → RSRS < 0

    def test_insufficient_data_returns_nan(self):
        """数据不足 → NaN"""
        from src.analysis.factor_engine import _compute_rsrs

        highs = pd.Series([10.0, 11.0], name="high")
        lows = pd.Series([9.0, 10.0], name="low")
        rsrs = _compute_rsrs(highs, lows, lookback=20)
        assert pd.isna(rsrs)


class TestComputeFactorsForDate:
    """测试单日因子计算集成（含 RSRS）"""

    def test_returns_dataframe_with_expected_columns(self):
        from src.analysis.factor_engine import compute_factors_for_date

        n = 30
        dates = pd.date_range("2025-01-01", periods=n, freq="D")
        kline_data = []
        share_data = []
        for code in ["A", "B", "C"]:
            for i, d in enumerate(dates):
                base = 10.0 + i * 0.1
                kline_data.append({
                    "ts_code": code, "trade_date": d,
                    "high": base + 0.5, "low": base - 0.5,
                    "close": base, "pct_chg": 0.5,
                })
                share_data.append({
                    "ts_code": code, "trade_date": d,
                    "fd_share": 1000 + i * 10,
                })

        kline_df = pd.DataFrame(kline_data)
        share_df = pd.DataFrame(share_data)
        preset = {
            "rsrs_lookback": 20,
            "flow_lookback": 10,
            "mom_lookback": 20,
            "factor_weights": {"rsrs": 0.4, "flow": 0.2, "mom": 0.4},
        }

        result = compute_factors_for_date(kline_df, share_df, dates[-1], preset)
        assert isinstance(result, pd.DataFrame)
        expected_cols = [
            "etf_code", "rsrs", "flow", "mom",
            "z_rsrs", "z_flow", "z_mom", "factor", "quadrant",
        ]
        for c in expected_cols:
            assert c in result.columns, f"Missing column: {c}"
        assert len(result) == 3
        # Factor should be a weighted combination of z_rsrs + z_flow + z_mom
        # In this uniform test data, all ETFs should have similar factors
        assert result["factor"].notna().all()
