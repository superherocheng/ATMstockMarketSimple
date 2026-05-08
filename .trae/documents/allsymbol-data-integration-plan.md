# ALLSYMBOL.csv 数据集成实施计划

> **目标**: 将包含申万一级至三级分类和多概念标签的股票数据集成到 DuckDB 数据库，同时确保数据可移植性、版本控制兼容性和维护便捷性。

---

## 一、项目背景分析

### 1.1 现有架构

- **数据库**: DuckDB (`tushare-py/data/analysis.duckdb`)
- **连接管理**: `DuckDBConnectionManager` 单例模式，线程本地存储
- **现有表结构**:
  - `stock_basic`: 股票基础信息 (ts_code, name, industry, area, market, list_date)
  - `stock_daily`: 日线数据
  - `stock_daily_basic`: 每日估值
  - `stock_fina_indicator`: 财务指标
- **.gitignore**: 已排除 `*.db`, `*.csv`, `tushare-py/data/`

### 1.2 ALLSYMBOL.csv 数据特征（预期）

| 字段 | 类型 | 说明 |
|------|------|------|
| ts_code | VARCHAR | 股票代码 (主键) |
| name | VARCHAR | 股票名称 |
| sw_level1 | VARCHAR | 申万一级行业分类 |
| sw_level2 | VARCHAR | 申万二级行业分类 |
| sw_level3 | VARCHAR | 申万三级行业分类 |
| concepts | VARCHAR | 概念标签 (多值，分隔符分隔) |

**核心挑战**: `concepts` 字段包含多个概念标签，需要设计合理的存储和查询方案。

---

## 二、数据提取与数据库集成

### 2.1 DuckDB Schema 设计

#### 方案选择：概念标签关系表设计

**推荐方案**: 使用关联表存储多对多关系

```sql
-- 股票基础信息扩展表 (替代现有 stock_basic)
CREATE TABLE IF NOT EXISTS stock_info (
    ts_code VARCHAR PRIMARY KEY,
    name VARCHAR,
    area VARCHAR,
    market VARCHAR,
    list_date VARCHAR,
    sw_level1 VARCHAR,
    sw_level2 VARCHAR,
    sw_level3 VARCHAR,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 概念标签字典表
CREATE TABLE IF NOT EXISTS concept_dict (
    concept_id INTEGER PRIMARY KEY,
    concept_name VARCHAR UNIQUE NOT NULL,
    concept_category VARCHAR
);

-- 股票-概念关联表 (多对多)
CREATE TABLE IF NOT EXISTS stock_concept (
    ts_code VARCHAR,
    concept_id INTEGER,
    PRIMARY KEY (ts_code, concept_id),
    FOREIGN KEY (ts_code) REFERENCES stock_info(ts_code),
    FOREIGN KEY (concept_id) REFERENCES concept_dict(concept_id)
);

-- 创建索引优化查询
CREATE INDEX IF NOT EXISTS idx_stock_concept_code ON stock_concept(ts_code);
CREATE INDEX IF NOT EXISTS idx_stock_concept_id ON stock_concept(concept_id);
CREATE INDEX IF NOT EXISTS idx_stock_info_sw1 ON stock_info(sw_level1);
CREATE INDEX IF NOT EXISTS idx_stock_info_sw2 ON stock_info(sw_level2);
CREATE INDEX IF NOT EXISTS idx_stock_info_sw3 ON stock_info(sw_level3);
```

**优势**:
- 符合数据库范式设计
- 高效的概念标签查询 (按概念查股票、按股票查概念)
- 支持概念分类管理
- 避免字符串重复存储

#### 备选方案：JSON/ARRAY 存储

