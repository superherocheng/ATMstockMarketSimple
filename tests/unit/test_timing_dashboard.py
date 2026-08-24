"""大盘温度计纯函数单元测试"""
import numpy as np
import pytest

from src.analysis.timing_dashboard import (
    panic_events,
    drawdown_series,
    locator_events,
    monthly_avg_returns,
    rolling_corr_regime,
    _percentile,
)


def _crash_series(n=300, crash_at=200, crash_pct=-0.08, seed=3):
    np.random.seed(seed)
    closes = 1 + np.cumsum(np.random.normal(0.0003, 0.012, n))
    closes[crash_at:crash_at + 6] = closes[crash_at - 1] * (1 + crash_pct) * np.ones(6) / 6 * 6
    closes[crash_at:crash_at + 6] = closes[crash_at - 1] * np.linspace(1, 1 + crash_pct, 6)
    amounts = np.random.uniform(1e6, 2e6, n)
    amounts[crash_at:crash_at + 8] = 5e6  # 放量
    return closes, amounts


class TestPanicEvents:
    def test_crash_with_volume_triggers_event(self):
        closes, amounts = _crash_series()
        events, stats, current = panic_events(closes, amounts)
        assert stats["n"] >= 1
        assert any(e["idx"] >= 200 for e in events)

    def test_forward_returns_rebound_positive_after_crash(self):
        closes, amounts = _crash_series()
        # 注入 V 型反弹
        closes[206:230] = np.linspace(closes[205], closes[205] * 1.10, 24)
        events, stats, _ = panic_events(closes, amounts)
        ev = [e for e in events if 195 <= e["idx"] <= 205]
        assert ev, "应有200附近的恐慌事件"
        assert ev[0]["fwd_10d"] > 0  # 反弹 → 前瞻为正

    def test_quiet_market_no_events(self):
        np.random.seed(1)
        n = 300
        closes = 1 + np.cumsum(np.random.normal(0.0004, 0.003, n))  # 低波动
        amounts = np.full(n, 1e6)
        events, stats, _ = panic_events(closes, amounts)
        assert stats["n"] == 0

    def test_insufficient_data(self):
        events, stats, current = panic_events(np.ones(30), np.ones(30))
        assert stats["n"] == 0
        assert current["triggered"] is False


class TestDrawdownAndLocator:
    def test_drawdown_at_new_high_is_zero(self):
        dd = drawdown_series(np.array([1.0, 2.0, 3.0]))
        assert dd[-1] == 0.0

    def test_drawdown_after_halving(self):
        dd = drawdown_series(np.array([2.0, 4.0, 2.0]))
        assert dd[-1] == -0.5

    def _mk_closes(self):
        # 注意：np.array([1.0]*50 + linspace + ...) 是元素相加不是拼接，必须 concatenate
        return np.concatenate([
            np.full(50, 1.0),
            np.linspace(1.0, 0.7, 50),
            np.full(50, 0.7),
        ])

    def test_locator_triggers_on_deep_drawdown_with_inflow(self):
        closes = self._mk_closes()
        dd = drawdown_series(closes)
        s20 = np.zeros(150); s20[80:] = 0.06  # 深跌途中份额流入
        events, active = locator_events(dd, s20)
        assert len(events) >= 1
        assert any(dd[i] <= -0.20 for i in events)

    def test_locator_no_trigger_without_inflow(self):
        closes = self._mk_closes()
        dd = drawdown_series(closes)
        s20 = np.zeros(150)  # 份额无流入
        events, active = locator_events(dd, s20)
        assert events == []


class TestMonthlyReturns:
    def test_two_months(self):
        dates = ["20240131", "20240229", "20240331"]
        closes = np.array([100.0, 110.0, 99.0])
        avg, n, detail = monthly_avg_returns(dates, closes)
        assert n == 2
        assert avg[0] is None  # 1月无样本
        assert avg[1] == 10.0  # 2月+10%
        assert avg[2] == -10.0  # 3月-10%

    def test_single_month_returns_empty(self):
        avg, n, _ = monthly_avg_returns(["20240131"], [100.0])
        assert n == 0
        assert all(v is None for v in avg)


class TestRollingCorrRegime:
    def test_dip_buying_detected(self):
        np.random.seed(2)
        n = 200
        rets = np.random.normal(0, 0.02, n)
        share = -rets + np.random.normal(0, 0.002, n)  # 跌日申购 → 强负相关
        corr, series, label = rolling_corr_regime(share, rets, 60)
        assert corr < -0.5
        assert label == "dip_buying"

    def test_chasing_detected(self):
        np.random.seed(2)
        rets = np.random.normal(0, 0.02, n := 200)
        share = rets + np.random.normal(0, 0.002, n)
        corr, _, label = rolling_corr_regime(share, rets, 60)
        assert corr > 0.5
        assert label == "chasing"

    def test_short_series_unknown(self):
        corr, series, label = rolling_corr_regime(np.ones(10), np.ones(10), 60)
        assert label == "unknown"


class TestPercentile:
    def test_mid(self):
        assert _percentile([1, 2, 3, 4, 5], 3) == 40.0

    def test_extremes(self):
        assert _percentile([1, 2, 3], 0) == 0.0
        assert _percentile([1, 2, 3], 9) == 100.0

    def test_empty_history(self):
        assert _percentile([], 3) == 50.0
