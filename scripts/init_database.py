"""
数据库初始化脚本
==================
一键初始化所有数据表和外部数据

用法:
    python init_database.py              # 完整初始化
    python init_database.py --schema     # 仅初始化 Schema
    python init_database.py --external   # 仅加载外部数据
    python init_database.py --verify     # 验证数据库状态
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

from src.core.trading_calendar import now_beijing


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

ENV_FILE = PROJECT_ROOT / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
EXTERNAL_DATA_DIR = PROJECT_ROOT / "data" / "external"
ALLSYMBOL_PATH = EXTERNAL_DATA_DIR / "ALLSYMBOL.csv"


def run_script(script_name: str, args: str = "") -> bool:
    """运行指定的 Python 脚本"""
    script_path = SCRIPT_DIR / script_name
    if not script_path.exists():
        print(f"[ERROR] 脚本不存在: {script_path}")
        return False
    
    cmd = [sys.executable, str(script_path)] + args.split()
    print(f"\n{'=' * 50}")
    print(f">>> 执行: {script_name} {args}")
    print("=" * 50)
    
    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    
    if result.returncode != 0:
        print(f"[ERROR] {script_name} 执行失败 (退出码: {result.returncode})")
        return False
    
    return True


def check_external_data() -> bool:
    """检查外部数据文件是否存在"""
    if not EXTERNAL_DATA_DIR.exists():
        print(f"[WARN] 外部数据目录不存在: {EXTERNAL_DATA_DIR}")
        print("       正在创建...")
        EXTERNAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
        return False
    
    if not ALLSYMBOL_PATH.exists():
        print(f"[WARN] 外部数据文件不存在: {ALLSYMBOL_PATH}")
        print("\n请将 ALLSYMBOL.csv 放置到以下位置:")
        print(f"  {EXTERNAL_DATA_DIR}/ALLSYMBOL.csv")
        print("\n文件格式要求:")
        print("  - 编码: UTF-8")
        print("  - 必需字段: ts_code, name")
        print("  - 可选字段: sw_level1, sw_level2, sw_level3, concepts")
        print("  - 概念分隔符: | (竖线)")
        return False
    
    return True


def init_schema() -> bool:
    """初始化数据库 Schema"""
    try:
        from src.data_fetchers.tushare_fetcher import init_db
        print("\n" + "=" * 50)
        print(">>> 初始化数据库 Schema")
        print("=" * 50)
        init_db()
        print("[OK] Schema 初始化完成")
        return True
    except Exception as e:
        print(f"[ERROR] Schema 初始化失败: {e}")
        return False


def load_external_data() -> bool:
    """加载外部数据"""
    if not check_external_data():
        print("[SKIP] 跳过外部数据加载")
        return True
    
    return run_script("load_allsymbol.py")


def verify_database() -> bool:
    """验证数据库状态"""
    print("\n" + "=" * 50)
    print("数据库状态验证")
    print("=" * 50)
    
    schema_ok = True
    
    from src.core.db_manager_postgresql import init_db_manager, get_db_manager

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("[ERROR] DATABASE_URL not set. Check .env file.")
        sys.exit(1)

    init_db_manager(db_url)
    db = get_db_manager()
    conn = db.get_connection()

    tables = [
        "index_etf_daily", "sector_etf_daily", "etf_share",
        "stock_daily", "stock_basic", "stock_daily_basic",
        "stock_fina_indicator", "stock_info", "concept_dict", "stock_concept"
    ]

    print("\n表记录统计:")
    for table in tables:
        try:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).fetchone()[0]
            status = "OK" if count > 0 else "--"
            print(f"  {status} {table}: {count:,} 条")
        except Exception:
            print(f"  X {table}: 不存在")

    external_ok = True
    try:
        stock_info_count = conn.execute(text("SELECT COUNT(*) FROM stock_info")).fetchone()[0]
        concept_count = conn.execute(text("SELECT COUNT(*) FROM concept_dict")).fetchone()[0]

        if stock_info_count == 0:
            print("\n[WARN] stock_info 表为空，请加载外部数据:")
            print("       python load_allsymbol.py")
            external_ok = False
    except Exception:
        external_ok = False

    return schema_ok and external_ok


def main():
    parser = argparse.ArgumentParser(
        description="数据库初始化",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python init_database.py              # 完整初始化
    python init_database.py --schema     # 仅初始化 Schema
    python init_database.py --external   # 仅加载外部数据
    python init_database.py --verify     # 验证数据库状态
        """
    )
    parser.add_argument("--schema", action="store_true", help="仅初始化 Schema")
    parser.add_argument("--external", action="store_true", help="仅加载外部数据")
    parser.add_argument("--verify", action="store_true", help="验证数据库状态")
    args = parser.parse_args()
    
    print("=" * 50)
    print("ATMstockMarket 数据库初始化工具")
    print(f"时间: {now_beijing().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    if args.verify:
        verify_database()
        return
    
    if args.schema:
        init_schema()
        return
    
    if args.external:
        load_external_data()
        return
    
    print("\n[Step 1/2] 初始化数据库 Schema...")
    if not init_schema():
        print("\n[FAILED] Schema 初始化失败")
        return
    
    print("\n[Step 2/2] 加载外部数据...")
    if not load_external_data():
        print("\n[WARN] 外部数据加载失败或跳过")
    
    print("\n[验证] 检查数据库状态...")
    verify_database()
    
    print("\n" + "=" * 50)
    print("[ALL DONE] 数据库初始化完成")
    print("=" * 50)
    print("\n下一步:")
    print("  1. 配置 Tushare Token: 设置环境变量 TUSHARE_TOKEN 或编辑 src/core/config.py")
    print("  2. 启动 Web 服务: python -m uvicorn src.web.app:app --port 8000")
    print("  3. 通过 Web 界面获取行情数据")


if __name__ == "__main__":
    main()
