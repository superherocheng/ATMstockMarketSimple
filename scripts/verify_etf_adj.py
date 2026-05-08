#!/usr/bin/env python3
"""
P2.6: ETF 复权验证脚本
=======================
验证 Tushare fund_daily 返回的 ETF 价格是否需要复权调整。

背景:
  - Tushare pro.daily（个股）返回的是前复权价格
  - Tushare pro.fund_daily（ETF/基金）可能返回未复权价格
  - 如果未复权，ETF 在除息除权日附近会出现人为价格跳空

方法:
  1. 选取有分红的 ETF（如 510300.SH 沪深300ETF）
  2. 对比 fund_daily 返回的 close 与 fund_adj 调整后的 close
  3. 如果两者在某日差异显著（>0.5%），则确认需要复权

用法:
    python scripts/verify_etf_adj.py                           # 验证全部ETF
    python scripts/verify_etf_adj.py --ts_code 510300.SH       # 验证指定ETF
    python scripts/verify_etf_adj.py --sample                  # 抽样验证前3只
"""

import argparse
import os
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np
from dotenv import load_dotenv

ENV_FILE = PROJECT_ROOT / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

from config.config import get_pro, INDEX_ETF, SECTOR_ETF
from src.core.db_manager_postgresql import init_db_manager, get_db_manager


def check_etf_adj(pro, ts_code, name):
    """检查单只 ETF 是否需要复权调整。

    Returns:
        dict with: ts_code, name, total_dates, dates_with_diff, max_diff_pct, max_diff_date
    """
    print(f"\n{'─' * 60}")
    print(f"  检查: {name} ({ts_code})")
    print(f"{'─' * 60}")

    result = {
        "ts_code": ts_code,
        "name": name,
        "status": "unknown",
        "total_dates": 0,
        "dates_with_diff": 0,
        "max_diff_pct": 0.0,
        "max_diff_date": None,
        "adj_factor_count": 0,
    }

    # ── 1. 获取 fund_daily 原始日线 ──
    try:
        df_raw = pro.fund_daily(ts_code=ts_code)
        if df_raw is None or len(df_raw) == 0:
            print(f"    [SKIP] fund_daily 无数据")
            result["status"] = "no_data"
            return result
        df_raw = df_raw.sort_values("trade_date").reset_index(drop=True)
        result["total_dates"] = len(df_raw)
        print(f"    fund_daily: {len(df_raw)} 条日线")
    except Exception as e:
        print(f"    [ERR] fund_daily 获取失败: {e}")
        result["status"] = "fund_daily_error"
        return result

    # ── 2. 获取 fund_adj 复权因子 ──
    try:
        df_adj = pro.fund_adj(ts_code=ts_code)
        if df_adj is None or len(df_adj) == 0:
            print(f"    [WARN] fund_adj 无数据 —— 可能该ETF无分红/拆分")
            print(f"    [INFO] 无需复权调整，原始价格即准确")
            result["status"] = "no_adj_needed"
            return result

        df_adj = df_adj.sort_values("trade_date").reset_index(drop=True)
        result["adj_factor_count"] = len(df_adj)
        print(f"    fund_adj: {len(df_adj)} 条复权因子")
    except Exception as e:
        err_msg = str(e)
        if "权限" in err_msg or "积分" in err_msg:
            print(f"    [WARN] fund_adj 接口无权限，无法验证")
            print(f"    [INFO] 需积分 ≥ 2000 才可访问 fund_adj")
        else:
            print(f"    [ERR] fund_adj 获取失败: {e}")
        result["status"] = "fund_adj_error"
        return result

    # ── 3. 对比：原始 close vs 复权 close ──
    adj_map = dict(zip(df_adj["trade_date"], df_adj["adj_factor"]))

    if len(df_adj) == 0 or df_adj["adj_factor"].iloc[-1] <= 0:
        print(f"    [WARN] 复权因子无效")
        result["status"] = "invalid_adj_factor"
        return result

    latest_adj = float(df_adj["adj_factor"].iloc[-1])
    print(f"    最新复权因子: {latest_adj:.6f}")

    # 对比每个交易日的原始 close 与调整后 close
    diffs = []
    for _, row in df_raw.iterrows():
        td = str(row["trade_date"])
        adj = adj_map.get(td)
        if adj is None or adj <= 0:
            continue

        raw_close = float(row["close"])
        adj_close = raw_close * adj / latest_adj
        diff_pct = abs(adj_close - raw_close) / raw_close * 100

        if diff_pct > 0.01:  # 忽略浮点误差
            diffs.append((td, raw_close, adj_close, diff_pct))

    result["dates_with_diff"] = len(diffs)

    if diffs:
        max_diff = max(diffs, key=lambda x: x[3])
        result["max_diff_pct"] = round(max_diff[3], 4)
        result["max_diff_date"] = max_diff[0]

        print(f"    ❌ 发现 {len(diffs)} 个交易日存在价格差异")
        print(f"       最大差异日: {max_diff[0]} 差异 {max_diff[3]:.4f}%")
        print(f"       原始 close: {max_diff[1]:.4f} → 复权 close: {max_diff[2]:.4f}")
        print(f"    [ACTION] 需要应用 fund_adj 前复权！")
        result["status"] = "adj_needed"
    else:
        print(f"    ✅ 所有交易日价格一致，无需复权调整")
        result["status"] = "no_adj_needed"

    return result


