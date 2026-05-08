"""
ATMstockMarket AKShare 数据获取脚本 v4
=======================================
v3: 移除北向资金（数据源已于 2024-08-16 停更）。
v4: 移除机构推荐模块。

获取龙虎榜数据。

用法：
    cd ATMstockMarket
    python src/data_fetchers/akshare_fetcher.py              # 获取龙虎榜（自动跳过已是最新）
    python src/data_fetchers/akshare_fetcher.py --verify     # 仅检查数据库状态
"""
import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="akshare")
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

import argparse
import time
import random
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
CSV_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "akshare"

from src.core.trading_calendar import (
    get_latest_trading_date,
    verify_database,
    now_beijing,
)

RETRY_MAX = 3
RETRY_BASE_SEC = 1.0


def _safe_fetch(func, **kwargs):
    """带重试的安全获取，返回 DataFrame 或 None"""
    last_err = None
    for attempt in range(RETRY_MAX):
        try:
            df = func(**kwargs)
            if df is None or df.empty:
                return None
            return df
        except Exception as e:
            last_err = e
            delay = RETRY_BASE_SEC * (2 ** attempt) + random.uniform(0.5, 1.5)
            print(f"    [RETRY {attempt+1}/{RETRY_MAX}] {e}, 等待{delay:.1f}s...")
            time.sleep(delay)
    print(f"    [ERR] {last_err}")
    return None


def fetch_lhb():
    """获取龙虎榜个股上榜统计，保存为每日 CSV。

    新鲜度检查：如果 CSV 已存在于最新交易日，跳过。
    """
    latest = get_latest_trading_date()
    if not latest:
        print("  [WARN] 无法确定最新交易日，继续拉取...")

    CSV_DIR.mkdir(parents=True, exist_ok=True)

    if latest:
        csv_path = CSV_DIR / f"lhb_{latest}.csv"
        if csv_path.exists():
            print(f"[SKIP] 龙虎榜已是最新 ({latest})，跳过")
            return

    import akshare as ak

    print("  获取龙虎榜数据...")
    df = _safe_fetch(ak.stock_lhb_ggtj_sina, symbol="5")
    if df is None:
        print("    [SKIP] 龙虎榜返回空数据")
        return

    today = now_beijing().strftime("%Y%m%d")
    csv_path = CSV_DIR / f"lhb_{today}.csv"

    df.to_csv(str(csv_path), index=False, encoding="utf-8-sig")
    print(f"    保存 {len(df)} 条到 {csv_path.name}")
    print("[OK] 龙虎榜获取完成")


def main():
    parser = argparse.ArgumentParser(description="ATMstockMarket AKShare 数据获取 v4")
    parser.add_argument("--verify", action="store_true", help="仅检查数据库状态")
    args = parser.parse_args()

    print("=" * 50)
    print("  ATMstockMarket AKShare 数据获取 v4")
    print(f"  {now_beijing().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    if args.verify:
        verify_database()
        return

    latest = get_latest_trading_date()
    if latest:
        print(f"  最新可用交易日: {latest}")

    fetch_lhb()
    print(f"\n[DONE] AKShare 数据获取完成！({now_beijing().strftime('%H:%M:%S')})")


if __name__ == "__main__":
    main()
