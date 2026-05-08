#!/usr/bin/env python3
"""检查日期范围"""
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

# 检查日期范围
print('=== 日期范围检查 ===')
date_stats = pd.read_sql(text('''
    SELECT
        trade_date,
        COUNT(*) as record_count
    FROM stock_daily_basic
    GROUP BY trade_date
    ORDER BY trade_date DESC
    LIMIT 5
'''), conn)

print(date_stats)

# 检查前一个真实日期
prev_date = conn.execute(text('''
    SELECT MAX(trade_date)
    FROM stock_daily_basic
    WHERE trade_date < '20260430'
''')).fetchone()[0]

print(f'\n前一个真实日期: {prev_date}')

# 使用前一个真实日期计算行业统计
print(f'\n=== 使用 {prev_date} 的行业统计 ===')
result = pd.read_sql(text(f'''
    SELECT
        si.sw_level1,
        COUNT(*) as stock_count,
        AVG(sb.total_mv) as avg_mv,
        AVG(sb.pe_ttm) as avg_pe,
        AVG(sb.pb) as avg_pb
    FROM stock_info si
    JOIN stock_daily_basic sb ON si.ts_code = sb.ts_code
    WHERE si.sw_level1 IS NOT NULL
        AND sb.trade_date = '{prev_date}'
    GROUP BY si.sw_level1
    ORDER BY stock_count DESC
    LIMIT 10
'''), conn)

print(result)

conn.close()