def main():
    parser = argparse.ArgumentParser(description="ETF 复权验证工具")
    parser.add_argument("--ts_code", type=str, default=None, help="指定 ETF 代码")
    parser.add_argument("--sample", action="store_true", help="仅抽样前3只 ETF")
    args = parser.parse_args()

    db_url = os.getenv("DATABASE_URL")
    if db_url:
        try:
            init_db_manager(db_url)
        except Exception:
            pass  # DB 可选

    try:
        pro = get_pro()
    except ValueError as e:
        print(f"[ERR] {e}")
        sys.exit(1)

    # ── 确定要检查的 ETF ──
    if args.ts_code:
        all_etfs = INDEX_ETF | SECTOR_ETF
        if args.ts_code in all_etfs:
            etfs_to_check = {args.ts_code: all_etfs[args.ts_code]}
        else:
            print(f"[ERR] 未知 ETF 代码: {args.ts_code}")
            print(f"  已知代码: {', '.join(all_etfs.keys())}")
            sys.exit(1)
    else:
        etfs_to_check = INDEX_ETF | SECTOR_ETF  # merge both dicts

    if args.sample:
        etfs_to_check = dict(list(etfs_to_check.items())[:3])

    # ── 逐只检查 ──
    results = []
    for code, name in etfs_to_check.items():
        try:
            r = check_etf_adj(pro, code, name)
            results.append(r)
        except Exception as e:
            print(f"    [ERR] {name}: {e}")
            results.append({
                "ts_code": code, "name": name, "status": "error",
                "total_dates": 0, "dates_with_diff": 0,
                "max_diff_pct": 0, "max_diff_date": None,
                "adj_factor_count": 0,
            })

    # ── 汇总 ──
    print(f"\n{'=' * 60}")
    print(f"  汇总报告")
    print(f"{'=' * 60}")

    need_adj = [r for r in results if r["status"] == "adj_needed"]
    ok = [r for r in results if r["status"] == "no_adj_needed"]
    no_factor = [r for r in results if r["status"] == "no_data"]
    errors = [r for r in results if r["status"] not in ("adj_needed", "no_adj_needed", "no_data")]

    print(f"  ✅ 无需复权: {len(ok)} 只")
    print(f"  ❌ 需要复权: {len(need_adj)} 只")
    print(f"  ⬜ 无数据:   {len(no_factor)} 只")
    print(f"  ⚠️  错误:    {len(errors)} 只")

    if need_adj:
        print(f"\n  需要复权的 ETF:")
        for r in need_adj:
            print(f"    - {r['name']} ({r['ts_code']}) "
                  f"最大差异 {r['max_diff_pct']:.4f}% 于 {r['max_diff_date']}")

    if errors:
        print(f"\n  检查出错的 ETF:")
        for r in errors:
            print(f"    - {r['name']} ({r['ts_code']}): {r['status']}")

    print(f"\n  结论: {'部分 ETF 需要复权调整，已通过 _apply_etf_adj 处理' if need_adj else '当前 ETF 数据无需复权，或 fund_adj 权限不足无法验证'}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
