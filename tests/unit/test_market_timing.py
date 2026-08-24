"""大盘择时模块单元测试（份额流 T+1 修复）"""
import pytest
from src.analysis.market_timing import _compute_share_flow_pct

# dates 共21个观测(值100..120)：latest=120, 10步前=110 → (120/110-1)*100 ≈ 9.0909%
EXPECT = pytest.approx((120 / 110 - 1) * 100)


def _mk_share_map(dates, base=100.0, step=1.0):
    """构造 fd_share 递增的 share_map（万份）。"""
    return {d: base + i * step for i, d in enumerate(dates)}


class TestComputeShareFlowPct:
    def test_t_plus_1_lag_anchors_on_previous_day(self):
        """价格日期为今天、份额只到昨天（T+1常态）→ 应锚定昨天并返回非零流。"""
        dates = [f"2026-08-{d:02d}" for d in range(1, 22)]  # 21个观测日
        share_map = _mk_share_map(dates, base=100.0, step=1.0)  # 每+1份
        as_of = "2026-08-22"  # 价格最新日，份额表里没有
        flow, anchor = _compute_share_flow_pct(share_map, as_of, period=10)
        assert anchor == "2026-08-21"
        assert flow == EXPECT

    def test_exact_date_match_still_works(self):
        """价格日期恰好在份额表里（盘中/停更日）→ 行为不变。"""
        dates = [f"2026-08-{d:02d}" for d in range(1, 22)]
        share_map = _mk_share_map(dates)
        flow, anchor = _compute_share_flow_pct(share_map, "2026-08-21", period=10)
        assert anchor == "2026-08-21"
        assert flow == EXPECT

    def test_flow_can_be_negative(self):
        """份额缩减 → 负流。"""
        dates = [f"2026-08-{d:02d}" for d in range(1, 22)]
        share_map = _mk_share_map(dates, base=200.0, step=-1.0)
        flow, _ = _compute_share_flow_pct(share_map, "2026-08-22", period=10)
        assert flow == pytest.approx((180 / 190 - 1) * 100)  # latest=180, 10步前=190

    def test_insufficient_data_returns_zero(self):
        """不足两个观测 → 0.0 且无锚点。"""
        share_map = {"2026-08-20": 100.0}
        flow, anchor = _compute_share_flow_pct(share_map, "2026-08-22", period=10)
        assert flow == 0.0
        assert anchor is None

    def test_all_share_dates_after_price_date_returns_zero(self):
        """份额数据整体晚于价格日（异常状态）→ 0.0。"""
        share_map = {"2026-09-01": 100.0, "2026-09-02": 101.0}
        flow, anchor = _compute_share_flow_pct(share_map, "2026-08-22", period=10)
        assert flow == 0.0
        assert anchor is None

    def test_period_clamped_at_start(self):
        """period 超过历史长度 → 用最早观测做基准。"""
        share_map = {"2026-08-01": 100.0, "2026-08-02": 110.0}
        flow, _ = _compute_share_flow_pct(share_map, "2026-08-02", period=10)
        assert flow == 10.0
