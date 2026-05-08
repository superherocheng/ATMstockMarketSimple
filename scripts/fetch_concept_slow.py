"""
获取股票概念数据（带延迟）
============================
从 Tushare 获取概念分类和成分股数据
添加延迟避免API限流
"""
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

ENV_FILE = PROJECT_ROOT / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

import pandas as pd
from sqlalchemy import text
from config.config import get_pro
from src.core.db_manager_postgresql import init_db_manager, get_db_manager, close_db_manager
from src.core.trading_calendar import now_beijing
import os


def fetch_concept_data():
    """获取概念分类和成分股数据（带延迟）"""
    print("=" * 60)
    print("概念数据获取工具（带延迟版）")
    print(f"时间: {now_beijing().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable not set")
    
    init_db_manager(db_url)
    db = get_db_manager()
    conn = db.get_connection()
    
    try:
        pro = get_pro()
        
        print("\n[1/3] 获取概念分类列表...")
        concept_df = pro.concept()
        
        if concept_df is None or len(concept_df) == 0:
            print("[ERROR] 未获取到概念数据")
            return
        
        print(f"[OK] 获取到 {len(concept_df)} 个概念")
        
        print("\n[2/3] 清空旧数据...")
        conn.execute(text("DELETE FROM stock_concept"))
        conn.execute(text("DELETE FROM concept_dict"))
        conn.commit()
        print("[OK] 旧数据已清空")
        
        print("\n[3/3] 获取概念成分股（每分钟最多380次请求）...")
        all_relations = []
        success_count = 0
        fail_count = 0
        
        for idx, row in concept_df.iterrows():
            concept_code = row['code']
            concept_name = row['name']
            
            try:
                detail_df = pro.concept_detail(id=concept_code)
                if detail_df is not None and len(detail_df) > 0:
                    for _, stock_row in detail_df.iterrows():
                        all_relations.append({
                            'concept_code': concept_code,
                            'concept_name': concept_name,
                            'ts_code': stock_row['ts_code']
                        })
                    success_count += 1
                else:
                    fail_count += 1
                
                if (idx + 1) % 10 == 0:
                    print(f"  进度: {idx+1}/{len(concept_df)} | 成功: {success_count} | 失败: {fail_count} | 关系数: {len(all_relations)}")
                
                time.sleep(0.16)
                
            except Exception as e:
                fail_count += 1
                if "频率超限" in str(e):
                    print(f"\n[WARN] API限流，等待60秒...")
                    time.sleep(60)
                    try:
                        detail_df = pro.concept_detail(id=concept_code)
                        if detail_df is not None and len(detail_df) > 0:
                            for _, stock_row in detail_df.iterrows():
                                all_relations.append({
                                    'concept_code': concept_code,
                                    'concept_name': concept_name,
                                    'ts_code': stock_row['ts_code']
                                })
                            success_count += 1
                    except Exception as e2:
                        print(f"[ERROR] 重试失败: {concept_name} - {e2}")
                continue
        
        print(f"\n[OK] 成功: {success_count}, 失败: {fail_count}, 总关系数: {len(all_relations)}")
        
        print("\n[4/4] 更新数据库...")
        
        concept_dict_df = concept_df[['code', 'name']].copy()
        concept_dict_df.columns = ['concept_id', 'concept_name']
        concept_dict_df['concept_category'] = None
        
        db.insert_dataframe(concept_dict_df, 'concept_dict', if_exists='append')
        print(f"[OK] 插入 {len(concept_dict_df)} 条概念记录")
        
        if all_relations:
            relations_df = pd.DataFrame(all_relations)
            
            concept_id_map = dict(zip(concept_dict_df['concept_name'], 
                                     concept_dict_df['concept_id']))
            
            relations_df['concept_id'] = relations_df['concept_name'].map(concept_id_map)
            relations_df = relations_df[['ts_code', 'concept_id']]
            
            db.insert_dataframe(relations_df, 'stock_concept', if_exists='append')
            print(f"[OK] 插入 {len(relations_df)} 条股票-概念关系")
        
        print("\n" + "=" * 60)
        print("[ALL DONE] 概念数据获取完成！")
        print("=" * 60)
        
        verify_data(conn)
        
    finally:
        conn.close()
        close_db_manager()


def verify_data(conn):
    """验证数据"""
    print("\n数据验证:")
    print("-" * 60)
    
    concept_count = conn.execute(text("SELECT COUNT(*) FROM concept_dict")).fetchone()[0]
    relation_count = conn.execute(text("SELECT COUNT(*) FROM stock_concept")).fetchone()[0]
    
    print(f"概念数量: {concept_count}")
    print(f"股票-概念关系: {relation_count}")
    
    if concept_count > 0:
        print("\n热门概念 TOP 10:")
        top_concepts = conn.execute(text("""
            SELECT cd.concept_name, COUNT(sc.ts_code) as stock_count
            FROM concept_dict cd
            LEFT JOIN stock_concept sc ON cd.concept_id = sc.concept_id
            GROUP BY cd.concept_id, cd.concept_name
            ORDER BY stock_count DESC
            LIMIT 10
        """)).fetchall()
        
        for name, count in top_concepts:
            print(f"  {name}: {count} 只股票")


if __name__ == "__main__":
    fetch_concept_data()
