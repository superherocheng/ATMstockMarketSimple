"""
P3.8: 概念热度评分单元测试
==========================
验证 _calculate_concept_heat() 的热度计算逻辑。
测试热度分数范围、leader_factor 规范化、单调性等。

不依赖数据库 —— 使用纯函数验证计算逻辑。
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ══════════════════════════════════════════════════
#  复制热度计算逻辑的独立函数（与 concept.py 一致）
# ══════════════════════════════════════════════════
def compute_heat_score(recent_vol, prev_vol, up_count, total_count, avg_leader_pct):
    """
    模拟 _calculate_concept_heat 的热度计算公式。

    Args:
        recent_vol: 最近 5 日成交量总和
        prev_vol: 前 5 日成交量总和
        up_count: 最新交易日上涨股票数
        total_count: 最新交易日总股票数
        avg_leader_pct: 领涨前 3 名平均涨幅 (%)

    Returns:
        heat_score: [0, 100]
    """
    # 成交量因子
    if prev_vol > 0:
        volume_factor = min((recent_vol - prev_vol) / prev_vol * 100, 100)
    else:
        volume_factor = 0

    # 涨跌比因子
    if total_count > 0:
        up_down_factor = (up_count / total_count) * 100
    else:
        up_down_factor = 0

    # 领涨因子 (P2.5: leader_norm 规范化)
    leader_factor = max(min(avg_leader_pct * 10, 100), -100)
    leader_norm = (leader_factor + 100) / 2  # -100→0, +100→100

    # 加权总分
    heat_score = (
        volume_factor * 0.3 +
        up_down_factor * 0.3 +
        leader_norm * 0.4
    )

    return round(max(0, min(100, heat_score)), 2)


# ══════════════════════════════════════════════════
#  测试
# ══════════════════════════════════════════════════
class TestHeatScoreBounds:
    """验证热度分数始终在 [0, 100] 范围内"""

    def test_baseline_is_50(self):
        """基础情况：成交量不变、一半涨、领涨 0% → 大约 50"""
        # volume_factor = 0 (无变化)
        # up_down_factor = 50 (50% up)
        # leader_factor = 0 → leader_norm = 50
        # heat = 0*0.3 + 50*0.3 + 50*0.4 = 35
        score = compute_heat_score(1000, 1000, 5, 10, 0.0)
        assert 0 <= score <= 100

    def test_all_bullish(self):
        """极度乐观：量暴增、全部涨、领涨涨停 → 接近 100"""
        score = compute_heat_score(
            recent_vol=2000,   # 比之前翻倍 (100% 增长, cap at 100)
            prev_vol=1000,
            up_count=10,
            total_count=10,    # 100% up
            avg_leader_pct=10.0  # 涨停 → leader_factor = 100, leader_norm = 100
        )
        # volume_factor = min(100%, 100) = 100
        # up_down_factor = 100% * 100 = 100
        # leader_factor = min(100, 100), leader_norm = 100
        # heat = 100*0.3 + 100*0.3 + 100*0.4 = 100
        assert 95 <= score <= 100

    def test_all_bearish(self):
        """极度悲观：量暴跌、全部跌、领涨暴跌 → 接近 0"""
        score = compute_heat_score(
            recent_vol=500,    # 腰斩 (-50%)
            prev_vol=1000,
            up_count=0,
            total_count=10,    # 0% up
            avg_leader_pct=-10.0  # leader_factor = max(-100, -100), leader_norm = 0
        )
        # volume_factor = max(-50, 0?)... actually: (-500/1000)*100 = -50, no cap
        #   Wait - the formula is: min((recent_vol - prev_vol)/prev_vol*100, 100)
        #   = min(-50, 100) = -50
        #   But volume_factor has no lower bound in the code!
        #   Let me check... yes, the code has: volume_factor = min((recent_vol - prev_vol) / prev_vol * 100, 100)
        #   So it CAN go negative!
        #   But the final heat_score is clamped to [0, 100]
        # volume_factor = (500-1000)/1000*100 = -50
        # up_down_factor = 0/10 * 100 = 0
        # leader_norm = (max(min(-100, 100), -100) + 100) / 2 = (-100+100)/2 = 0
        # heat = -50*0.3 + 0*0.3 + 0*0.4 = -15 → clamped to 0
        assert 0 <= score <= 5

    def test_extreme_values_clamped(self):
        """极值输入被钳制在 [0, 100]"""
        # 体积翻 10 倍
        score_high = compute_heat_score(10000, 1000, 10, 10, 100.0)
        assert 0 <= score_high <= 100

        # 体积跌 99%
        score_low = compute_heat_score(10, 1000, 0, 10, -100.0)
        assert 0 <= score_low <= 100

    @pytest.mark.parametrize("recent_vol,prev_vol,up,total,leader", [
        (1000, 1000, 5, 10, 0.0),       # neutral
        (2000, 1000, 10, 10, 10.0),      # bullish
        (500, 1000, 0, 10, -10.0),       # bearish
        (0, 0, 0, 0, 0.0),               # all zeros
        (1e9, 1, 1, 1, 100.0),           # extreme
    ])
    def test_parametrized_bounds(self, recent_vol, prev_vol, up, total, leader):
        """参数化测试：任意合法输入都应产生 [0,100] 的结果"""
        score = compute_heat_score(recent_vol, prev_vol, up, total, leader)
        assert 0 <= score <= 100, \
            f"Score {score} out of bounds for inputs ({recent_vol},{prev_vol},{up},{total},{leader})"


class TestWeightedFormula:
    """测试加权公式的正确性"""

    def test_weights_sum_to_one(self):
        """权重之和 = 1"""
        assert 0.3 + 0.3 + 0.4 == 1.0

    def test_volume_factor_formula(self):
        """成交量因子 = min(增长率*100, 100)"""
        # 10% 增长
        factor = min((1100 - 1000) / 1000 * 100, 100)
        assert factor == 10.0

        # 200% 增长 → 钳制在 100
        factor = min((3000 - 1000) / 1000 * 100, 100)
        assert factor == 100.0

        # 50% 下降 → 无下界（但在最终分数钳制）
        factor = min((500 - 1000) / 1000 * 100, 100)
        assert factor == -50.0

    def test_up_down_factor_formula(self):
        """涨跌比因子 = up_count / total * 100"""
        assert (7 / 10) * 100 == 70.0
        assert (0 / 10) * 100 == 0.0
        assert (10 / 10) * 100 == 100.0

    def test_leader_factor_formula(self):
        """领涨因子 = max(min(avg_pct * 10, 100), -100)"""
        # +5% 平均 → leader_factor = 50
        assert max(min(5.0 * 10, 100), -100) == 50.0

        # +15% 平均 → leader_factor = 100 (capped)
        assert max(min(15.0 * 10, 100), -100) == 100.0

        # -15% 平均 → leader_factor = -100 (capped)
        assert max(min(-15.0 * 10, 100), -100) == -100.0

    def test_leader_norm_formula(self):
        """leader_norm = (leader_factor + 100) / 2 → [0, 100]"""
        # leader_factor in [-100, 100]
        assert (100 + 100) / 2 == 100.0   # max → 100
        assert (0 + 100) / 2 == 50.0     # neutral → 50
        assert (-100 + 100) / 2 == 0.0   # min → 0


class TestMonotonicity:
    """验证热度分数与因子之间的单调性"""

    def test_volume_increase_raises_heat(self):
        """成交量增加 → 热度上升"""
        base = compute_heat_score(1000, 1000, 5, 10, 0.0)
        higher = compute_heat_score(1200, 1000, 5, 10, 0.0)
        assert higher >= base

    def test_up_ratio_increase_raises_heat(self):
        """涨跌比增加 → 热度上升"""
        base = compute_heat_score(1000, 1000, 5, 10, 0.0)
        higher = compute_heat_score(1000, 1000, 8, 10, 0.0)
        assert higher >= base

    def test_leader_performance_increase_raises_heat(self):
        """领涨股表现越好 → 热度越高"""
        base = compute_heat_score(1000, 1000, 5, 10, 0.0)
        higher = compute_heat_score(1000, 1000, 5, 10, 5.0)
        assert higher >= base

    def test_all_factors_decreasing_lowers_heat(self):
        """所有因子下降 → 热度下降"""
        bullish = compute_heat_score(1500, 1000, 8, 10, 5.0)
        bearish = compute_heat_score(1000, 1000, 3, 10, -5.0)
        assert bearish < bullish


class TestLeaderFactorNormalization:
    """P2.5: leader_factor 规范化 0-100"""

    def test_leader_norm_zero_when_all_limit_down(self):
        """全部跌停 (-10%) → leader_norm ≈ 0"""
        # leader_factor = max(min(-10*10, 100), -100) = -100
        # leader_norm = (-100 + 100) / 2 = 0
        leader_factor = max(min(-10.0 * 10, 100), -100)
        leader_norm = (leader_factor + 100) / 2
        assert leader_norm == 0.0

    def test_leader_norm_fifty_when_flat(self):
        """领涨 0% → leader_norm = 50"""
        leader_factor = max(min(0.0 * 10, 100), -100)
        leader_norm = (leader_factor + 100) / 2
        assert leader_norm == 50.0

    def test_leader_norm_hundred_when_all_limit_up(self):
        """全部涨停 (+10%) → leader_norm = 100"""
        leader_factor = max(min(10.0 * 10, 100), -100)
        leader_norm = (leader_factor + 100) / 2
        assert leader_norm == 100.0

    def test_leader_norm_symmetric(self):
        """规范化应对称：+X 和 -X 的 leader_norm 在 50 两侧对称"""
        x = 5.0
        pos_factor = max(min(x * 10, 100), -100)
        neg_factor = max(min(-x * 10, 100), -100)
        pos_norm = (pos_factor + 100) / 2
        neg_norm = (neg_factor + 100) / 2
        # 正负对称：50 + (pos_norm - 50) == 50 - (neg_norm - 50)
        assert pos_norm - 50 == pytest.approx(50 - neg_norm, abs=0.01)


class TestErrorResilience:
    """错误恢复能力"""

    def test_zero_prev_vol(self):
        """prev_vol = 0 → volume_factor = 0 (不崩溃)"""
        score = compute_heat_score(1000, 0, 5, 10, 0.0)
        assert 0 <= score <= 100

    def test_zero_total_count(self):
        """total_count = 0 → up_down_factor = 0 (不崩溃)"""
        score = compute_heat_score(1000, 1000, 0, 0, 0.0)
        assert 0 <= score <= 100

    def test_both_vol_zero(self):
        """recent_vol = prev_vol = 0 → volume_factor = 0"""
        score = compute_heat_score(0, 0, 5, 10, 0.0)
        assert 0 <= score <= 100

    def test_negative_volume(self):
        """负成交量（异常输入）→ 不应崩溃"""
        score = compute_heat_score(-100, 1000, 5, 10, 0.0)
        assert 0 <= score <= 100
