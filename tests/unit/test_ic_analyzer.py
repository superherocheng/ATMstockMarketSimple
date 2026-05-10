"""IC分析器单元测试"""
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock


class TestComputeICForDate:
    """测试单日IC计算"""

    def test_perfect_positive_correlation(self):
        """因子与收益完全正相关 → IC接近1"""
        from src.analysis.ic_analyzer import _compute_ic_for_date

        factors = pd.Series([0.1, 0.3, 0.5, 0.7, 0.9, 1.1, 1.3, 1.5])
        returns = pd.Series([0.01, 0.03, 0.05, 0.07, 0.09, 0.11, 0.13, 0.15])
        ic = _compute_ic_for_date(factors, returns)
        assert ic > 0.9

    def test_perfect_negative_correlation(self):
        """因子与收益完全负相关 → IC接近-1"""
        from src.analysis.ic_analyzer import _compute_ic_for_date

        factors = pd.Series([1.5, 1.3, 1.1, 0.9, 0.7, 0.5, 0.3, 0.1])
        returns = pd.Series([0.01, 0.03, 0.05, 0.07, 0.09, 0.11, 0.13, 0.15])
        ic = _compute_ic_for_date(factors, returns)
        assert ic < -0.9

    def test_insufficient_data_returns_nan(self):
        """数据不足 → NaN"""
        from src.analysis.ic_analyzer import _compute_ic_for_date

        factors = pd.Series([0.1, 0.2])
        returns = pd.Series([0.01, 0.02])
        ic = _compute_ic_for_date(factors, returns)
        assert pd.isna(ic)


class TestComputeICSummary:
    """测试IC汇总统计"""

    def test_basic_summary(self):
        """基本IC汇总"""
        from src.analysis.ic_analyzer import _compute_ic_summary

        ic_series = pd.Series([0.05, 0.03, -0.02, 0.04, 0.06, 0.01, -0.01, 0.07, 0.02, 0.03])
        summary = _compute_ic_summary(ic_series)
        assert "ic_mean" in summary
        assert "ic_std" in summary
        assert "icir" in summary
        assert "ic_win_rate" in summary
        assert summary["ic_win_rate"] == 0.8  # 8 out of 10 positive
        assert summary["sample_count"] == 10

    def test_all_positive_ic(self):
        """全部正IC → 胜率1.0"""
        from src.analysis.ic_analyzer import _compute_ic_summary

        ic_series = pd.Series([0.1, 0.2, 0.3, 0.4, 0.5])
        summary = _compute_ic_summary(ic_series)
        assert summary["ic_win_rate"] == 1.0
        assert summary["icir"] > 0
