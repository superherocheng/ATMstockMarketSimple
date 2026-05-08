#!/usr/bin/env python3
"""
检查行业分析数据完整性
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
ENV_FILE = PROJECT_ROOT / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

from sqlalchemy import create_engine, text
import pandas as pd

db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("[ERROR] DATABASE_URL not set")
    sys.exit(1)
engine = create_engine(db_url)

def check_industry_data():
    """检查行业分析相关数据"""
    print("=" * 60)
    print("行业分析数据完整性检查")
    print("=" * 60)

    conn = engine.connect()

    # 1. 检查 stock_info 表
    print("\n[1. stock_info 表]")
    try:
        result = conn.execute(text("""
            SELECT
                COUNT(*) as total_stocks,
                COUNT(DISTINCT sw_level1) as industries,
                COUNT(CASE WHEN sw_level1 IS NOT NULL AND sw_level1 != '' THEN 1 END) as with_industry
            FROM stock_info
        """)).fetchone()

        print(f"  总股票数: {result[0]:,}")
        print(f"  行业数量: {result[1]}")
        print(f"  有行业分类的股票: {result[2]:,}")

        if result[2] == 0:
            print("  WARN 没有股票有行业分类！请先加载 ALLSYMBOL.csv")
    except Exception as e:
        print(f"  X 查询失败: {e}")

    # 2. 检查 stock_daily_basic 表
    print("\n[2. stock_daily_basic 表]")
    try:
        result = conn.execute(text("""
            SELECT
                COUNT(*) as total_records,
                COUNT(DISTINCT ts_code) as stocks,
                MAX(trade_date) as latest_date,
                MIN(trade_date) as earliest_date
            FROM stock_daily_basic
        """)).fetchone()

        print(f"  总记录数: {result[0]:,}")
        print(f"  股票数量: {result[1]:,}")
        print(f"  最新日期: {result[2]}")
        print(f"  最早日期: {result[3]}")

        if result[0] == 0:
            print("  WARN stock_daily_basic 表为空！请运行: python fetch_data.py --funda")
    except Exception as e:
        print(f"  X 查询失败: {e}")

    # 3. 检查 stock_daily 表
    print("\n[3. stock_daily 表]")
    try:
        result = conn.execute(text("""
            SELECT
                COUNT(*) as total_records,
                COUNT(DISTINCT ts_code) as stocks,
                MAX(trade_date) as latest_date
            FROM stock_daily
        """)).fetchone()

        print(f"  总记录数: {result[0]:,}")
        print(f"  股票数量: {result[1]:,}")
        print(f"  最新日期: {result[2]}")
    except Exception as e:
        print(f"  X 查询失败: {e}")

    # 4. 检查数据关联性
    print("\n[4. 数据关联性检查]")
    try:
        # 检查 stock_info 和 stock_daily_basic 的关联
        result = conn.execute(text("""
            SELECT
                COUNT(DISTINCT si.ts_code) as total_in_info,
                COUNT(DISTINCT CASE WHEN sb.ts_code IS NOT NULL THEN si.ts_code END) as in_daily_basic,
                COUNT(DISTINCT CASE WHEN sb.ts_code IS NULL THEN si.ts_code END) as not_in_daily_basic
            FROM stock_info si
            LEFT JOIN (
                SELECT DISTINCT ts_code
                FROM stock_daily_basic
                WHERE trade_date = (SELECT MAX(trade_date) FROM stock_daily_basic)
            ) sb ON si.ts_code = sb.ts_code
            WHERE si.sw_level1 IS NOT NULL AND si.sw_level1 != ''
        """)).fetchone()

        print(f"  有行业分类的股票: {result[0]:,}")
        print(f"  在 stock_daily_basic 中的: {result[1]:,}")
        print(f"  不在 stock_daily_basic 中的: {result[2]:,}")

        if result[2] > 0:
            print(f"  WARN 有 {result[2]:,} 只股票没有每日估值数据")
    except Exception as e:
        print(f"  X 查询失败: {e}")

    # 5. 检查行业数据示例
    print("\n[5. 行业数据示例（前5个行业）]")
    try:
        result = pd.read_sql(text("""
            SELECT
                si.sw_level1 as industry,
                COUNT(DISTINCT si.ts_code) as stock_count,
                AVG(sb.total_mv) as avg_mv,
                AVG(sb.pe_ttm) as avg_pe,
                AVG(sb.pb) as avg_pb
            FROM stock_info si
            LEFT JOIN stock_daily_basic sb ON si.ts_code = sb.ts_code
                AND sb.trade_date = (SELECT MAX(trade_date) FROM stock_daily_basic)
            WHERE si.sw_level1 IS NOT NULL AND si.sw_level1 != ''
            GROUP BY si.sw_level1
            ORDER BY stock_count DESC
            LIMIT 5
        """), conn)

        print(result.to_string(index=False))

        # 检查是否有数据
        if result['avg_mv'].isna().all():
            print("\n  WARN 所有行业的平均市值都是 NULL！")
            print("  这可能是因为:")
            print("    1. stock_daily_basic 表没有数据")
            print("    2. stock_daily_basic 的最新日期与 stock_daily 不匹配")
            print("    3. stock_info 和 stock_daily_basic 的股票代码不匹配")
    except Exception as e:
        print(f"  X 查询失败: {e}")

    # 6. 检查日期匹配
    print("\n[6. 日期匹配检查]")
    try:
        daily_date = conn.execute(text("SELECT MAX(trade_date) FROM stock_daily")).fetchone()[0]
        basic_date = conn.execute(text("SELECT MAX(trade_date) FROM stock_daily_basic")).fetchone()[0]

        print(f"  stock_daily 最新日期: {daily_date}")
        print(f"  stock_daily_basic 最新日期: {basic_date}")

        if daily_date != basic_date:
            print(f"  WARN 日期不匹配！这可能导致数据关联失败")
    except Exception as e:
        print(f"  X 查询失败: {e}")

    conn.close()

    print("\n" + "=" * 60)
    print("检查完成")
    print("=" * 60)

if __name__ == "__main__":
    check_industry_data()
