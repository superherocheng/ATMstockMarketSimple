#!/usr/bin/env python3
"""清除 BARRA 分析缓存"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
ENV_FILE = PROJECT_ROOT / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

from src.core.db_manager_postgresql import init_db_manager, get_db_manager
from sqlalchemy import text


def main():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("[ERROR] DATABASE_URL not set. Check .env file.")
        sys.exit(1)

    init_db_manager(db_url)
    conn = get_db_manager().get_connection()

    result = conn.execute(text("DELETE FROM precomputed_cache WHERE cache_key LIKE 'barra_%'"))
    conn.commit()
    print(f"[OK] 已清除 {result.rowcount} 条 BARRA 缓存")
    print("[INFO] 请重启 Web 服务以刷新内存缓存")


if __name__ == "__main__":
    main()
