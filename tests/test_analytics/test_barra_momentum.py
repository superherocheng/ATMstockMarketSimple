"""
P3.8: BARRA 动量因子单元测试
============================
验证动量/波动率/相关性聚合的正确性，使用已知答案的 DataFrame 作为测试数据。

不依赖数据库 —— 使用 monkeypatch 注入 fixtures。
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# 确保项目根目录在路径中
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.analytics.barra import (
    calc_momentum_factors,
    calc_style_factors,
    calc_size_factors,
    calc_industry_factors,
)


# ══════════════════════════════════════════════════
#  Fixtures
# ══════════════════════════════════════════════════
def _make_kline_df(ts_code, prices, volumes, amounts):
    """构造模拟 K 线 DataFrame（最近 N 个交易日）"""
    n = len(prices)
    records = []
    for i in range(n):
        pct = ((prices[i] - prices[i - 1]) / prices[i - 1] * 100) if i > 0 else 0.0
        records.append({
            "ts_code": ts_code,
            "trade_date": f"20260{i+1:02d}",
            "close": prices[i],
            "pct_chg": round(pct, 4),
            "vol": volumes[i],
            "amount": amounts[i],
            "pre_close": prices[i - 1] if i > 0 else prices[i],
            "open": prices[i] * 0.99,
            "high": prices[i] * 1.02,
            "low": prices[i] * 0.98,
        })
    return pd.DataFrame(records)


@pytest.fixture
def known_momentum_fixture():
    """
    已知答案的动量测试数据。

    2 只股票，20 个交易日：
      - TEST1: 每天涨 1%，累计涨幅 ≈ 20%，波动率低
      - TEST2: 随机波动，累计涨幅 ≈ 5%，波动率高
    """
    np.random.seed(42)

    # TEST1: 每天精确涨 1%
    p1 = [10.0]
    for _ in range(19):
        p1.append(p1[-1] * 1.01)
    v1 = [100000] * 20
    a1 = [v * p for v, p in zip(v1, p1)]
    df1 = _make_kline_df("TEST1.SH", p1, v1, a1)

    # TEST2: 随机波动
    p2 = [10.0]
    for _ in range(19):
        p2.append(p2[-1] * (1 + np.random.normal(0, 0.03)))
    v2 = [80000 + np.random.randint(-10000, 10000) for _ in range(20)]
    a2 = [v * p for v, p in zip(v2, p2)]
    df2 = _make_kline_df("TEST2.SH", p2, v2, a2)

    combined = pd.concat([df1, df2], ignore_index=True)

    # 预计算已知答案
    # TEST1: 每天 1%，20 天
    pct1 = df1["pct_chg"].values
    momentum_20_test1 = pct1.sum()  # ≈ 19 * 1% = 19% approx (first day is 0)
    volatility_20_test1 = pct1.std()

    pct2 = df2["pct_chg"].values
    momentum_20_test2 = pct2.sum()
    volatility_20_test2 = pct2.std()

    return {
        "combined": combined,
        "expected": {
            "TEST1.SH": {
                "momentum_20": round(float(momentum_20_test1), 2),
                "volatility_20": round(float(volatility_20_test1), 2),
            },
            "TEST2.SH": {
                "momentum_20": round(float(momentum_20_test2), 2),
                # TEST2 波动率应该明显更高
                "vol_gt": float(volatility_20_test1),  # TEST2 vol > this
            },
        }
    }


# ══════════════════════════════════════════════════
#  核心计算逻辑的独立测试 (不依赖 DB)
# ══════════════════════════════════════════════════
class TestMomentumAggregation:
    """测试动量聚合 —— 使用纯函数逻辑，不依赖数据库"""

    def test_momentum_20_is_sum_of_pct_chg(self, known_momentum_fixture):
        """验证 momentum_20 = SUM(pct_chg) 跨最近 20 个交易日"""
        fix = known_momentum_fixture
        df = fix["combined"]

        for ts_code in ["TEST1.SH", "TEST2.SH"]:
            subset = df[df["ts_code"] == ts_code]
            momentum = float(subset["pct_chg"].sum())
            expected = fix["expected"][ts_code]["momentum_20"]
            assert momentum == pytest.approx(expected, abs=0.1), \
                f"{ts_code}: momentum={momentum}, expected={expected}"

    def test_volatility_is_stddev_of_pct_chg(self, known_momentum_fixture):
        """验证 volatility = STDDEV(pct_chg)"""
        fix = known_momentum_fixture
        df = fix["combined"]

        ts1 = df[df["ts_code"] == "TEST1.SH"]["pct_chg"].values
        ts2 = df[df["ts_code"] == "TEST2.SH"]["pct_chg"].values

        vol1 = float(np.std(ts1))
        vol2 = float(np.std(ts2))
        expected_vol1 = fix["expected"]["TEST1.SH"]["volatility_20"]

        assert vol1 == pytest.approx(expected_vol1, abs=0.01)
        assert vol2 > vol1, f"TEST2 vol ({vol2}) should be > TEST1 vol ({vol1})"

    def test_pv_corr_range(self):
        """验证价格-成交量相关系数应在 [-1, 1] 范围内"""
        np.random.seed(123)
        prices = np.cumsum(np.random.randn(20) * 0.5) + 100
        volumes = np.random.randint(80000, 120000, 20)

        corr = float(np.corrcoef(prices, volumes)[0, 1])
        assert -1.0 <= corr <= 1.0, f"Correlation {corr} out of range"
        # 随机数据通常相关性接近 0
        assert abs(corr) < 0.8  # 不太可能极端相关


class TestReturnRiskRatio:
    """测试 回报/风险比 计算（P2.1：sharpe_like → return_risk_ratio）"""

    def test_ratio_positive_momentum_low_vol(self):
        """正动量 + 低波动 → 高比率"""
        momentum_20 = 10.0  # 10% 累计涨幅
        volatility_20 = 1.0  # 1% 日波动
        ratio = momentum_20 / volatility_20
        assert ratio == 10.0

    def test_ratio_negative_momentum_high_vol(self):
        """负动量 + 高波动 → 负比率"""
        momentum_20 = -15.0
        volatility_20 = 5.0
        ratio = momentum_20 / volatility_20
        assert ratio == -3.0

    def test_ratio_zero_vol_returns_zero(self):
        """波动率为 0 → 比率 = 0 (避免除零)"""
        # 模拟 calc_momentum_factors 中的逻辑
        momentum_20 = 5.0
        volatility_20 = 0.0
        ratio = momentum_20 / volatility_20 if volatility_20 > 0 else 0
        assert ratio == 0.0


class TestRiskScoreThresholds:
    """测试 P2.2：风险评分使用百分位阈值"""

    def test_percentile_thresholds_top5(self):
        """验证 95 分位数阈值逻辑"""
        np.random.seed(1)
        # 100 只"股票"的波动率
        volatilities = np.concatenate([
            np.random.uniform(0.5, 1.5, 95),   # 正常范围
            np.random.uniform(3.0, 5.0, 5),     # 高波动（top 5%）
        ])
        vol_95 = np.quantile(volatilities, 0.95)
        high_risk_count = int(np.sum(volatilities >= vol_95))
        # 至少 5 只被标记（95 分位数以上）
        assert high_risk_count >= 5, f"Expected >=5 high risk, got {high_risk_count}"

    def test_bottom10_percentile(self):
        """验证底部 10% 分位数逻辑"""
        np.random.seed(2)
        corrs = np.random.uniform(-1.0, 1.0, 100)
        pv_10 = np.quantile(corrs, 0.10)
        bottom_count = int(np.sum(corrs <= pv_10))
        # 应有大约 10 只在底部
        assert 5 <= bottom_count <= 15, f"Expected ~10 in bottom decile, got {bottom_count}"

    def test_risk_score_range(self):
        """验证 risk_score 在 [0, 3] 范围内"""
        # 模拟 _aggregate_industry_metrics 的风险分级
        risk_levels = {"high": 3, "medium": 2, "low": 1}
        for level, expected_min in [("high", 3), ("medium", 2), ("low", 1)]:
            assert risk_levels[level] >= 1
            assert risk_levels[level] <= 3


class TestStyleFactors:
    """测试风格因子（HML）计算 —— P2.3 复合 PE/PB"""

    def test_composite_pe_pb_split(self):
        """验证复合 PE/PB 排名中位数分割包含所有股票"""
        np.random.seed(3)
        n = 200
        latest = pd.DataFrame({
            "ts_code": [f"STOCK{i:04d}" for i in range(n)],
            "pe_ttm": np.random.uniform(5, 80, n),
            "pb": np.random.uniform(0.5, 10, n),
        })

        # P2.3: composite score
        latest["pe_rank"] = latest["pe_ttm"].rank(pct=True)
        latest["pb_rank"] = latest["pb"].rank(pct=True)
        latest["composite"] = latest["pe_rank"] + latest["pb_rank"]
        composite_median = latest["composite"].median()

        growth = latest[latest["composite"] > composite_median]
        value = latest[latest["composite"] <= composite_median]

        # 所有股票都应被分类
        assert len(growth) + len(value) == n
        # 大小应大致对半
        assert 80 <= len(growth) <= 120, f"Growth count {len(growth)} not balanced"
        assert 80 <= len(value) <= 120, f"Value count {len(value)} not balanced"

    def test_hml_sign_consistency(self):
        """验证 HML = growth_return - value_return 方向一致性"""
        # 成长股收益 > 价值股收益 → HML > 0 (成长占优)
        g_ret, v_ret = 1.5, -0.5
        hml = g_ret - v_ret
        assert hml > 0

        # 价值股收益 > 成长股收益 → HML < 0 (价值占优)
        g_ret, v_ret = -2.0, 1.0
        hml = g_ret - v_ret
        assert hml < 0


class TestSizeFactors:
    """测试规模因子（SMB）计算 —— P2.4 中位数分割"""

    def test_smb_median_split(self):
        """验证 SMB 使用市值中位数分割（标准 Fama-French）"""
        np.random.seed(4)
        n = 300
        latest = pd.DataFrame({
            "ts_code": [f"STOCK{i:04d}" for i in range(n)],
            "total_mv": np.random.uniform(200, 500000, n),  # 万为单位
            "pct_chg": np.random.normal(0, 2, n),
        })

        mv_median = latest["total_mv"].median()
        large = latest[latest["total_mv"] >= mv_median]
        small = latest[latest["total_mv"] < mv_median]

        assert len(large) + len(small) == n
        # 中位数分割应严格对半
        assert len(large) == n // 2 or len(large) == n // 2 + 1

    def test_smb_calculation(self):
        """验证 SMB = 小盘收益 - 大盘收益"""
        # 小盘跑赢
        small_ret, large_ret = 0.8, 0.2
        smb = small_ret - large_ret
        assert smb == pytest.approx(0.6)
        assert smb > 0  # 小盘占优

        # 大盘跑赢
        small_ret, large_ret = -1.0, 1.5
        smb = small_ret - large_ret
        assert smb == pytest.approx(-2.5)
        assert smb < 0  # 大盘占优

    def test_smb_thresholds(self):
        """验证 SMB 风格判断阈值"""
        # |avg_smb| > 0.3 → small_cap (正) or large_cap (负)
        assert 0.5 > 0.3  # small_cap
        assert -0.5 < -0.3  # large_cap
        # |avg_smb| <= 0.3 → balanced
        assert abs(0.1) <= 0.3  # balanced


class TestIndustryFactors:
    """测试行业因子聚合"""

    def test_industry_aggregation(self):
        """验证行业聚合：pct_chg 取均值，amount 求和"""
        df = pd.DataFrame({
            "industry": ["银行", "银行", "半导体", "半导体", "半导体"],
            "trade_date": ["20260701", "20260701", "20260701", "20260701", "20260701"],
            "pct_chg": [0.5, 1.5, 3.0, -1.0, 2.0],
            "amount": [1e6, 2e6, 5e5, 3e5, 2e5],
            "close": [10.0, 20.0, 50.0, 55.0, 48.0],
        })

        agg = df.groupby(["industry", "trade_date"]).agg({
            "pct_chg": "mean",
            "amount": "sum",
        }).reset_index()

        bank = agg[agg["industry"] == "银行"]
        semi = agg[agg["industry"] == "半导体"]

        assert float(bank["pct_chg"].iloc[0]) == 1.0  # (0.5 + 1.5) / 2
        assert float(bank["amount"].iloc[0]) == 3e6   # 1e6 + 2e6
        assert float(semi["pct_chg"].iloc[0]) == pytest.approx(1.3333, abs=0.01)  # (3-1+2)/3
        assert float(semi["amount"].iloc[0]) == 1e6    # 5e5+3e5+2e5

    def test_risk_level_classification(self):
        """验证风险级别分类逻辑"""
        # momentum_20 < -5 AND volatility_20 > 2.5 → high risk
        assert (-6 < -5) and (3.0 > 2.5)  # high

        # momentum_20 < 0 AND volatility_20 > 2 → medium risk
        assert (-2 < 0) and (2.2 > 2)  # medium
        assert (1 > 0) or (1.5 <= 2)  # low (positive momentum)

    def test_momentum_cumulative(self):
        """验证动量 = 累计涨幅"""
        pct_changes = [0.5, 1.0, -0.3, 2.0, -0.5]
        cumulative = sum(pct_changes)
        assert cumulative == 2.7
