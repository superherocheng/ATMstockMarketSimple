"""
ALLSYMBOL.csv 数据加载脚本
===========================
将外部股票分类数据导入 PostgreSQL 数据库

用法:
    python load_allsymbol.py                    # 从默认路径加载
    python load_allsymbol.py --path /path/to/   # 指定数据路径
    python load_allsymbol.py --verify           # 验证数据一致性
    python load_allsymbol.py --separator "|"    # 指定概念分隔符
"""
import argparse
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Set

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

import pandas as pd
from sqlalchemy import text

from src.core.db_manager_postgresql import init_db_manager, get_db_manager
from src.core.trading_calendar import now_beijing


SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "database"
EXTERNAL_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "external"
ALLSYMBOL_PATH = EXTERNAL_DATA_DIR / "ALLSYMBOL.csv"
META_PATH = EXTERNAL_DATA_DIR / "ALLSYMBOL.meta.json"

DEFAULT_CONCEPT_SEPARATOR = "|"


def detect_separator(concept_str: str) -> str:
    """自动检测概念分隔符"""
    if not concept_str or pd.isna(concept_str):
        return DEFAULT_CONCEPT_SEPARATOR
    
    concept_str = str(concept_str)
    
    if '|' in concept_str:
        return '|'
    elif ',' in concept_str:
        return ','
    elif '，' in concept_str:
        return '，'
    else:
        return DEFAULT_CONCEPT_SEPARATOR


def parse_concepts(concept_str: str, separator: str = None) -> List[str]:
    """解析概念字符串，返回概念列表"""
    if pd.isna(concept_str) or not concept_str:
        return []
    
    concept_str = str(concept_str)
    
    if separator is None:
        separator = detect_separator(concept_str)
    
    return [c.strip() for c in concept_str.split(separator) if c.strip()]


def calculate_checksum(file_path: Path) -> str:
    """计算文件 SHA256 校验和"""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return f"sha256:{sha256.hexdigest()}"


def load_csv_data(csv_path: Path) -> pd.DataFrame:
    """加载 CSV 数据，自动检测编码"""
    encodings = ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']
    
    for encoding in encodings:
        try:
            df = pd.read_csv(csv_path, encoding=encoding)
            print(f"[OK] 成功加载 CSV ({encoding}): {len(df)} 行, {len(df.columns)} 列")
            return df
        except UnicodeDecodeError:
            continue
    
    raise ValueError(f"无法识别文件编码: {csv_path}")


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """标准化列名，支持多种命名方式"""
    column_mapping = {
        'ts_code': ['ts_code', 'code', '股票代码', '代码', 'qmtcode', 'QMTCODE'],
        'name': ['name', '股票名称', '名称', 'stock_name', 'NAME'],
        'sw_level1': ['sw_level1', 'sw_l1', '申万一级行业', '一级行业', 'industry_l1', 'CLASS1', 'class1'],
        'sw_level2': ['sw_level2', 'sw_l2', '申万二级行业', '二级行业', 'industry_l2', 'CLASS2', 'class2'],
        'sw_level3': ['sw_level3', 'sw_l3', '申万三级行业', '三级行业', 'industry_l3', 'CLASS3', 'class3'],
        'concepts': ['concepts', 'concept', '概念', '概念板块', 'concept_tags', 'CONCEPTIONS', 'conceptions'],
        'area': ['area', '地区', '区域', 'province'],
        'market': ['market', '市场', 'exchange'],
        'list_date': ['list_date', '上市日期', 'listdate'],
    }
    
    rename_map = {}
    df_columns_lower = {col.lower(): col for col in df.columns}
    
    for standard_name, aliases in column_mapping.items():
        for alias in aliases:
            if alias.lower() in df_columns_lower:
                rename_map[df_columns_lower[alias.lower()]] = standard_name
                break
    
    df = df.rename(columns=rename_map)
    
    return df


