"""
ATMstockMarket 交易日历工具
============================
提供统一的交易日查询与数据库新鲜度验证。

核心功能：
  - get_latest_trading_date()  获取最新可用交易日（考虑市场是否已收盘）
  - is_fresh(table)            检查数据表是否已是最新
  - get_dates_to_fetch(table)  返回需要补拉的交易日列表
  - verify_database()          打印所有表的新鲜度报告

用法：
    python trading_calendar.py          # 查看数据库状态报告
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

# ── 单例缓存 ──────────────────────────────────────
_cal_cache = None
_cal_cache_range = (None, None)
_latest_td_cache = None
_latest_td_cache_ts = 0.0

# A股收盘后数据可用时间（北京时间）—— 15:00 收盘，留 30 分钟 buffer
_DATA_AVAILABLE_HOUR_BJ = 16


# ══════════════════════════════════════════════════
#  时间工具（公开 API）
# ══════════════════════════════════════════════════
def now_beijing():
    """当前北京时间 (UTC+8)。使用 datetime.utcnow() 获取 UTC 时间再加 8 小时，
    完全不依赖服务器本地时区设置，确保在不同地区的 VPS 都能正确工作。"""
    return datetime.utcnow() + timedelta(hours=8)


def _now_beijing():
    return now_beijing()


def _fetch_calendar(start_date, end_date):
    """从 Tushare 拉取交易日历（带内存缓存，避免重复 API 调用）。"""
    global _cal_cache, _cal_cache_range

    # 缓存命中
    if _cal_cache is not None:
        cs, ce = _cal_cache_range
        if cs and ce and start_date >= cs and end_date <= ce:
            mask = (_cal_cache["cal_date"] >= start_date) & (
                _cal_cache["cal_date"] <= end_date
            )
            return _cal_cache[mask].copy()

    # 缓存未命中：扩展范围以提高缓存命中率
    s = datetime.strptime(start_date, "%Y%m%d")
    e = datetime.strptime(end_date, "%Y%m%d")
    ext_start = (s - timedelta(days=30)).strftime("%Y%m%d")
    ext_end = (e + timedelta(days=30)).strftime("%Y%m%d")

    from config.config import get_pro

    pro = get_pro()
    cal = pro.trade_cal(exchange="SSE", start_date=ext_start, end_date=ext_end)
    _cal_cache = cal
    _cal_cache_range = (ext_start, ext_end)

    mask = (cal["cal_date"] >= start_date) & (cal["cal_date"] <= end_date)
    return cal[mask].copy()


# ══════════════════════════════════════════════════
#  公开 API
# ══════════════════════════════════════════════════
def get_open_trade_dates(start_date=None, end_date=None):
    """返回 start_date ~ end_date 之间（含）的开市交易日列表。

    Args:
        start_date: YYYYMMDD 字符串，默认一年前
        end_date:   YYYYMMDD 字符串，默认今天
    Returns:
        list[str] — 排序后的交易日字符串
    """
    today = datetime.utcnow().strftime("%Y%m%d")
    if start_date is None:
        start_date = (datetime.utcnow() - timedelta(days=365)).strftime("%Y%m%d")
    if end_date is None:
        end_date = today

    cal = _fetch_calendar(start_date, end_date)
    return sorted(cal[cal["is_open"] == 1]["cal_date"].tolist())


def get_latest_trading_date():
    """获取"最新可用交易日"——即数据理应已存在的最近一个交易日。

    三级策略：
      1. Tushare 交易日历（权威来源）
      2. DB stock_daily 表的 MAX(trade_date)（实际交易证据）
      3. 工作日推断（当日历明显过时时补充）

    如果今天是交易日且已过 16:00（北京时间），返回今天。
    如果今天是交易日但还没收盘，返回上一个交易日。
    结果缓存 30 分钟。
    """
    global _latest_td_cache, _latest_td_cache_ts

    now_ts = datetime.utcnow().timestamp()
    if _latest_td_cache and (now_ts - _latest_td_cache_ts) < 1800:
        return _latest_td_cache

    now_bj = _now_beijing()
    today_str = now_bj.strftime("%Y%m%d")
    lookback = (now_bj - timedelta(days=10)).strftime("%Y%m%d")

    candidates = []
    cal_dates = None

    # ── 来源 1：Tushare 交易日历 ──
    cal_latest = None
    try:
        cal_dates = get_open_trade_dates(lookback, today_str)
        if cal_dates:
            cal_latest = cal_dates[-1]
            candidates.append(cal_latest)
    except Exception:
        pass

    # ── 来源 2：DB stock_daily 实际数据 ──
    db_max = get_db_max_date("stock_daily")
    if db_max and db_max <= today_str:
        candidates.append(db_max)

    if not candidates:
        return None

    latest = max(candidates)

    # ── 来源 3：当日历明显过时（>3 天）且今天为工作日时，推断今天 ──
    if cal_latest:
        cal_age = (now_bj.date() - datetime.strptime(cal_latest, "%Y%m%d").date()).days
    else:
        cal_age = 999

    today_dt = now_bj.date()
    if cal_age > 3 and latest < today_str and today_dt.weekday() < 5:
        if now_bj.hour >= _DATA_AVAILABLE_HOUR_BJ:
            latest = today_str

    # ── 市场未收盘 → 排除今天 ──
    if latest == today_str and now_bj.hour < _DATA_AVAILABLE_HOUR_BJ:
        # 回退到之前最近的已知交易日
        candidates_minus_today = [c for c in candidates if c < today_str]
        if candidates_minus_today:
            latest = max(candidates_minus_today)
        elif cal_dates:
            # cal_dates 中有完整日历，取今天之前的最后一个交易日
            prev_from_cal = [d for d in cal_dates if d < today_str]
            latest = max(prev_from_cal) if prev_from_cal else None
        else:
            latest = None

    _latest_td_cache = latest
    _latest_td_cache_ts = now_ts
    return latest


def get_db_max_date(table, ts_code=None, date_column="trade_date"):
    """查询某张表的 MAX(date_column)。"""
    try:
        from src.core.db_manager_postgresql import get_db_manager
        from sqlalchemy import text
        
        db = get_db_manager()
        with db.get_connection() as conn:
            if ts_code:
                sql = f"SELECT MAX({date_column}) FROM {table} WHERE ts_code = :ts_code"
                result = conn.execute(text(sql), {"ts_code": ts_code}).fetchone()
            else:
                sql = f"SELECT MAX({date_column}) FROM {table}"
                result = conn.execute(text(sql)).fetchone()
            return result[0] if result and result[0] else None
    except Exception:
        return None


def is_fresh(table, ts_code=None):
    """检查数据表是否已同步到最新交易日。

    Returns:
        True  — db_max_date >= latest_trading_date
        False — 否则
    """
    latest = get_latest_trading_date()
    if not latest:
        return False
    db_max = get_db_max_date(table, ts_code)
    return db_max is not None and db_max >= latest


def get_dates_to_fetch(table, ts_code=None, start_date=None):
    """返回需要补拉的交易日列表（DB 中缺失且 <= 最新交易日的日期）。

    Args:
        table:      数据表名
        ts_code:    可选，按具体代码过滤
        start_date: 可选，强制起始日期（YYYYMMDD）
    Returns:
        list[str] — 需要拉取的交易日
    """
    latest = get_latest_trading_date()
    if not latest:
        return []

    db_max = get_db_max_date(table, ts_code)

    if start_date:
        fetch_from = start_date
    elif db_max:
        fetch_from = db_max
    else:
        fetch_from = (datetime.utcnow() - timedelta(days=365)).strftime("%Y%m%d")

    dates = get_open_trade_dates(fetch_from, latest)

    # 如果日历没有覆盖到最新交易日（日历过时），
    # 用工作日逻辑补充缺失的日期
    if not dates or (dates and dates[-1] < latest):
        start_dt = datetime.strptime(dates[-1] if dates else fetch_from, "%Y%m%d").date()
        end_dt = datetime.strptime(latest, "%Y%m%d").date()
        d = start_dt + timedelta(days=1)
        existing = set(dates)
        while d <= end_dt:
            if d.weekday() < 5:  # Mon-Fri
                ds = d.strftime("%Y%m%d")
                if ds not in existing:
                    dates.append(ds)
            d += timedelta(days=1)
        dates = sorted(set(dates))

    # 去掉 DB 中已有的最后一天
    if db_max and db_max in dates:
        idx = dates.index(db_max)
        dates = dates[idx + 1:]

    return dates


def verify_database():
    """打印所有核心表的新鲜度报告，返回 dict 结果。"""
    latest = get_latest_trading_date()
    if not latest:
        print("[ERR] 无法确定最新交易日，请检查 Tushare Token 和网络")
        return {}

    header = "  数据库状态检查"
    print(f"\n{'=' * 62}")
    print(f"{header}  (最新交易日: {latest})")
    print(f"{'=' * 62}")

    tables = [
        ("index_etf_daily", "指数ETF日线", "trade_date"),
        ("etf_share", "ETF份额", "trade_date"),
        ("sector_etf_daily", "行业ETF日线", "trade_date"),
        ("etf_adj_factor", "ETF复权因子", "trade_date"),
        ("stock_daily", "个股日线", "trade_date"),
        ("stock_daily_basic", "每日估值", "trade_date"),
        ("stock_fina_indicator", "财务指标", "end_date"),
    ]

    results = {}
    for table, desc, date_col in tables:
        db_max = get_db_max_date(table, date_column=date_col)
        fresh = db_max is not None and db_max >= latest
        gap = 0
        if db_max and db_max < latest:
            behind = get_open_trade_dates(db_max, latest)
            gap = len([d for d in behind if d > db_max])

        if fresh:
            status = "OK  最新"
        elif db_max:
            status = f"!!  落后 {gap:>2d} 个交易日 (DB最新: {db_max})"
        else:
            status = "??  无数据"

        print(f"  {desc:12s} ({table:22s}): {status}")
        results[table] = {"max_date": db_max, "is_fresh": fresh, "gap_days": gap}

    print(f"{'=' * 62}\n")
    return results


# ══════════════════════════════════════════════════
#  CLI 入口
# ══════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"  北京时间: {_now_beijing().strftime('%Y-%m-%d %H:%M:%S')}")
    latest = get_latest_trading_date()
    if latest:
        print(f"  最新可用交易日: {latest}")
    verify_database()