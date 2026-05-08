#!/usr/bin/env python3
"""生成示例市值数据"""
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
import random

db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("[ERROR] DATABASE_URL not set")
    sys.exit(1)
engine = create_engine(db_url)
conn = engine.connect()

# 获取所有股票代码
stocks = pd.read_sql(text("""
    SELECT ts_code, name, sw_level1
    FROM stock_info
    WHERE sw_level1 IS NOT NULL
"""), conn)

print(f"找到 {len(stocks)} 只股票")

# 获取最新交易日期
latest_date = conn.execute(text("SELECT MAX(trade_date) FROM stock_daily")).fetchone()[0]
print(f"最新交易日期: {latest_date}")

# 生成市值数据
data = []
for _, row in stocks.iterrows():
    ts_code = row['ts_code']
    name = row['name']
    industry = row['sw_level1']

    # 根据行业设定合理的市值范围
    if industry == '银行':
        total_mv = random.uniform(5000, 30000)  # 5000-30000亿
        pe = random.uniform(4, 10)
        pb = random.uniform(0.5, 1.0)
    elif industry == '非银金融':
        total_mv = random.uniform(3000, 20000)
        pe = random.uniform(10, 25)
        pb = random.uniform(1.0, 2.0)
    elif industry in ['电子', '计算机', '通信']:
        total_mv = random.uniform(500, 8000)
        pe = random.uniform(20, 80)
        pb = random.uniform(2.0, 8.0)
    elif industry in ['医药生物']:
        total_mv = random.uniform(300, 5000)
        pe = random.uniform(20, 60)
        pb = random.uniform(2.0, 6.0)
    elif industry in ['食品饮料']:
        total_mv = random.uniform(500, 6000)
        pe = random.uniform(25, 60)
        pb = random.uniform(3.0, 10.0)
    elif industry in ['家用电器']:
        total_mv = random.uniform(500, 5000)
        pe = random.uniform(10, 30)
        pb = random.uniform(1.5, 5.0)
    elif industry in ['汽车']:
        total_mv = random.uniform(500, 6000)
        pe = random.uniform(15, 40)
        pb = random.uniform(1.0, 4.0)
    elif industry in ['公用事业']:
        total_mv = random.uniform(500, 3000)
        pe = random.uniform(10, 25)
        pb = random.uniform(1.0, 2.5)
    elif industry in ['房地产']:
        total_mv = random.uniform(300, 3000)
        pe = random.uniform(5, 15)
        pb = random.uniform(0.5, 1.5)
    else:
        total_mv = random.uniform(200, 3000)
        pe = random.uniform(10, 40)
        pb = random.uniform(1.0, 4.0)

    turnover_rate = random.uniform(0.5, 8.0)

    data.append({
        'ts_code': ts_code,
        'trade_date': latest_date,
        'pe': round(pe * 0.9, 2),  # PE
        'pe_ttm': round(pe, 2),     # PE TTM
        'pb': round(pb, 2),         # PB
        'ps': round(random.uniform(1, 10), 2),  # PS
        'ps_ttm': round(random.uniform(1, 10), 2),  # PS TTM
        'total_mv': round(total_mv, 2),  # 总市值
        'circ_mv': round(total_mv * 0.7, 2),  # 流通市值
        'turnover_rate': round(turnover_rate, 2)
    })

df = pd.DataFrame(data)

# 删除旧数据
conn.execute(text(f"DELETE FROM stock_daily_basic WHERE trade_date = '{latest_date}'"))
conn.commit()

# 插入新数据 (using pandas to_sql instead of DuckDB CREATE TABLE AS SELECT)
df.to_sql('stock_daily_basic', conn, if_exists='append', index=False, method='multi')
conn.commit()

print(f"OK 成功生成 {len(df)} 条市值数据")
print(f"\n数据示例:")
print(df.head(10))

# 验证数据
result = pd.read_sql(text("""
    SELECT
        si.sw_level1,
        COUNT(*) as stock_count,
        AVG(sb.total_mv) as avg_mv,
        AVG(sb.pe_ttm) as avg_pe,
        AVG(sb.pb) as avg_pb
    FROM stock_info si
    JOIN stock_daily_basic sb ON si.ts_code = sb.ts_code
    WHERE si.sw_level1 IS NOT NULL
    GROUP BY si.sw_level1
    ORDER BY stock_count DESC
    LIMIT 10
"""), conn)

print("\n行业统计:")
print(result)

conn.close()
