#!/usr/bin/env bash
# ATMstockMarket 跨平台安装脚本
# 用法: bash setup.sh
#
# 支持: macOS / Linux / Windows (Git Bash / WSL)

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================="
echo "  ATMstockMarket 安装脚本"
echo "========================================="

# 检测 Python
detect_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        echo -e "${RED}[错误] 未找到 Python。请安装 Python 3.9+${NC}"
        echo "  macOS:  brew install python@3.11"
        echo "  Ubuntu: sudo apt install python3 python3-venv python3-pip"
        echo "  Windows: 从 https://python.org 下载安装"
        exit 1
    fi

    PY_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PY_MAJOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.major)")
    PY_MINOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.minor)")

    if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]); then
        echo -e "${RED}[错误] Python 版本过低: $PY_VERSION, 需要 3.9+${NC}"
        exit 1
    fi

    echo -e "${GREEN}[OK] Python $PY_VERSION ($PYTHON_CMD)${NC}"
}

# 创建虚拟环境
create_venv() {
    if [ -d ".venv" ]; then
        echo -e "${YELLOW}[跳过] 虚拟环境已存在 (.venv/)${NC}"
        return
    fi

    echo "[1/3] 创建虚拟环境..."
    $PYTHON_CMD -m venv .venv

    # 激活虚拟环境
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    elif [ -f ".venv/Scripts/activate" ]; then
        source .venv/Scripts/activate
    else
        echo -e "${RED}[错误] 无法激活虚拟环境${NC}"
        exit 1
    fi

    echo -e "${GREEN}[OK] 虚拟环境已创建${NC}"
}

# 安装依赖
install_deps() {
    echo "[2/3] 安装依赖..."
    pip install --upgrade pip --quiet
    pip install -e . --quiet
    echo -e "${GREEN}[OK] 依赖安装完成${NC}"
}

# 初始化数据库
init_db() {
    echo "[3/3] 初始化数据库..."
    $PYTHON_CMD scripts/init_database.py --schema 2>/dev/null || echo -e "${YELLOW}[跳过] 数据库初始化${NC}"
    echo -e "${GREEN}[OK] 数据库初始化完成${NC}"
}

# 打印使用说明
print_usage() {
    echo ""
    echo "========================================="
    echo -e "${GREEN}  安装完成！${NC}"
    echo "========================================="
    echo ""
    echo "使用方式:"
    echo ""
    echo "  1. 激活虚拟环境:"
    if [ -f ".venv/bin/activate" ]; then
        echo "     source .venv/bin/activate"
    else
        echo "     .venv\\Scripts\\activate  (Windows)"
    fi
    echo ""
    echo "  2. 配置 Tushare Token:"
    echo "     export TUSHARE_TOKEN='你的Token'"
    echo "     或编辑 src/core/config.py 文件"
    echo "     获取地址: https://tushare.pro/register"
    echo ""
    echo "  3. 获取数据:"
    echo "     python scripts/init_database.py        # 初始化数据库"
    echo "     python src/data_fetchers/tushare_fetcher.py          # 全量获取"
    echo "     python src/data_fetchers/tushare_fetcher.py --etf    # 仅 ETF"
    echo "     python src/data_fetchers/tushare_fetcher.py --stocks # 仅个股"
    echo "     python src/data_fetchers/akshare_fetcher.py          # AKShare 数据"
    echo ""
    echo "  4. 启动 Web 服务:"
    echo "     python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000 --reload"
    echo ""
    echo "  5. 浏览器打开: http://localhost:8000"
    echo ""
    echo "  手机/iPad 访问: http://<电脑IP>:8000"
    echo "  (确保设备在同一局域网)"
    echo "========================================="
}

# 主流程
cd "$(dirname "$0")"

detect_python
create_venv

# 如果虚拟环境刚创建，已被激活；如果已存在，需要手动激活
if [ -f ".venv/bin/activate" ] && [ -z "$VIRTUAL_ENV" ]; then
    source .venv/bin/activate
elif [ -f ".venv/Scripts/activate" ] && [ -z "$VIRTUAL_ENV" ]; then
    source .venv/Scripts/activate
fi

install_deps
init_db
print_usage