```sql
-- 使用 DuckDB 原生 ARRAY 类型
CREATE TABLE IF NOT EXISTS stock_info_v2 (
    ts_code VARCHAR PRIMARY KEY,
    name VARCHAR,
    sw_level1 VARCHAR,
    sw_level2 VARCHAR,
    sw_level3 VARCHAR,
    concepts VARCHAR[],  -- DuckDB ARRAY 类型
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**适用场景**: 概念标签仅用于展示，无需复杂查询。

### 2.2 数据提取脚本设计

**文件**: `tushare-py/load_allsymbol.py`

```python
"""
ALLSYMBOL.csv 数据加载脚本
===========================
将外部股票分类数据导入 DuckDB 数据库

用法:
    python load_allsymbol.py                    # 从默认路径加载
    python load_allsymbol.py --path /path/to/   # 指定数据路径
    python load_allsymbol.py --verify           # 验证数据一致性
"""
import argparse
import os
from pathlib import Path
from typing import Optional, List, Set

import pandas as pd
import duckdb

from db_manager import init_db_manager, get_db_manager
from trading_calendar import now_beijing


SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
EXTERNAL_DATA_DIR = SCRIPT_DIR / "external_data"
ALLSYMBOL_PATH = EXTERNAL_DATA_DIR / "ALLSYMBOL.csv"

CONCEPT_SEPARATOR = "|"  # 概念分隔符，根据实际文件调整


def parse_concepts(concept_str: str, separator: str = CONCEPT_SEPARATOR) -> List[str]:
    """解析概念字符串，返回概念列表"""
    if pd.isna(concept_str) or not concept_str:
        return []
    return [c.strip() for c in str(concept_str).split(separator) if c.strip()]


