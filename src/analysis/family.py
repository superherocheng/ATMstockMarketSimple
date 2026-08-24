"""同指数家族份额聚合（消除工具轮动假信号）。

单只 ETF 的份额 = 投资者流量 × 工具轮动。同指数家族（如 510300+510310+
159919+…）加总后，轮动搬家相互抵消，剩下的是真流量。纯函数、无IO，
供 divergence / overview / market_timing 共用。
"""
from __future__ import annotations


def aggregate_family_share(
    member_series: dict[str, list[tuple[str, float]]],
) -> list[tuple[str, float]]:
    """按日期加总家族成员份额，成员序列各自前向填充。

    - 成员报告日不完全对齐：某成员在某日缺失时沿用其最近一次值（缺席是
      报告空缺，不是份额清零）。
    - 成员首次报告前贡献 0（基金尚未成立，家族总量不含它，自然处理新发）。
    - 返回按日期升序的 [(date_str, total_share)]。

    已知局限：成员份额折算/合并（如 510500 2015-04 合并）会在加总序列中
    产生一次跳变，属于罕见事件，交给上游异常检测标记。
    """
    if not member_series:
        return []
    # 各成员序列按日期升序（对输入顺序鲁棒：调用方可能给降序）
    ordered = {
        code: sorted(series, key=lambda x: x[0])
        for code, series in member_series.items()
    }
    all_dates = sorted({d for series in ordered.values() for d, _ in series})
    totals = []
    current = {}
    for date in all_dates:
        for code, series in ordered.items():
            # 各成员序列升序，按日期值二分查找最后一次 <= date 的值（前向填充）
            val = _last_value_on_or_before(series, date)
            if val is not None:
                current[code] = val
        totals.append((date, sum(current.values())))
    return totals


def _last_value_on_or_before(series: list[tuple[str, float]], date: str):
    """升序序列中 <= date 的最后一个值（线性指针缓存由调用侧保证升序）。"""
    lo, hi, ans = 0, len(series) - 1, None
    while lo <= hi:
        mid = (lo + hi) // 2
        if series[mid][0] <= date:
            ans = series[mid][1]
            lo = mid + 1
        else:
            hi = mid - 1
    return ans


def window_change(
    series: list[tuple[str, float]], window: int
) -> tuple[float | None, float | None]:
    """序列在 window 个观测步上的变化：返回 (pct, qty)。

    不足 window+1 个观测时返回 (None, None)。
    """
    if len(series) <= window:
        return None, None
    latest = series[-1][1]
    ago = series[-1 - window][1]
    if ago is None or ago <= 0:
        return None, None
    return (latest / ago - 1) * 100.0, latest - ago


def family_label(name: str, n_members: int) -> str:
    """家族展示标签，如 '沪深300ETF家族(6)'。"""
    base = name.replace("ETF", "")
    return f"{base}家族({n_members})"