def extract_and_load_data(df: pd.DataFrame, separator: str = None):
    """提取并加载数据到数据库"""
    db = get_db_manager()
    conn = db.get_connection()
    
    df = normalize_column_names(df)
    
    if 'ts_code' not in df.columns:
        raise ValueError("CSV 文件缺少必需字段: ts_code (股票代码)")
    
    all_concepts: Set[str] = set()
    concept_column = None
    for col in ['concepts', 'concept', '概念', '概念板块']:
        if col in df.columns:
            concept_column = col
            break
    
    if concept_column:
        for concept_str in df[concept_column]:
            all_concepts.update(parse_concepts(concept_str, separator))
        print(f"[INFO] 发现 {len(all_concepts)} 个唯一概念标签")
    
    if all_concepts:
        existing_concepts = conn.execute(
            text("SELECT concept_name FROM concept_dict")
        ).fetchall()
        existing_names = {row[0] for row in existing_concepts}

        new_concepts = all_concepts - existing_names
        if new_concepts:
            max_id_result = conn.execute(
                text("SELECT COALESCE(MAX(concept_id), 0) FROM concept_dict")
            ).fetchone()
            max_id = max_id_result[0] if max_id_result else 0

            for i, concept in enumerate(sorted(new_concepts), start=max_id + 1):
                conn.execute(
                    text("INSERT INTO concept_dict (concept_id, concept_name) VALUES (:p0, :p1)"),
                    {"p0": i, "p1": concept}
                )
            conn.commit()
            print(f"[OK] 插入 {len(new_concepts)} 个新概念")
    
    concept_map = {}
    if all_concepts:
        concept_map_result = conn.execute(
            text("SELECT concept_id, concept_name FROM concept_dict")
        ).fetchall()
        concept_map = {name: cid for cid, name in concept_map_result}
    
    stock_columns = ['ts_code']
    for col in ['name', 'area', 'market', 'list_date', 'sw_level1', 'sw_level2', 'sw_level3']:
        if col in df.columns:
            stock_columns.append(col)
    
    stock_info_df = df[stock_columns].copy()
    stock_info_df = stock_info_df.drop_duplicates(subset=['ts_code'], keep='first')
    
    db.upsert_dataframe(stock_info_df, 'stock_info', ['ts_code'])
    print(f"[OK] 更新 {len(stock_info_df)} 条股票信息")
    
    if concept_column:
        stock_concept_records = []
        for _, row in df.iterrows():
            ts_code = row['ts_code']
            concepts = parse_concepts(row.get(concept_column, ''), separator)
            for concept in concepts:
                if concept in concept_map:
                    stock_concept_records.append({
                        'ts_code': ts_code,
                        'concept_id': concept_map[concept]
                    })
        
        if stock_concept_records:
            stock_concept_df = pd.DataFrame(stock_concept_records)
            stock_concept_df = stock_concept_df.drop_duplicates()
            
            # 在单个事务内执行 DELETE + INSERT：若INSERT失败，DELETE自动回滚
            try:
                conn.execute(text("DELETE FROM stock_concept"))
                db.insert_dataframe(stock_concept_df, 'stock_concept')
                conn.commit()
                print(f"[OK] 建立 {len(stock_concept_df)} 条股票-概念关联")
            except Exception:
                conn.rollback()
                raise
        else:
            conn.execute(text("DELETE FROM stock_concept"))
            conn.commit()
            print(f"[INFO] 概念列为空，已清空股票-概念关联表")


def verify_data():
    """验证数据一致性"""
    db = get_db_manager()
    conn = db.get_connection()
    
    print("\n" + "=" * 50)
    print("数据验证")
    print("=" * 50)
    
    stock_count = conn.execute(text("SELECT COUNT(*) FROM stock_info")).fetchone()[0]
    concept_count = conn.execute(text("SELECT COUNT(*) FROM concept_dict")).fetchone()[0]
    relation_count = conn.execute(text("SELECT COUNT(*) FROM stock_concept")).fetchone()[0]
    
    print(f"股票数量: {stock_count}")
    print(f"概念数量: {concept_count}")
    print(f"关联数量: {relation_count}")
    
    orphan_concepts = conn.execute(text("""
        SELECT COUNT(*) FROM concept_dict c
        WHERE NOT EXISTS (SELECT 1 FROM stock_concept sc WHERE sc.concept_id = c.concept_id)
    """)).fetchone()[0]

    stocks_without_concepts = conn.execute(text("""
        SELECT COUNT(*) FROM stock_info si
        WHERE NOT EXISTS (SELECT 1 FROM stock_concept sc WHERE sc.ts_code = si.ts_code)
    """)).fetchone()[0]
    
    print(f"孤立概念: {orphan_concepts}")
    print(f"无概念股票: {stocks_without_concepts}")
    
    if concept_count > 0:
        top_concepts = conn.execute(text("""
            SELECT cd.concept_name, COUNT(sc.ts_code) as stock_count
            FROM concept_dict cd
            JOIN stock_concept sc ON cd.concept_id = sc.concept_id
            GROUP BY cd.concept_id, cd.concept_name
            ORDER BY stock_count DESC
            LIMIT 10
        """)).fetchall()
        
        print("\n热门概念 TOP 10:")
        for name, count in top_concepts:
            print(f"  {name}: {count} 只股票")
    
    if stock_count > 0:
        sw1_stats = conn.execute(text("""
            SELECT sw_level1, COUNT(*) as cnt
            FROM stock_info
            WHERE sw_level1 IS NOT NULL AND sw_level1 != ''
            GROUP BY sw_level1
            ORDER BY cnt DESC
            LIMIT 10
        """)).fetchall()
        
        if sw1_stats:
            print("\n申万一级行业分布 TOP 10:")
            for name, count in sw1_stats:
                print(f"  {name}: {count} 只股票")
    
    print("=" * 50)
    
    return stock_count > 0