def init_schema():
    """初始化数据库 Schema"""
    db = get_db_manager()
    conn = db.get_connection()
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stock_info (
            ts_code VARCHAR PRIMARY KEY,
            name VARCHAR,
            area VARCHAR,
            market VARCHAR,
            list_date VARCHAR,
            sw_level1 VARCHAR,
            sw_level2 VARCHAR,
            sw_level3 VARCHAR,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS concept_dict (
            concept_id INTEGER PRIMARY KEY,
            concept_name VARCHAR UNIQUE NOT NULL,
            concept_category VARCHAR
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stock_concept (
            ts_code VARCHAR,
            concept_id INTEGER,
            PRIMARY KEY (ts_code, concept_id)
        )
    """)
    
    conn.execute("CREATE INDEX IF NOT EXISTS idx_stock_concept_code ON stock_concept(ts_code)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_stock_concept_id ON stock_concept(concept_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_stock_info_sw1 ON stock_info(sw_level1)")
    
    print("[OK] Schema 初始化完成")


def load_csv_data(csv_path: Path) -> pd.DataFrame:
    """加载 CSV 数据，自动检测编码"""
    encodings = ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']
    
    for encoding in encodings:
        try:
            df = pd.read_csv(csv_path, encoding=encoding)
            print(f"[OK] 成功加载 CSV ({encoding}): {len(df)} 行")
            return df
        except UnicodeDecodeError:
            continue
    
    raise ValueError(f"无法识别文件编码: {csv_path}")


def extract_and_load_data(df: pd.DataFrame):
    """提取并加载数据到数据库"""
    db = get_db_manager()
    conn = db.get_connection()
    
    # 1. 提取所有概念标签
    all_concepts: Set[str] = set()
    for concept_str in df.get('concepts', []):
        all_concepts.update(parse_concepts(concept_str))
    
    print(f"[INFO] 发现 {len(all_concepts)} 个唯一概念标签")
    
    # 2. 插入概念字典
    existing_concepts = conn.execute(
        "SELECT concept_name FROM concept_dict"
    ).fetchall()
    existing_names = {row[0] for row in existing_concepts}
    
    new_concepts = all_concepts - existing_names
    if new_concepts:
        concept_df = pd.DataFrame({
            'concept_name': list(new_concepts)
        })
        conn.execute("""
            INSERT INTO concept_dict (concept_name)
            SELECT concept_name FROM concept_df
        """)
        print(f"[OK] 插入 {len(new_concepts)} 个新概念")
    
    # 3. 构建概念名称到 ID 的映射
    concept_map = conn.execute(
        "SELECT concept_id, concept_name FROM concept_dict"
    ).fetchall()
    concept_name_to_id = {name: cid for cid, name in concept_map}
    
    # 4. 准备股票信息数据
    stock_info_df = df[['ts_code', 'name', 'sw_level1', 'sw_level2', 'sw_level3']].copy()
    if 'area' in df.columns:
        stock_info_df['area'] = df['area']
    if 'market' in df.columns:
        stock_info_df['market'] = df['market']
    if 'list_date' in df.columns:
        stock_info_df['list_date'] = df['list_date']
    
    # 5. Upsert 股票信息
    db.upsert_dataframe(stock_info_df, 'stock_info', ['ts_code'])
    print(f"[OK] 更新 {len(stock_info_df)} 条股票信息")
    
    # 6. 构建股票-概念关联
    stock_concept_records = []
    for _, row in df.iterrows():
        ts_code = row['ts_code']
        concepts = parse_concepts(row.get('concepts', ''))
        for concept in concepts:
            if concept in concept_name_to_id:
                stock_concept_records.append({
                    'ts_code': ts_code,
                    'concept_id': concept_name_to_id[concept]
                })
    
    if stock_concept_records:
        stock_concept_df = pd.DataFrame(stock_concept_records)
        # 删除旧关联
        conn.execute("DELETE FROM stock_concept")
        # 插入新关联
        db.insert_dataframe(stock_concept_df, 'stock_concept')
        print(f"[OK] 建立 {len(stock_concept_df)} 条股票-概念关联")


def verify_data():
    """验证数据一致性"""
    db = get_db_manager()
    conn = db.get_connection()
    
    stock_count = conn.execute("SELECT COUNT(*) FROM stock_info").fetchone()[0]
    concept_count = conn.execute("SELECT COUNT(*) FROM concept_dict").fetchone()[0]
    relation_count = conn.execute("SELECT COUNT(*) FROM stock_concept").fetchone()[0]
    
    print("\n=== 数据验证 ===")
    print(f"股票数量: {stock_count}")
    print(f"概念数量: {concept_count}")
    print(f"关联数量: {relation_count}")
    
    # 检查孤立记录
    orphan_concepts = conn.execute("""
        SELECT COUNT(*) FROM concept_dict c
        WHERE NOT EXISTS (SELECT 1 FROM stock_concept sc WHERE sc.concept_id = c.concept_id)
    """).fetchone()[0]
    
    print(f"孤立概念: {orphan_concepts}")
    
    return stock_count > 0 and concept_count > 0


def main():
    parser = argparse.ArgumentParser(description="ALLSYMBOL.csv 数据加载")
    parser.add_argument("--path", type=str, help="CSV 文件路径")
    parser.add_argument("--verify", action="store_true", help="仅验证数据")
    args = parser.parse_args()
    
    print("=" * 50)
    print("ALLSYMBOL 数据加载工具")
    print(f"时间: {now_beijing().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    init_db_manager(DATA_DIR / "analysis.duckdb")
    
    if args.verify:
        verify_data()
        return
    
    csv_path = Path(args.path) if args.path else ALLSYMBOL_PATH
    
    if not csv_path.exists():
        print(f"[ERROR] 文件不存在: {csv_path}")
        print("\n请将 ALLSYMBOL.csv 放置到以下位置之一:")
        print(f"  1. {EXTERNAL_DATA_DIR}/ALLSYMBOL.csv")
        print(f"  2. 使用 --path 参数指定路径")
        return
    
    init_schema()
    df = load_csv_data(csv_path)
    extract_and_load_data(df)
    verify_data()
    
    print("\n[ALL DONE] 数据加载完成")


if __name__ == "__main__":
    main()
```

### 2.3 性能优化策略

#### 2.3.1 批量插入优化

```python
def batch_insert_optimized(df: pd.DataFrame, table: str, batch_size: int = 10000):
    """批量插入优化"""
    db = get_db_manager()
    conn = db.get_connection()
    
    total = len(df)
    for i in range(0, total, batch_size):
        batch = df.iloc[i:i+batch_size]
        conn.execute(f"INSERT INTO {table} SELECT * FROM batch")
        
        if (i + batch_size) % 50000 == 0:
            print(f"  进度: {min(i+batch_size, total)}/{total}")
```

#### 2.3.2 查询性能基准

| 查询类型 | 预期数据量 | 目标响应时间 |
|---------|-----------|-------------|
| 按股票代码查询概念 | 1 条 | < 10ms |
| 按概念查询股票列表 | 50-500 条 | < 50ms |
| 按申万行业查询股票 | 50-200 条 | < 30ms |
| 全量概念统计 | 5000+ 条 | < 200ms |

---

## 三、项目结构与数据迁移策略

### 3.1 外部数据存储设计

#### 目录结构

```
ATMstockMarket/
├── tushare-py/
│   ├── data/                          # 运行时数据 (Git 忽略)
│   │   └── analysis.duckdb            # DuckDB 数据库
│   │
│   ├── external_data/                 # 外部数据源 (Git 跟踪)
│   │   ├── ALLSYMBOL.csv              # 股票分类数据
│   │   ├── ALLSYMBOL.meta.json        # 数据元信息
│   │   └── README.md                  # 数据说明文档
│   │
│   ├── load_allsymbol.py              # 数据加载脚本
│   └── sync_external_data.py          # 数据同步脚本
│
└── .gitignore
```

#### 数据元信息文件

**文件**: `tushare-py/external_data/ALLSYMBOL.meta.json`

```json
{
    "version": "1.0.0",
    "updated_at": "2026-05-03",
    "source": "申万行业分类 + 概念标签",
    "records": 5234,
    "columns": [
        "ts_code", "name", "sw_level1", "sw_level2", "sw_level3", "concepts"
    ],
    "concept_count": 285,
    "checksum": "sha256:abc123...",
    "notes": "概念标签使用 | 分隔"
}
```

### 3.2 数据格式选择

#### 推荐格式: Parquet + CSV 双格式

| 格式 | 用途 | 优势 |
|------|------|------|
| **CSV** | 人工查看/编辑 | 通用性强，易于调试 |
| **Parquet** | 高效加载 | 列式存储，压缩率高，加载快 |

**转换脚本**:

```python
def convert_to_parquet(csv_path: Path) -> Path:
    """将 CSV 转换为 Parquet 格式"""
    df = pd.read_csv(csv_path)
    parquet_path = csv_path.with_suffix('.parquet')
    df.to_parquet(parquet_path, compression='snappy')
    
    csv_size = csv_path.stat().st_size / 1024
    parquet_size = parquet_path.stat().st_size / 1024
    print(f"压缩率: {parquet_size/csv_size:.1%}")
    
    return parquet_path
```

### 3.3 自动加载机制

#### 方案 A: 应用启动时检查

**修改**: `web/app.py`

```python
def _ensure_external_data():
    """检查并加载外部数据"""
    db = get_db_manager()
    conn = db.get_connection()
    
    # 检查 stock_info 表是否存在数据
    count = conn.execute("SELECT COUNT(*) FROM stock_info").fetchone()[0]
    
    if count == 0:
        print("[INFO] 检测到股票分类数据为空，尝试加载外部数据...")
        csv_path = EXTERNAL_DATA_DIR / "ALLSYMBOL.csv"
        if csv_path.exists():
            import load_allsymbol
            load_allsymbol.init_schema()
            df = load_allsymbol.load_csv_data(csv_path)
            load_allsymbol.extract_and_load_data(df)
        else:
            print("[WARN] 未找到外部数据文件，请手动运行 load_allsymbol.py")
```

#### 方案 B: 独立初始化脚本

**文件**: `tushare-py/init_database.py`

```python
"""
数据库初始化脚本
==================
一键初始化所有数据表和外部数据

用法:
    python init_database.py
"""
import subprocess
import sys
from pathlib import Path

def main():
    scripts = [
        ("fetch_data.py", "--init"),
        ("load_allsymbol.py", ""),
    ]
    
    for script, args in scripts:
        print(f"\n>>> 执行: {script}")
        result = subprocess.run(
            [sys.executable, script] + args.split(),
            cwd=Path(__file__).parent
        )
        if result.returncode != 0:
            print(f"[ERROR] {script} 执行失败")
            return
    
    print("\n[OK] 数据库初始化完成")

if __name__ == "__main__":
    main()
```

### 3.4 迁移文档

**文件**: `tushare-py/external_data/README.md`

```markdown
# 外部数据说明

## 数据文件

| 文件 | 说明 | 更新频率 |
|------|------|---------|
| ALLSYMBOL.csv | 股票分类数据 (申万行业+概念标签) | 季度更新 |

## 数据加载

### 首次安装

\`\`\`bash
cd tushare-py
python load_allsymbol.py
\`\`\`

### 数据更新

1. 替换 `external_data/ALLSYMBOL.csv`
2. 运行 `python load_allsymbol.py`

## 数据格式

- 编码: UTF-8
- 分隔符: 逗号
- 概念分隔符: `|`

## 数据来源

- 申万行业分类: http://www.swsindex.com/
- 概念标签: 东方财富/同花顺
```

---

## 四、版本控制与 GitHub 兼容性

### 4.1 GitHub 存储限制

| 限制项 | 阈值 | 应对策略 |
|--------|------|---------|
| 单文件大小 | 100 MB | CSV/Parquet 通常 < 50 MB |
| 仓库总大小 | 建议 < 1 GB | 排除数据库文件 |
| 单次推送 | < 2 GB | 无影响 |

### 4.2 .gitignore 配置更新

**更新**: `.gitignore`

```gitignore
# Data - Runtime (不提交)
*.db
*.duckdb
*.sqlite
*.sqlite3
tushare-py/data/

# Data - External (提交)
# tushare-py/external_data/  # 此目录需要提交

# 但排除大型压缩包
*.zip
*.tar.gz
*.7z

# 排除 Parquet 文件 (可选，根据大小决定)
# *.parquet
```

### 4.3 数据同步策略

**单一数据源原则**: `external_data/ALLSYMBOL.csv` 是唯一数据源

```
┌─────────────────────┐
│  ALLSYMBOL.csv      │  ← 唯一数据源 (Git 跟踪)
│  (external_data/)   │
└──────────┬──────────┘
           │
           │ load_allsymbol.py
           ▼
┌─────────────────────┐
│  analysis.duckdb    │  ← 派生数据 (Git 忽略)
│  (data/)            │
└─────────────────────┘
```

### 4.4 Setup 文档更新

**更新**: `README.md`

```markdown
## 🚀 快速开始

### 1. 克隆项目

\`\`\`bash
git clone https://github.com/superherocheng/ATMstockMarket.git
cd ATMstockMarket
\`\`\`

### 2. 初始化数据库

\`\`\`bash
cd tushare-py

# 初始化 DuckDB 数据库
python fetch_data.py --init

# 加载股票分类数据
python load_allsymbol.py

# 获取行情数据
python fetch_data.py
\`\`\`

### 3. 配置 Token

\`\`\`bash
cp config.py.example config.py
# 编辑 config.py，填入 Tushare Token
\`\`\`

### 4. 启动服务

\`\`\`bash
cd ../web
python -m uvicorn app:app --host 0.0.0.0 --port 8000
\`\`\`
```

---

## 五、数据刷新与维护

### 5.1 数据更新流程

```python
"""
数据更新脚本
============
检查并更新外部数据

用法:
    python sync_external_data.py --check     # 检查更新
    python sync_external_data.py --update    # 执行更新
"""
import hashlib
import json
from pathlib import Path

def calculate_checksum(file_path: Path) -> str:
    """计算文件 SHA256 校验和"""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return f"sha256:{sha256.hexdigest()}"

def check_data_freshness():
    """检查数据新鲜度"""
    csv_path = EXTERNAL_DATA_DIR / "ALLSYMBOL.csv"
    meta_path = EXTERNAL_DATA_DIR / "ALLSYMBOL.meta.json"
    
    if not csv_path.exists():
        return False, "CSV 文件不存在"
    
    current_checksum = calculate_checksum(csv_path)
    
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)
        if meta.get('checksum') == current_checksum:
            return True, "数据已是最新"
        else:
            return False, "数据已变更，需要重新加载"
    
    return False, "元信息文件不存在"


def update_data():
    """更新数据库中的数据"""
    from load_allsymbol import load_csv_data, extract_and_load_data
    
    csv_path = EXTERNAL_DATA_DIR / "ALLSYMBOL.csv"
    df = load_csv_data(csv_path)
    extract_and_load_data(df)
    
    # 更新元信息
    meta = {
        "version": "1.0.0",
        "updated_at": datetime.now().strftime("%Y-%m-%d"),
        "records": len(df),
        "checksum": calculate_checksum(csv_path)
    }
    
    with open(EXTERNAL_DATA_DIR / "ALLSYMBOL.meta.json", 'w') as f:
        json.dump(meta, f, indent=2)
```

### 5.2 数据验证检查

```python
def validate_data_integrity():
    """验证数据完整性"""
    db = get_db_manager()
    conn = db.get_connection()
    
    checks = []
    
    # 1. 检查主键完整性
    duplicate_stocks = conn.execute("""
        SELECT ts_code, COUNT(*) as cnt 
        FROM stock_info 
        GROUP BY ts_code 
        HAVING cnt > 1
    """).fetchall()
    checks.append(("主键唯一性", len(duplicate_stocks) == 0))
    
    # 2. 检查外键完整性
    orphan_relations = conn.execute("""
        SELECT COUNT(*) FROM stock_concept sc
        WHERE NOT EXISTS (SELECT 1 FROM stock_info si WHERE si.ts_code = sc.ts_code)
    """).fetchone()[0]
    checks.append(("外键完整性", orphan_relations == 0))
    
    # 3. 检查空值
    null_sw1 = conn.execute(
        "SELECT COUNT(*) FROM stock_info WHERE sw_level1 IS NULL OR sw_level1 = ''"
    ).fetchone()[0]
    checks.append(("申万一级非空", null_sw1 == 0))
    
    # 4. 检查概念关联
    stocks_without_concepts = conn.execute("""
        SELECT COUNT(*) FROM stock_info si
        WHERE NOT EXISTS (SELECT 1 FROM stock_concept sc WHERE sc.ts_code = si.ts_code)
    """).fetchone()[0]
    checks.append(("概念关联完整性", stocks_without_concepts == 0))
    
    return checks
```

### 5.3 备份与恢复

```python
def backup_external_data(backup_dir: Path):
    """备份外部数据"""
    import shutil
    from datetime import datetime
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"ALLSYMBOL_{timestamp}.csv"
    
    shutil.copy2(EXTERNAL_DATA_DIR / "ALLSYMBOL.csv", backup_path)
    
    # 保留最近 5 个备份
    backups = sorted(backup_dir.glob("ALLSYMBOL_*.csv"))
    for old_backup in backups[:-5]:
        old_backup.unlink()
    
    print(f"[OK] 备份已保存: {backup_path}")


def restore_from_backup(backup_path: Path):
    """从备份恢复数据"""
    import shutil
    
    shutil.copy2(backup_path, EXTERNAL_DATA_DIR / "ALLSYMBOL.csv")
    print(f"[OK] 已从备份恢复: {backup_path}")
    
    # 重新加载数据
    from load_allsymbol import load_csv_data, extract_and_load_data
    df = load_csv_data(EXTERNAL_DATA_DIR / "ALLSYMBOL.csv")
    extract_and_load_data(df)
```

### 5.4 与动态数据的集成

```python
def merge_with_tushare_data():
    """将外部数据与 Tushare 动态数据合并"""
    db = get_db_manager()
    conn = db.get_connection()
    
    # 合并查询示例：获取某概念股票的实时行情
    query = """
        SELECT 
            si.ts_code,
            si.name,
            si.sw_level1,
            sd.close,
            sd.pct_chg,
            sd.total_mv
        FROM stock_info si
        JOIN stock_concept sc ON si.ts_code = sc.ts_code
        JOIN concept_dict cd ON sc.concept_id = cd.concept_id
        LEFT JOIN stock_daily sd ON si.ts_code = sd.ts_code
        WHERE cd.concept_name = ?
          AND sd.trade_date = (SELECT MAX(trade_date) FROM stock_daily)
        ORDER BY sd.total_mv DESC
    """
    
    return conn.execute(query, ['新能源车']).fetchdf()
```

---

## 六、实施步骤

### Phase 1: Schema 设计与验证 (Day 1)

- [ ] **Step 1.1**: 确认 ALLSYMBOL.csv 实际字段结构
- [ ] **Step 1.2**: 创建 `stock_info`, `concept_dict`, `stock_concept` 表
- [ ] **Step 1.3**: 编写 Schema 验证测试
- [ ] **Step 1.4**: 创建索引并测试查询性能

### Phase 2: 数据加载脚本 (Day 2)

- [ ] **Step 2.1**: 实现 `load_allsymbol.py` 核心逻辑
- [ ] **Step 2.2**: 处理概念分隔符解析
- [ ] **Step 2.3**: 实现增量更新逻辑
- [ ] **Step 2.4**: 添加数据验证检查

### Phase 3: 项目结构重组 (Day 3)

- [ ] **Step 3.1**: 创建 `external_data/` 目录
- [ ] **Step 3.2**: 编写数据元信息文件
- [ ] **Step 3.3**: 更新 `.gitignore`
- [ ] **Step 3.4**: 编写外部数据 README

### Phase 4: 自动化与集成 (Day 4)

- [ ] **Step 4.1**: 实现应用启动时自动检查
- [ ] **Step 4.2**: 创建 `init_database.py` 一键初始化脚本
- [ ] **Step 4.3**: 更新主 README.md
- [ ] **Step 4.4**: 编写数据同步脚本

### Phase 5: 测试与文档 (Day 5)

- [ ] **Step 5.1**: 端到端测试：从空库到完整数据
- [ ] **Step 5.2**: 性能基准测试
- [ ] **Step 5.3**: 编写用户文档
- [ ] **Step 5.4**: Code Review 与优化

---

## 七、技术推荐总结

### 7.1 数据库设计

| 决策点 | 推荐方案 | 理由 |
|--------|---------|------|
| 概念存储 | 关联表 (stock_concept) | 范式化，查询高效 |
| 主键设计 | (ts_code, concept_id) 复合主键 | 避免重复关联 |
| 索引策略 | ts_code, concept_id, sw_level1/2/3 | 覆盖常用查询 |

### 7.2 文件格式

| 决策点 | 推荐方案 | 理由 |
|--------|---------|------|
| 主数据格式 | CSV | 通用性强，易于版本控制 |
| 备选格式 | Parquet | 高效加载，压缩率高 |
| 元信息 | JSON | 结构化，易于解析 |

### 7.3 迁移策略

| 决策点 | 推荐方案 | 理由 |
|--------|---------|------|
| 数据位置 | `external_data/` | 与运行时数据分离 |
| 版本控制 | Git 跟踪 CSV | 变更可追溯 |
| 加载时机 | 首次启动/手动触发 | 灵活可控 |

### 7.4 维护策略

| 决策点 | 推荐方案 | 理由 |
|--------|---------|------|
| 数据更新 | 替换 CSV + 重载 | 简单直接 |
| 校验机制 | SHA256 校验和 | 检测变更 |
| 备份策略 | 保留最近 5 个版本 | 平衡空间与安全 |

---

## 八、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| CSV 文件过大 (>100MB) | GitHub 拒绝 | 使用 Git LFS 或压缩 |
| 概念分隔符冲突 | 数据解析错误 | 支持自定义分隔符 |
| 数据库锁定 | 并发写入失败 | 使用 WAL 模式 |
| 字段名不匹配 | 加载失败 | 字段映射配置 |

---

## 九、验收标准

- [ ] `python load_allsymbol.py` 成功加载 ALLSYMBOL.csv
- [ ] 数据库中 `stock_info` 表包含所有股票
- [ ] 概念查询响应时间 < 50ms
- [ ] `git status` 显示 `external_data/` 被跟踪
- [ ] `git status` 不显示 `data/*.duckdb`
- [ ] 新克隆项目后可一键初始化数据库

---

**文档版本**: 1.0
**创建时间**: 2026-05-03
**作者**: ATMstockMarket Team
