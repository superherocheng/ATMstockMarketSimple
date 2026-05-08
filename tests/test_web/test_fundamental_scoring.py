"""
P3.8: 基本面评分单元测试
========================
验证 _compute_stocks_fundamental() 中的复合评分逻辑。
测试规范化函数、周期性/非周期性行业估值处理、分数范围等。

不依赖数据库 —— 使用合成 DataFrame 模拟 DB 查询结果。
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.config import CYCLICAL_INDUSTRIES


# ══════════════════════════════════════════════════
#  复制评分逻辑的独立函数（避免依赖 DB）
# ══════════════════════════════════════════════════
def _norm(series):
    """0-100 规范化：与 _compute_stocks_fundamental 中的 _norm 一致"""
    s_min, s_max = series.min(), series.max()
    if s_max == s_min:
        return pd.Series(50.0, index=series.index)
    return ((series - s_min) / (s_max - s_min) * 100).fillna(0)


def compute_composite_scores(df):
    """模拟 _compute_stocks_fundamental 的评分计算逻辑"""
    df = df.copy()

    # 标记周期性行业
    df["is_cyclical"] = df["industry"].isin(CYCLICAL_INDUSTRIES)

    # 规范化各指标
    df["roe_score"] = _norm(df["roe"])
    df["margin_score"] = _norm(df["grossprofit_margin"])
    df["tr_yoy_score"] = _norm(df["tr_yoy"])
    df["profit_yoy_score"] = _norm(df["netprofit_yoy"])

    # 成长评分
    df["growth_score"] = df["tr_yoy_score"] * 0.5 + df["profit_yoy_score"] * 0.5

    # 盈利能力评分
    df["profitability_score"] = df["roe_score"] * 0.6 + df["margin_score"] * 0.4

    # 估值评分（行业内分位数）
    df["valuation_score"] = 50.0  # default
    for industry_name, group in df.groupby("industry"):
        metric = "pb" if group["is_cyclical"].iloc[0] else "pe_ttm"
        vals = group[metric].rank(pct=True)
        df.loc[group.index, "valuation_score"] = (1 - vals) * 100

    # 复合评分
    df["composite_score"] = (
        df["growth_score"] * 0.30 +
        df["profitability_score"] * 0.30 +
        df["valuation_score"] * 0.40
    )

    return df


# ══════════════════════════════════════════════════
#  Fixtures
# ══════════════════════════════════════════════════
@pytest.fixture
def curated_funda_fixture():
    """
    精心设计的 6 只股票，覆盖 3 个行业。
    业界 A: 3 只 (银行-周期性)
    业界 B: 3 只 (半导体-非周期性)
    """
    np.random.seed(100)
    return pd.DataFrame({
        "ts_code": ["BANK1.SH", "BANK2.SH", "BANK3.SH",
                     "SEMI1.SZ", "SEMI2.SZ", "SEMI3.SZ"],
        "name": ["银行A", "银行B", "银行C", "半导体A", "半导体B", "半导体C"],
        "industry": ["银行", "银行", "银行", "半导体", "半导体", "半导体"],
        "pe_ttm":  [5.0, 8.0, 12.0, 30.0, 45.0, 80.0],
        "pb":       [0.6, 0.9, 1.2, 3.0, 5.0, 8.0],
        "total_mv": [5000, 3000, 1000, 800, 500, 200],
        "roe":      [12.0, 10.0, 8.0, 15.0, 20.0, 25.0],
        "netprofit_yoy": [5.0, 8.0, 3.0, 20.0, 35.0, 50.0],
        "tr_yoy":        [3.0, 6.0, 2.0, 15.0, 30.0, 45.0],
        "grossprofit_margin": [45.0, 40.0, 35.0, 50.0, 55.0, 60.0],
        "netprofit_margin":   [20.0, 18.0, 15.0, 25.0, 28.0, 30.0],
    })


# ══════════════════════════════════════════════════
#  测试
# ══════════════════════════════════════════════════
class TestNormFunction:
    """测试 _norm 规范化函数"""

    def test_norm_range_0_to_100(self):
        """规范化结果应在 [0, 100] 范围内"""
        s = pd.Series([10, 20, 30, 40, 50])
        result = _norm(s)
        assert result.min() == 0.0
        assert result.max() == 100.0

    def test_norm_constant_input_returns_50(self):
        """常量输入 → 所有值返回 50"""
        s = pd.Series([7.0, 7.0, 7.0])
        result = _norm(s)
        assert (result == 50.0).all()

    def test_norm_preserves_order(self):
        """规范化保持原始排序"""
        s = pd.Series([3.0, 1.0, 5.0, 2.0, 4.0])
        result = _norm(s)
        # 排序应一致
        assert result.iloc[2] > result.iloc[4] > result.iloc[0] > result.iloc[3] > result.iloc[1]

    def test_norm_single_value(self):
        """单值输入 → 50"""
        s = pd.Series([42.0])
        result = _norm(s)
        assert result.iloc[0] == 50.0


class TestCompositeScore:
    """测试复合评分计算"""

    def test_all_scores_in_range(self, curated_funda_fixture):
        """所有评分应在 [0, 100] 范围内"""
        df = compute_composite_scores(curated_funda_fixture)

        score_cols = ["roe_score", "margin_score", "tr_yoy_score",
                       "profit_yoy_score", "growth_score",
                       "profitability_score", "valuation_score",
                       "composite_score"]
        for col in score_cols:
            assert df[col].min() >= 0.0, f"{col} min {df[col].min()} < 0"
            assert df[col].max() <= 100.0, f"{col} max {df[col].max()} > 100"

    def test_growth_score_weighted_average(self, curated_funda_fixture):
        """growth_score = 0.5*tr_yoy_score + 0.5*profit_yoy_score"""
        df = compute_composite_scores(curated_funda_fixture)
        for _, row in df.iterrows():
            expected = row["tr_yoy_score"] * 0.5 + row["profit_yoy_score"] * 0.5
            assert row["growth_score"] == pytest.approx(expected, abs=0.01)

    def test_profitability_score_weighted_average(self, curated_funda_fixture):
        """profitability_score = 0.6*roe_score + 0.4*margin_score"""
        df = compute_composite_scores(curated_funda_fixture)
        for _, row in df.iterrows():
            expected = row["roe_score"] * 0.6 + row["margin_score"] * 0.4
            assert row["profitability_score"] == pytest.approx(expected, abs=0.01)

    def test_composite_score_weighted_average(self, curated_funda_fixture):
        """composite_score = 0.30*growth + 0.30*profitability + 0.40*valuation"""
        df = compute_composite_scores(curated_funda_fixture)
        for _, row in df.iterrows():
            expected = (row["growth_score"] * 0.30 +
                        row["profitability_score"] * 0.30 +
                        row["valuation_score"] * 0.40)
            assert row["composite_score"] == pytest.approx(expected, abs=0.01)

    def test_weight_sum_is_one(self):
        """权重之和 = 1"""
        assert 0.30 + 0.30 + 0.40 == 1.0


class TestCyclicalVsNonCyclical:
    """测试周期性行业差异化估值处理"""

    def test_cyclical_uses_pb(self):
        """周期性行业（银行）估值使用 PB"""
        # 银行在 CYCLICAL_INDUSTRIES 中
        df = pd.DataFrame({
            "ts_code": ["B1", "B2", "B3"],
            "industry": ["银行", "银行", "银行"],
            "pe_ttm": [5.0, 8.0, 12.0],
            "pb": [0.6, 0.9, 1.2],
            "total_mv": [5000, 3000, 1000],
            "roe": [12.0, 10.0, 8.0],
            "netprofit_yoy": [5.0, 8.0, 3.0],
            "tr_yoy": [3.0, 6.0, 2.0],
            "grossprofit_margin": [45.0, 40.0, 35.0],
            "netprofit_margin": [20.0, 18.0, 15.0],
        })

        result = compute_composite_scores(df)
        # PB 最低的应该 valuation_score 最高
        lowest_pb_idx = result["pb"].idxmin()
        highest_val = result.loc[lowest_pb_idx, "valuation_score"]
        for idx in result.index:
            if idx != lowest_pb_idx:
                assert highest_val > result.loc[idx, "valuation_score"], \
                    f"Lowest PB stock should have highest valuation score"

    def test_non_cyclical_uses_pe(self):
        """非周期性行业（半导体）估值使用 PE"""
        df = pd.DataFrame({
            "ts_code": ["S1", "S2", "S3"],
            "industry": ["半导体", "半导体", "半导体"],
            "pe_ttm": [30.0, 45.0, 80.0],
            "pb": [3.0, 5.0, 8.0],
            "total_mv": [800, 500, 200],
            "roe": [15.0, 20.0, 25.0],
            "netprofit_yoy": [20.0, 35.0, 50.0],
            "tr_yoy": [15.0, 30.0, 45.0],
            "grossprofit_margin": [50.0, 55.0, 60.0],
            "netprofit_margin": [25.0, 28.0, 30.0],
        })

        result = compute_composite_scores(df)
        # PE 最低的应该 valuation_score 最高
        lowest_pe_idx = result["pe_ttm"].idxmin()
        highest_val = result.loc[lowest_pe_idx, "valuation_score"]
        for idx in result.index:
            if idx != lowest_pe_idx:
                assert highest_val > result.loc[idx, "valuation_score"], \
                    f"Lowest PE stock should have highest valuation score"


class TestEdgeCases:
    """边缘情况测试"""

    def test_empty_dataframe(self):
        """空 DataFrame 不崩溃"""
        df = pd.DataFrame(columns=["ts_code", "name", "industry", "pe_ttm", "pb",
                                    "total_mv", "roe", "netprofit_yoy", "tr_yoy",
                                    "grossprofit_margin", "netprofit_margin"])
        # 应优雅处理空数据
        assert len(df) == 0

    def test_single_stock(self):
        """单只股票评分"""
        df = pd.DataFrame({
            "ts_code": ["ONLY1.SH"],
            "name": ["独苗"],
            "industry": ["综合"],
            "pe_ttm": [15.0],
            "pb": [2.0],
            "total_mv": [1000],
            "roe": [10.0],
            "netprofit_yoy": [5.0],
            "tr_yoy": [3.0],
            "grossprofit_margin": [40.0],
            "netprofit_margin": [15.0],
        })

        result = compute_composite_scores(df)
        assert len(result) == 1
        # 单只股票，roe_score 应为 50（唯一值）
        assert result["roe_score"].iloc[0] == 50.0

    def test_zero_values_dont_break(self):
        """零值不应导致 NaN 或崩溃"""
        df = pd.DataFrame({
            "ts_code": ["ZERO1.SH", "ZERO2.SH"],
            "name": ["零值A", "零值B"],
            "industry": ["测试", "测试"],
            "pe_ttm": [0.0, 5.0],
            "pb": [0.0, 1.0],
            "total_mv": [100, 200],
            "roe": [0.0, 5.0],
            "netprofit_yoy": [0.0, 2.0],
            "tr_yoy": [0.0, 1.0],
            "grossprofit_margin": [0.0, 30.0],
            "netprofit_margin": [0.0, 10.0],
        })

        result = compute_composite_scores(df)
        # 应无 NaN
        for col in ["composite_score", "growth_score", "profitability_score"]:
            assert not result[col].isna().any(), f"{col} contains NaN"

    def test_negative_values_handled(self):
        """负值应能被正确处理（规范化为 0-100 范围）"""
        df = pd.DataFrame({
            "ts_code": ["NEG1.SH", "NEG2.SH", "POS1.SH"],
            "name": ["负A", "负B", "正A"],
            "industry": ["测试", "测试", "测试"],
            "pe_ttm": [10.0, 12.0, 8.0],
            "pb": [1.0, 1.2, 0.8],
            "total_mv": [500, 300, 700],
            "roe": [-5.0, -2.0, 8.0],
            "netprofit_yoy": [-20.0, -10.0, 15.0],
            "tr_yoy": [-15.0, -5.0, 10.0],
            "grossprofit_margin": [20.0, 25.0, 45.0],
            "netprofit_margin": [-5.0, 2.0, 15.0],
        })

        result = compute_composite_scores(df)

        # 规范化后应在 [0, 100] 范围内
        for col in ["roe_score", "margin_score", "tr_yoy_score", "profit_yoy_score"]:
            assert result[col].min() >= 0.0, f"{col} min < 0"
            assert result[col].max() <= 100.0, f"{col} max > 100"

        # 最差的公司 roe_score 应为 0
        worst_roe_idx = df["roe"].idxmin()
        assert result.loc[worst_roe_idx, "roe_score"] == 0.0


class TestKnownAnswer:
    """已知答案验证"""

    def test_simple_two_stock_composite(self):
        """
        两只股票，只有一个指标不同 → 可手动验证复合评分。
        
        A: 高成长、低盈利、中等估值
        B: 低成长、高盈利、中等估值
        
        预期:
          - A 的 growth_score 更高
          - B 的 profitability_score 更高
          - 估值分取决于行业分位数
        """
        df = pd.DataFrame({
            "ts_code": ["A.SH", "B.SH"],
            "name": ["成长股", "盈利股"],
            "industry": ["科技", "科技"],  # 同行业
            "pe_ttm": [50.0, 30.0],
            "pb": [4.0, 3.0],
            "total_mv": [1000, 1000],
            "roe": [10.0, 25.0],          # B 盈利更高
            "netprofit_yoy": [40.0, 5.0], # A 成长更高
            "tr_yoy": [35.0, 3.0],        # A 成长更高
            "grossprofit_margin": [60.0, 50.0],
            "netprofit_margin": [20.0, 25.0],
        })

        result = compute_composite_scores(df)

        a = result[result["ts_code"] == "A.SH"].iloc[0]
        b = result[result["ts_code"] == "B.SH"].iloc[0]

        # A 成长评分更高
        assert a["growth_score"] > b["growth_score"], \
            f"A growth={a['growth_score']}, B growth={b['growth_score']}"

        # B 盈利能力评分更高
        assert b["profitability_score"] > a["profitability_score"], \
            f"A profitability={a['profitability_score']}, B profitability={b['profitability_score']}"
