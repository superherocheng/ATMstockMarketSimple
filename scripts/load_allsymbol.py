"""
ALLSYMBOL.csv 数据加载脚本入口
================================
调用 external_loader 模块加载外部股票分类数据

用法:
    python load_allsymbol.py                    # 从默认路径加载
    python load_allsymbol.py --path /path/to/   # 指定数据路径
    python load_allsymbol.py --verify           # 验证数据一致性
    python load_allsymbol.py --separator "|"    # 指定概念分隔符
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_fetchers.external_loader import main

if __name__ == "__main__":
    main()
