#!/usr/bin/env python3
"""
DuckDB 到 PostgreSQL 数据迁移脚本
=================================
安全迁移所有数据，确保数据完整性
"""
import sys
import os
from pathlib import Path
import duckdb
import pandas as pd
from sqlalchemy import create_engine, text
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DUCKDB_PATH = PROJECT_ROOT / "data" / "database" / "analysis.duckdb"

TABLE_DEFINITIONS = {
    "index_etf_daily": """
        CREATE TABLE IF NOT EXISTS index_etf_daily (
            ts_code VARCHAR(20) NOT NULL,
            trade_date VARCHAR(8) NOT NULL,
            open DOUBLE PRECISION,
            high DOUBLE PRECISION,
            low DOUBLE PRECISION,
            close DOUBLE PRECISION,
            vol DOUBLE PRECISION,
            amount DOUBLE PRECISION,
            pre_close DOUBLE PRECISION,
            pct_chg DOUBLE PRECISION,
            PRIMARY KEY (ts_code, trade_date)
        )
    """,
    "etf_share": """
        CREATE TABLE IF NOT EXISTS etf_share (
            ts_code VARCHAR(20) NOT NULL,
            trade_date VARCHAR(8) NOT NULL,
            fd_share DOUBLE PRECISION,
            PRIMARY KEY (ts_code, trade_date)
        )
    """,
    "sector_etf_daily": """
        CREATE TABLE IF NOT EXISTS sector_etf_daily (
            ts_code VARCHAR(20) NOT NULL,
            trade_date VARCHAR(8) NOT NULL,
            open DOUBLE PRECISION,
            high DOUBLE PRECISION,
            low DOUBLE PRECISION,
            close DOUBLE PRECISION,
            vol DOUBLE PRECISION,
            amount DOUBLE PRECISION,
            pre_close DOUBLE PRECISION,
            pct_chg DOUBLE PRECISION,
            PRIMARY KEY (ts_code, trade_date)
        )
    """,
    "stock_daily": """
        CREATE TABLE IF NOT EXISTS stock_daily (
            ts_code VARCHAR(20) NOT NULL,
            trade_date VARCHAR(8) NOT NULL,
            open DOUBLE PRECISION,
            high DOUBLE PRECISION,
            low DOUBLE PRECISION,
            close DOUBLE PRECISION,
            vol DOUBLE PRECISION,
            amount DOUBLE PRECISION,
            pre_close DOUBLE PRECISION,
            pct_chg DOUBLE PRECISION,
            PRIMARY KEY (ts_code, trade_date)
        )
    """,
    "stock_basic": """
        CREATE TABLE IF NOT EXISTS stock_basic (
            ts_code VARCHAR(20) PRIMARY KEY,
            name VARCHAR(100),
            industry VARCHAR(100),
            area VARCHAR(50),
            market VARCHAR(20),
            list_date VARCHAR(8)
        )
    """,
    "stock_daily_basic": """
        CREATE TABLE IF NOT EXISTS stock_daily_basic (
            ts_code VARCHAR(20) NOT NULL,
            trade_date VARCHAR(8) NOT NULL,
            pe DOUBLE PRECISION,
            pe_ttm DOUBLE PRECISION,
            pb DOUBLE PRECISION,
            ps DOUBLE PRECISION,
            ps_ttm DOUBLE PRECISION,
            total_mv DOUBLE PRECISION,
            circ_mv DOUBLE PRECISION,
            turnover_rate DOUBLE PRECISION,
            PRIMARY KEY (ts_code, trade_date)
        )
    """,
    "stock_fina_indicator": """
        CREATE TABLE IF NOT EXISTS stock_fina_indicator (
            ts_code VARCHAR(20) NOT NULL,
            ann_date VARCHAR(8),
            end_date VARCHAR(8) NOT NULL,
            roe DOUBLE PRECISION,
            netprofit_yoy DOUBLE PRECISION,
            tr_yoy DOUBLE PRECISION,
            grossprofit_margin DOUBLE PRECISION,
            netprofit_margin DOUBLE PRECISION,
            eps DOUBLE PRECISION,
            debt_to_assets DOUBLE PRECISION,
            current_ratio DOUBLE PRECISION,
            PRIMARY KEY (ts_code, end_date)
        )
    """,
    "precomputed_cache": """
        CREATE TABLE IF NOT EXISTS precomputed_cache (
            cache_key VARCHAR(255) PRIMARY KEY,
            updated_at VARCHAR(20),
            data_json TEXT
        )
    """,
    "lhb_data": """
        CREATE TABLE IF NOT EXISTS lhb_data (
            trade_date VARCHAR(8) PRIMARY KEY,
            data_json TEXT
        )
    """,
    "stock_info": """
        CREATE TABLE IF NOT EXISTS stock_info (
            ts_code VARCHAR(20) PRIMARY KEY,
            name VARCHAR(100),
            area VARCHAR(50),
            market VARCHAR(20),
            list_date VARCHAR(8),
            sw_level1 VARCHAR(100),
            sw_level2 VARCHAR(100),
            sw_level3 VARCHAR(100),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "concept_dict": """
        CREATE TABLE IF NOT EXISTS concept_dict (
            concept_id INTEGER PRIMARY KEY,
            concept_name TEXT UNIQUE NOT NULL,
            concept_category VARCHAR(100)
        )
    """,
    "stock_concept": """
        CREATE TABLE IF NOT EXISTS stock_concept (
            ts_code VARCHAR(20) NOT NULL,
            concept_id INTEGER NOT NULL,
            PRIMARY KEY (ts_code, concept_id)
        )
    """,
}

INDEX_DEFINITIONS = {
    "stock_daily": [
        "CREATE INDEX IF NOT EXISTS idx_stock_daily_ts ON stock_daily(ts_code)",
        "CREATE INDEX IF NOT EXISTS idx_stock_daily_date ON stock_daily(trade_date)",
        "CREATE INDEX IF NOT EXISTS idx_stock_daily_date_code ON stock_daily(trade_date, ts_code)",
    ],
    "stock_daily_basic": [
        "CREATE INDEX IF NOT EXISTS idx_stock_daily_basic_ts ON stock_daily_basic(ts_code)",
        "CREATE INDEX IF NOT EXISTS idx_stock_daily_basic_date ON stock_daily_basic(trade_date)",
        "CREATE INDEX IF NOT EXISTS idx_stock_daily_basic_date_code ON stock_daily_basic(trade_date, ts_code)",
    ],
    "stock_fina_indicator": [
        "CREATE INDEX IF NOT EXISTS idx_stock_fina_ts ON stock_fina_indicator(ts_code)",
    ],
    "stock_basic": [
        "CREATE INDEX IF NOT EXISTS idx_stock_basic_industry ON stock_basic(industry)",
    ],
    "etf_share": [
        "CREATE INDEX IF NOT EXISTS idx_etf_share_ts ON etf_share(ts_code)",
    ],
    "sector_etf_daily": [
        "CREATE INDEX IF NOT EXISTS idx_sector_etf_ts ON sector_etf_daily(ts_code)",
    ],
    "index_etf_daily": [
        "CREATE INDEX IF NOT EXISTS idx_index_etf_ts ON index_etf_daily(ts_code)",
    ],
    "stock_concept": [
        "CREATE INDEX IF NOT EXISTS idx_stock_concept_code ON stock_concept(ts_code)",
        "CREATE INDEX IF NOT EXISTS idx_stock_concept_id ON stock_concept(concept_id)",
        "CREATE INDEX IF NOT EXISTS idx_stock_concept_concept_code ON stock_concept(concept_id, ts_code)",
    ],
    "stock_info": [
        "CREATE INDEX IF NOT EXISTS idx_stock_info_sw_level1 ON stock_info(sw_level1)",
        "CREATE INDEX IF NOT EXISTS idx_stock_info_sw_level2 ON stock_info(sw_level2)",
        "CREATE INDEX IF NOT EXISTS idx_stock_info_sw_level3 ON stock_info(sw_level3)",
    ],
}


def get_duckdb_connection():
    """获取DuckDB连接"""
    if not DUCKDB_PATH.exists():
        print(f"❌ DuckDB文件不存在: {DUCKDB_PATH}")
        sys.exit(1)
    
    return duckdb.connect(str(DUCKDB_PATH), read_only=True)


def get_postgres_engine(db_url: str):
    """获取PostgreSQL引擎"""
    return create_engine(db_url, pool_pre_ping=True)


def create_tables(pg_engine):
    """在PostgreSQL中创建表结构"""
    print("\n📋 创建PostgreSQL表结构...")
    
    with pg_engine.connect() as conn:
        for table_name, create_sql in tqdm(TABLE_DEFINITIONS.items(), desc="创建表"):
            try:
                conn.execute(text(create_sql))
                conn.commit()
            except Exception as e:
                print(f"  ⚠️  创建表 {table_name} 失败: {e}")
        
        print("\n📇 创建索引...")
        for table_name, indexes in INDEX_DEFINITIONS.items():
            for idx_sql in tqdm(indexes, desc=f"索引 {table_name}"):
                try:
                    conn.execute(text(idx_sql))
                    conn.commit()
                except Exception as e:
                    print(f"  ⚠️  创建索引失败: {e}")
    
    print("✅ 表结构创建完成")


def migrate_table_data(duck_conn, pg_engine, table_name: str):
    """迁移单个表的数据"""
    print(f"\n📦 迁移表: {table_name}")
    
    try:
        count_result = duck_conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
        total_rows = count_result[0] if count_result else 0
        
        if total_rows == 0:
            print(f"  ℹ️  表 {table_name} 为空，跳过")
            return 0
        
        print(f"  📊 总行数: {total_rows:,}")
        
        df = duck_conn.execute(f"SELECT * FROM {table_name}").fetchdf()
        
        chunk_size = 10000
        total_chunks = (len(df) + chunk_size - 1) // chunk_size
        
        with pg_engine.connect() as conn:
            for i in tqdm(range(total_chunks), desc=f"写入 {table_name}"):
                start_idx = i * chunk_size
                end_idx = min((i + 1) * chunk_size, len(df))
                chunk = df.iloc[start_idx:end_idx]
                
                chunk.to_sql(
                    table_name,
                    conn,
                    if_exists='append',
                    index=False,
                    method='multi'
                )
                conn.commit()
        
        print(f"  ✅ 迁移完成: {len(df):,} 行")
        return len(df)
        
    except Exception as e:
        print(f"  ❌ 迁移失败: {e}")
        return 0


def verify_migration(duck_conn, pg_engine):
    """验证数据迁移完整性"""
    print("\n🔍 验证数据完整性...")
    
    all_ok = True
    with pg_engine.connect() as pg_conn:
        for table_name in TABLE_DEFINITIONS.keys():
            try:
                duck_count = duck_conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                
                pg_count = pg_conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).fetchone()[0]
                
                if duck_count == pg_count:
                    print(f"  ✅ {table_name}: {duck_count:,} 行 (一致)")
                else:
                    print(f"  ❌ {table_name}: DuckDB {duck_count:,} 行, PostgreSQL {pg_count:,} 行 (不一致)")
                    all_ok = False
                    
            except Exception as e:
                print(f"  ⚠️  {table_name}: 验证失败 - {e}")
                all_ok = False
    
    return all_ok


def main():
    """主函数"""
    print("=" * 60)
    print("🚀 DuckDB → PostgreSQL 数据迁移")
    print("=" * 60)
    
    if len(sys.argv) < 2:
        print("\n❌ 请提供PostgreSQL数据库URL")
        print("\n使用方法:")
        print("  python scripts/migrate_to_postgresql.py \"postgresql://user:password@host:port/database\"")
        print("\n示例:")
        print("  python scripts/migrate_to_postgresql.py \"postgresql://postgres:postgres@localhost:5432/atm_stock_market\"")
        sys.exit(1)
    
    db_url = sys.argv[1]
    
    print(f"\n📂 DuckDB路径: {DUCKDB_PATH}")
    print(f"🐘 PostgreSQL URL: {db_url.split('@')[1] if '@' in db_url else db_url}")
    
    duck_conn = get_duckdb_connection()
    pg_engine = get_postgres_engine(db_url)
    
    try:
        create_tables(pg_engine)
        
        print("\n📦 开始迁移数据...")
        total_migrated = 0
        for table_name in TABLE_DEFINITIONS.keys():
            migrated = migrate_table_data(duck_conn, pg_engine, table_name)
            total_migrated += migrated
        
        print(f"\n✅ 总计迁移: {total_migrated:,} 行")
        
        if verify_migration(duck_conn, pg_engine):
            print("\n" + "=" * 60)
            print("🎉 迁移成功！所有数据已完整迁移到PostgreSQL")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("⚠️  迁移完成，但数据验证发现问题，请检查日志")
            print("=" * 60)
            sys.exit(1)
            
    finally:
        duck_conn.close()
        pg_engine.dispose()


if __name__ == "__main__":
    main()