def update_meta_file(csv_path: Path, df: pd.DataFrame):
    """更新元信息文件"""
    EXTERNAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    db = get_db_manager()
    conn = db.get_connection()
    
    concept_count = conn.execute(text("SELECT COUNT(*) FROM concept_dict")).fetchone()[0]
    
    meta = {
        "version": "1.0.0",
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "申万行业分类 + 概念标签",
        "records": len(df),
        "columns": list(df.columns),
        "concept_count": concept_count,
        "checksum": calculate_checksum(csv_path),
        "notes": f"概念标签使用 {DEFAULT_CONCEPT_SEPARATOR} 分隔"
    }
    
    with open(META_PATH, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    
    print(f"[OK] 元信息已更新: {META_PATH}")


def main():
    parser = argparse.ArgumentParser(
        description="ALLSYMBOL.csv 数据加载",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python load_allsymbol.py                          # 从默认路径加载
    python load_allsymbol.py --path ./my_data.csv     # 指定文件路径
    python load_allsymbol.py --separator ","          # 使用逗号作为分隔符
    python load_allsymbol.py --verify                 # 仅验证数据
        """
    )
    parser.add_argument("--path", type=str, help="CSV 文件路径")
    parser.add_argument("--verify", action="store_true", help="仅验证数据")
    parser.add_argument("--separator", type=str, default=None,
                        help="概念分隔符 (默认: 自动检测)")
    parser.add_argument("--no-meta", action="store_true", help="不更新元信息文件")
    args = parser.parse_args()
    
    print("=" * 50)
    print("ALLSYMBOL 数据加载工具")
    print(f"时间: {now_beijing().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("[ERROR] DATABASE_URL 环境变量未设置")
        print("请在 .env 文件中配置 DATABASE_URL")
        return
    
    init_db_manager(db_url)
    
    if args.verify:
        verify_data()
        return
    
    csv_path = Path(args.path) if args.path else ALLSYMBOL_PATH
    
    if not csv_path.exists():
        print(f"[ERROR] 文件不存在: {csv_path}")
        print("\n请将 ALLSYMBOL.csv 放置到以下位置之一:")
        print(f"  1. {EXTERNAL_DATA_DIR}/ALLSYMBOL.csv")
        print(f"  2. 使用 --path 参数指定路径")
        print("\nCSV 文件应包含以下字段:")
        print("  - ts_code: 股票代码 (必需)")
        print("  - name: 股票名称")
        print("  - sw_level1/sw_level2/sw_level3: 申万行业分类")
        print("  - concepts: 概念标签 (多个概念用分隔符分开)")
        return
    
    print(f"[INFO] 加载文件: {csv_path}")
    if args.separator:
        print(f"[INFO] 概念分隔符: '{args.separator}'")
    else:
        print(f"[INFO] 概念分隔符: 自动检测")
    
    df = load_csv_data(csv_path)
    extract_and_load_data(df, args.separator)
    verify_data()
    
    if not args.no_meta:
        update_meta_file(csv_path, df)
    
    print("\n[ALL DONE] 数据加载完成")


if __name__ == "__main__":
    main()
