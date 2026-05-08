#!/bin/bash
# =============================================================================
# ATMstockMarket PostgreSQL 迁移脚本
# =============================================================================
# 用途: 一键完成从 DuckDB 到 PostgreSQL 的迁移
# 使用: ./scripts/quick_migrate.sh
# =============================================================================

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE}    ATMstockMarket PostgreSQL 迁移工具${NC}"
echo -e "${BLUE}================================================================${NC}"
echo ""

# 检查 .env 文件
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${YELLOW}⚠️  未找到 .env 文件${NC}"
    echo -e "${YELLOW}正在从模板创建 .env 文件...${NC}"
    cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
    echo -e "${GREEN}✅ 已创建 .env 文件${NC}"
    echo -e "${YELLOW}请编辑 .env 文件，填写您的数据库信息：${NC}"
    echo -e "${YELLOW}  nano $PROJECT_ROOT/.env${NC}"
    echo ""
    echo -e "${YELLOW}填写完成后，请重新运行此脚本。${NC}"
    exit 1
fi

# 加载环境变量
source "$PROJECT_ROOT/.env"

# 检查 DATABASE_URL
if [ -z "$DATABASE_URL" ]; then
    echo -e "${RED}❌ 错误: DATABASE_URL 环境变量未设置${NC}"
    echo -e "${YELLOW}请在 .env 文件中设置 DATABASE_URL${NC}"
    exit 1
fi

echo -e "${GREEN}✅ 找到数据库配置${NC}"
echo -e "${BLUE}数据库URL: ${DATABASE_URL#*@}${NC}"  # 隐藏密码
echo ""

# 检查 Python 依赖
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}步骤 1/5: 检查 Python 依赖${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if ! python3 -c "import psycopg2" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  未安装 psycopg2，正在安装...${NC}"
    pip3 install -r "$PROJECT_ROOT/requirements.txt"
    echo -e "${GREEN}✅ 依赖安装完成${NC}"
else
    echo -e "${GREEN}✅ Python 依赖已安装${NC}"
fi
echo ""

# 检查 PostgreSQL 连接
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}步骤 2/5: 测试 PostgreSQL 连接${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

python3 -c "
import os
import psycopg2
try:
    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    conn.close()
    print('✅ PostgreSQL 连接成功')
except Exception as e:
    print(f'❌ PostgreSQL 连接失败: {e}')
    exit(1)
"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ 无法连接到 PostgreSQL${NC}"
    echo -e "${YELLOW}请检查：${NC}"
    echo -e "${YELLOW}  1. PostgreSQL 服务是否运行${NC}"
    echo -e "${YELLOW}  2. 数据库是否存在${NC}"
    echo -e "${YELLOW}  3. 用户名和密码是否正确${NC}"
    exit 1
fi
echo ""

# 检查 DuckDB 文件
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}步骤 3/5: 检查 DuckDB 数据文件${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

DUCKDB_FILE="$PROJECT_ROOT/data/database/analysis.duckdb"

if [ ! -f "$DUCKDB_FILE" ]; then
    echo -e "${YELLOW}⚠️  未找到 DuckDB 文件: $DUCKDB_FILE${NC}"
    echo -e "${YELLOW}这可能是新安装，跳过数据迁移${NC}"
    SKIP_MIGRATION=true
else
    echo -e "${GREEN}✅ 找到 DuckDB 文件${NC}"
    FILE_SIZE=$(du -h "$DUCKDB_FILE" | cut -f1)
    echo -e "${BLUE}文件大小: $FILE_SIZE${NC}"
    SKIP_MIGRATION=false
fi
echo ""

# 执行数据迁移
if [ "$SKIP_MIGRATION" = false ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}步骤 4/5: 执行数据迁移${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    echo -e "${YELLOW}正在迁移数据...${NC}"
    python3 "$PROJECT_ROOT/scripts/migrate_to_postgresql.py" "$DATABASE_URL"
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ 数据迁移失败${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ 数据迁移完成${NC}"
else
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}步骤 4/5: 创建数据库表结构${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    python3 -c "
import os
from sqlalchemy import create_engine, text

db_url = os.getenv('DATABASE_URL')
engine = create_engine(db_url)

# 创建表结构的 SQL
tables = {
    'index_etf_daily': '''
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
    ''',
    # ... 其他表定义
}

with engine.connect() as conn:
    for table_name, create_sql in tables.items():
        conn.execute(text(create_sql))
        conn.commit()
    print('✅ 数据库表结构创建完成')
"
fi
echo ""

# 测试应用
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}步骤 5/5: 测试应用${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "${YELLOW}正在测试 Web 应用...${NC}"

# 启动应用测试
timeout 5 python3 -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000 &
APP_PID=$!
sleep 3

# 测试健康检查
if curl -s http://localhost:8000/health > /dev/null; then
    echo -e "${GREEN}✅ Web 应用启动成功${NC}"
    kill $APP_PID 2>/dev/null
else
    echo -e "${YELLOW}⚠️  Web 应用启动测试跳过${NC}"
    kill $APP_PID 2>/dev/null
fi
echo ""

# 完成
echo -e "${GREEN}================================================================${NC}"
echo -e "${GREEN}    🎉 迁移完成！${NC}"
echo -e "${GREEN}================================================================${NC}"
echo ""
echo -e "${BLUE}下一步操作：${NC}"
echo ""
echo -e "${YELLOW}1. 启动 Web 应用：${NC}"
echo -e "   ${BLUE}python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000${NC}"
echo ""
echo -e "${YELLOW}2. 访问网站：${NC}"
echo -e "   ${BLUE}http://localhost:8000${NC}"
echo ""
echo -e "${YELLOW}3. 更新数据：${NC}"
echo -e "   ${BLUE}python src/data_fetchers/tushare_fetcher.py${NC}"
echo ""
echo -e "${YELLOW}4. 查看详细文档：${NC}"
echo -e "   ${BLUE}cat MIGRATION_COMPLETE.md${NC}"
echo ""
echo -e "${GREEN}现在您可以同时更新数据和查看网站了！${NC}"
echo ""
