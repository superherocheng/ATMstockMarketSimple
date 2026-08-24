"""家族份额聚合单元测试"""
import pytest
from src.analysis.family import (
    aggregate_family_share,
    window_change,
    _last_value_on_or_before,
)


class TestAggregateFamilyShare:
    def test_rotation_between_members_cancels_out(self):
        """核心场景：资金在两只同指数ETF间搬家 → 家族总量不变。"""
        # 成员A每天-100，成员B每天+100（工具轮动）
        member_a = [(f"2026-08-{d:02d}", 10000 - 100 * i) for i, d in enumerate(range(1, 11), 1)]
        member_b = [(f"2026-08-{d:02d}", 5000 + 100 * i) for i, d in enumerate(range(1, 11), 1)]
        agg = dict(aggregate_family_share({"A": member_a, "B": member_b}))
        # 总量恒为 15000
        assert all(abs(v - 15000.0) < 1e-6 for v in agg.values())
        assert len(agg) == 10

    def test_genuine_inflow_shows_in_aggregate(self):
        """全体成员同步净申购 → 家族总量真实增长。"""
        member_a = [(f"2026-08-{d:02d}", 1000.0 * (1.01 ** i)) for i, d in enumerate(range(1, 6), 1)]
        agg = aggregate_family_share({"A": member_a})
        assert agg[-1][1] > agg[0][1]

    def test_member_reports_on_different_dates_ffill(self):
        """成员报告日不对齐 → 缺席日沿用最近值，不当作清零。"""
        # A 天天报，B 隔天报
        a = [(f"2026-08-{d:02d}", 100.0) for d in range(1, 6)]
        b = [("2026-08-01", 50.0), ("2026-08-03", 60.0), ("2026-08-05", 70.0)]
        agg = dict(aggregate_family_share({"A": a, "B": b}))
        assert agg["2026-08-02"] == 150.0  # B 缺席 → 沿用50
        assert agg["2026-08-03"] == 160.0
        assert agg["2026-08-05"] == 170.0

    def test_new_member_starts_contributing_at_inception(self):
        """新发基金首报前贡献0，首报后计入家族总量。"""
        a = [(f"2026-08-{d:02d}", 100.0) for d in range(1, 6)]
        b = [("2026-08-04", 30.0), ("2026-08-05", 40.0)]
        agg = dict(aggregate_family_share({"A": a, "B": b}))
        assert agg["2026-08-03"] == 100.0
        assert agg["2026-08-04"] == 130.0

    def test_descending_input_order_is_sorted(self):
        """调用方给降序序列（如 overview 的 rn<=11 查询）→ 内部先排序，结果不变。"""
        # 显式构造降序（日期从新到旧）
        member_a = [("2026-08-05", 104.0), ("2026-08-04", 103.0), ("2026-08-03", 102.0),
                    ("2026-08-02", 101.0), ("2026-08-01", 100.0)]
        member_b = [("2026-08-05", 54.0), ("2026-08-04", 53.0), ("2026-08-03", 52.0),
                    ("2026-08-02", 51.0), ("2026-08-01", 50.0)]
        agg = dict(aggregate_family_share({"A": member_a, "B": member_b}))
        assert agg["2026-08-05"] == 158.0
        assert agg["2026-08-01"] == 150.0
        assert len(agg) == 5

    def test_empty_input(self):
        assert aggregate_family_share({}) == []


class TestWindowChange:
    def test_pct_and_qty(self):
        series = [(f"d{i:02d}", 100.0 + i) for i in range(11)]
        pct, qty = window_change(series, 10)
        assert pct == pytest.approx(10.0)
        assert qty == 10.0

    def test_insufficient_window(self):
        series = [("d1", 100.0), ("d2", 101.0)]
        pct, qty = window_change(series, 10)
        assert pct is None and qty is None

    def test_zero_base_returns_none(self):
        series = [("d1", 0.0)] + [(f"d{i:02d}", float(i)) for i in range(2, 12)]
        pct, qty = window_change(series, 10)
        assert pct is None and qty is None


class TestLastValueOnOrBefore:
    def test_binary_search(self):
        series = [("a", 1.0), ("b", 2.0), ("d", 4.0)]
        assert _last_value_on_or_before(series, "a") == 1.0
        assert _last_value_on_or_before(series, "c") == 2.0  # b <= c
        assert _last_value_on_or_before(series, "z") == 4.0
        assert _last_value_on_or_before(series, "0") is None
