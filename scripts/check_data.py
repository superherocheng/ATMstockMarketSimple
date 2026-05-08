#!/usr/bin/env python3
"""检查数据库中的市值数据"""
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
conn = engine.connect()

print("=== 数据检查 ===\n")

# 检查记录数
basic_count = conn.execute(text('SELECT COUNT(*) FROM stock_daily_basic')).fetchone()[0]
daily_count = conn.execute(text('SELECT COUNT(*) FROM stock_daily')).fetchone()[0]
stock_count = conn.execute(text('SELECT COUNT(*) FROM stock_info')).fetchone()[0]

print(f'stock_daily_basic: {basic_count:,} 条记录')
print(f'stock_daily: {daily_count:,} 条记录')
print(f'stock_info: {stock_count:,} 条记录')

# 检查日期
basic_max_date = conn.execute(text('SELECT MAX(trade_date) FROM stock_daily_basic')).fetchone()[0]
daily_max_date = conn.execute(text('SELECT MAX(trade_date) FROM stock_daily')).fetchone()[0]

print(f'\nstock_daily_basic 最新日期: {basic_max_date}')
print(f'stock_daily 最新日期: {daily_max_date}')

# 检查最新日期的数据量
basic_latest_count = conn.execute(
    text("SELECT COUNT(*) FROM stock_daily_basic WHERE trade_date = :date"),
    {"date": basic_max_date}
).fetchone()[0]
daily_latest_count = conn.execute(
    text("SELECT COUNT(*) FROM stock_daily WHERE trade_date = :date"),
    {"date": daily_max_date}
).fetchone()[0]

print(f'\nstock_daily_basic 最新日期记录数: {basic_latest_count}')
print(f'stock_daily 最新日期记录数: {daily_latest_count}')

# 检查能否JOIN上
test_join = conn.execute(
    text('''
        SELECT COUNT(*)
        FROM stock_info si
        JOIN stock_daily_basic sb ON si.ts_code = sb.ts_code
        WHERE sb.trade_date = :date
    '''),
    {"date": basic_max_date}
).fetchone()[0]

print(f'\nstock_info 和 stock_daily_basic 能JOIN上的股票数: {test_join}')

# 检查行业统计
if basic_max_date == daily_max_date:
    print(f'\n日期匹配，检查行业统计:')

    result = pd.read_sql(
        text('''
            SELECT
                si.sw_level1,
                COUNT(*) as stock_count,
                AVG(sb.total_mv) as avg_mv,
                AVG(sb.pe_ttm) as avg_pe,
                AVG(sb.pb) as avg_pb
            FROM stock_info si
            JOIN stock_daily_basic sb ON si.ts_code = sb.ts_code
            WHERE si.sw_level1 IS NOT NULL
                AND sb.trade_date = :date
            GROUP BY si.sw_level1
            ORDER BY stock_count DESC
            LIMIT 5
        '''),
        conn,
        params={"date": basic_max_date}
    )

    print(result)
else:
    print(f'\nWARN 日期不匹配！')
    print(f'stock_daily_basic: {basic_max_date}')
    print(f'stock_daily: {daily_max_date}')

conn.close()
