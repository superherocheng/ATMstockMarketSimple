"""
外部数据同步脚本
==================
检查并同步外部数据，提供备份和恢复功能

用法:
    python sync_external_data.py --check        # 检查数据新鲜度
    python sync_external_data.py --update       # 更新数据库
    python sync_external_data.py --backup       # 备份外部数据
    python sync_external_data.py --restore FILE # 从备份恢复
    python sync_external_data.py --validate     # 验证数据完整性
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from sqlalchemy import text

from src.core.trading_calendar import now_beijing

ENV_FILE = PROJECT_ROOT / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
EXTERNAL_DATA_DIR = PROJECT_ROOT / "data" / "external"
BACKUP_DIR = EXTERNAL_DATA_DIR / "backups"
ALLSYMBOL_PATH = EXTERNAL_DATA_DIR / "ALLSYMBOL.csv"
META_PATH = EXTERNAL_DATA_DIR / "ALLSYMBOL.meta.json"

MAX_BACKUPS = 5


def calculate_checksum(file_path: Path) -> str:
    """计算文件 SHA256 校验和"""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return f"sha256:{sha256.hexdigest()}"


def check_data_freshness() -> tuple:
    """检查数据新鲜度"""
    print("\n" + "=" * 50)
    print("数据新鲜度检查")
    print("=" * 50)
    
    if not ALLSYMBOL_PATH.exists():
        return False, "CSV 文件不存在"
    
    current_checksum = calculate_checksum(ALLSYMBOL_PATH)
    file_size = ALLSYMBOL_PATH.stat().st_size
    file_mtime = datetime.fromtimestamp(ALLSYMBOL_PATH.stat().st_mtime)
    
    print(f"\n文件信息:")
    print(f"  路径: {ALLSYMBOL_PATH}")
    print(f"  大小: {file_size / 1024:.1f} KB")
    print(f"  修改时间: {file_mtime.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  校验和: {current_checksum[:20]}...")
    
    if META_PATH.exists():
        with open(META_PATH, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        
        stored_checksum = meta.get('checksum', '')
        stored_time = meta.get('updated_at', '')
        stored_records = meta.get('records', 0)
        
        print(f"\n元信息:")
        print(f"  更新时间: {stored_time}")
        print(f"  记录数: {stored_records}")
        print(f"  校验和: {stored_checksum[:20] if stored_checksum else 'N/A'}...")
        
        if current_checksum == stored_checksum:
            print("\n[OK] 数据已是最新，无需更新")
            return True, "数据已是最新"
        else:
            print("\n[WARN] 数据已变更，需要重新加载到数据库")
            return False, "数据已变更"
    else:
        print("\n[WARN] 元信息文件不存在")
        return False, "元信息文件不存在"


def update_database():
    """更新数据库中的数据"""
    print("\n" + "=" * 50)
    print("更新数据库")
    print("=" * 50)
    
    if not ALLSYMBOL_PATH.exists():
        print(f"[ERROR] CSV 文件不存在: {ALLSYMBOL_PATH}")
        return False
    
    import subprocess
    import sys
    
    cmd = [sys.executable, str(SCRIPT_DIR / "load_allsymbol.py")]
    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    
    if result.returncode == 0:
        print("\n[OK] 数据库更新成功")
        return True
    else:
        print("\n[ERROR] 数据库更新失败")
        return False


def backup_data():
    """备份外部数据"""
    print("\n" + "=" * 50)
    print("备份外部数据")
    print("=" * 50)
    
    if not ALLSYMBOL_PATH.exists():
        print(f"[ERROR] CSV 文件不存在: {ALLSYMBOL_PATH}")
        return False
    
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_csv = BACKUP_DIR / f"ALLSYMBOL_{timestamp}.csv"
    backup_meta = BACKUP_DIR / f"ALLSYMBOL_{timestamp}.meta.json"
    
    shutil.copy2(ALLSYMBOL_PATH, backup_csv)
    
    if META_PATH.exists():
        shutil.copy2(META_PATH, backup_meta)
    
    print(f"[OK] 备份已创建:")
    print(f"  {backup_csv}")
    if backup_meta.exists():
        print(f"  {backup_meta}")
    
    backups = sorted(BACKUP_DIR.glob("ALLSYMBOL_*.csv"))
    if len(backups) > MAX_BACKUPS:
        print(f"\n清理旧备份 (保留最近 {MAX_BACKUPS} 个):")
        for old_backup in backups[:-MAX_BACKUPS]:
            old_meta = old_backup.with_suffix('.meta.json')
            print(f"  删除: {old_backup.name}")
            old_backup.unlink()
            if old_meta.exists():
                old_meta.unlink()
    
    return True


def restore_data(backup_file: str):
    """从备份恢复数据"""
    print("\n" + "=" * 50)
    print("从备份恢复数据")
    print("=" * 50)
    
    backup_path = Path(backup_file)
    
    if not backup_path.exists():
        print(f"[ERROR] 备份文件不存在: {backup_path}")
        return False
    
    if not backup_path.name.startswith("ALLSYMBOL_"):
        print(f"[ERROR] 无效的备份文件名: {backup_path.name}")
        print("备份文件名应以 ALLSYMBOL_ 开头")
        return False
    
    shutil.copy2(backup_path, ALLSYMBOL_PATH)
    print(f"[OK] 已从备份恢复: {backup_path}")
    
    backup_meta = backup_path.with_suffix('.meta.json')
    if backup_meta.exists():
        shutil.copy2(backup_meta, META_PATH)
        print(f"[OK] 元信息已恢复: {backup_meta}")
    
    print("\n[INFO] 请运行以下命令更新数据库:")
    print("  python sync_external_data.py --update")
    
    return True


def validate_data_integrity():
    """验证数据完整性"""
    print("\n" + "=" * 50)
    print("数据完整性验证")
    print("=" * 50)

    from src.core.db_manager_postgresql import init_db_manager, get_db_manager

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("[ERROR] DATABASE_URL not set. Check .env file.")
        return False

    init_db_manager(db_url)
    db = get_db_manager()
    conn = db.get_connection()

    checks = []

    print("\n检查项:")

    try:
        duplicate_stocks = conn.execute(text("""
            SELECT ts_code, COUNT(*) as cnt
            FROM stock_info
            GROUP BY ts_code
            HAVING cnt > 1
        """)).fetchall()
        status = "OK" if len(duplicate_stocks) == 0 else "X"
        print(f"  {status} 主键唯一性: {len(duplicate_stocks)} 个重复")
        checks.append(("主键唯一性", len(duplicate_stocks) == 0))
    except Exception as e:
        print(f"  X 主键唯一性: 检查失败 - {e}")
        checks.append(("主键唯一性", False))

    try:
        orphan_relations = conn.execute(text("""
            SELECT COUNT(*) FROM stock_concept sc
            WHERE NOT EXISTS (SELECT 1 FROM stock_info si WHERE si.ts_code = sc.ts_code)
        """)).fetchone()[0]
        status = "OK" if orphan_relations == 0 else "X"
        print(f"  {status} 外键完整性: {orphan_relations} 个孤立关联")
        checks.append(("外键完整性", orphan_relations == 0))
    except Exception as e:
        print(f"  X 外键完整性: 检查失败 - {e}")
        checks.append(("外键完整性", False))

    try:
        null_sw1 = conn.execute(text(
            "SELECT COUNT(*) FROM stock_info WHERE sw_level1 IS NULL OR sw_level1 = ''"
        )).fetchone()[0]
        total_stocks = conn.execute(text("SELECT COUNT(*) FROM stock_info")).fetchone()[0]
        coverage = (total_stocks - null_sw1) / total_stocks * 100 if total_stocks > 0 else 0
        status = "OK" if null_sw1 == 0 else "--"
        print(f"  {status} 申万一级非空: {null_sw1} 个空值 (覆盖率: {coverage:.1f}%)")
        checks.append(("申万一级非空", null_sw1 == 0))
    except Exception as e:
        print(f"  X 申万一级非空: 检查失败 - {e}")
        checks.append(("申万一级非空", False))

    try:
        stocks_without_concepts = conn.execute(text("""
            SELECT COUNT(*) FROM stock_info si
            WHERE NOT EXISTS (SELECT 1 FROM stock_concept sc WHERE sc.ts_code = si.ts_code)
        """)).fetchone()[0]
        total_stocks = conn.execute(text("SELECT COUNT(*) FROM stock_info")).fetchone()[0]
        coverage = (total_stocks - stocks_without_concepts) / total_stocks * 100 if total_stocks > 0 else 0
        status = "OK" if stocks_without_concepts == 0 else "--"
        print(f"  {status} 概念关联完整性: {stocks_without_concepts} 个无概念 (覆盖率: {coverage:.1f}%)")
        checks.append(("概念关联完整性", stocks_without_concepts == 0))
    except Exception as e:
        print(f"  X 概念关联完整性: 检查失败 - {e}")
        checks.append(("概念关联完整性", False))

    print("\n" + "=" * 50)
    all_passed = all(check[1] for check in checks)
    if all_passed:
        print("[OK] 所有检查通过")
    else:
        print("[WARN] 部分检查未通过")

    return all_passed


def list_backups():
    """列出所有备份"""
    print("\n" + "=" * 50)
    print("备份列表")
    print("=" * 50)
    
    if not BACKUP_DIR.exists():
        print("无备份")
        return
    
    backups = sorted(BACKUP_DIR.glob("ALLSYMBOL_*.csv"), reverse=True)
    
    if not backups:
        print("无备份")
        return
    
    print(f"\n找到 {len(backups)} 个备份:\n")
    for backup in backups:
        stat = backup.stat()
        size = stat.st_size / 1024
        mtime = datetime.fromtimestamp(stat.st_mtime)
        print(f"  {backup.name}")
        print(f"    大小: {size:.1f} KB")
        print(f"    时间: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="外部数据同步工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python sync_external_data.py --check        # 检查数据新鲜度
    python sync_external_data.py --update       # 更新数据库
    python sync_external_data.py --backup       # 备份外部数据
    python sync_external_data.py --restore ALLSYMBOL_20260503_120000.csv
    python sync_external_data.py --validate     # 验证数据完整性
    python sync_external_data.py --list         # 列出所有备份
        """
    )
    parser.add_argument("--check", action="store_true", help="检查数据新鲜度")
    parser.add_argument("--update", action="store_true", help="更新数据库")
    parser.add_argument("--backup", action="store_true", help="备份外部数据")
    parser.add_argument("--restore", type=str, help="从指定备份恢复")
    parser.add_argument("--validate", action="store_true", help="验证数据完整性")
    parser.add_argument("--list", action="store_true", help="列出所有备份")
    args = parser.parse_args()
    
    print("=" * 50)
    print("外部数据同步工具")
    print(f"时间: {now_beijing().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    if args.check:
        check_data_freshness()
    elif args.update:
        update_database()
    elif args.backup:
        backup_data()
    elif args.restore:
        restore_data(args.restore)
    elif args.validate:
        validate_data_integrity()
    elif args.list:
        list_backups()
    else:
        check_data_freshness()
        print("\n使用 --help 查看更多选项")


if __name__ == "__main__":
    main()
