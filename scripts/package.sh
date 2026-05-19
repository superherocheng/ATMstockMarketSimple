#!/usr/bin/env bash
# ATMstockMarket 项目打包脚本
# 自动：删除 token → 打包 zip → 恢复 token
set -e

cd "$(dirname "$0")/.."
PROJECT_NAME="ATMstockMarket"

echo "========================================="
echo "  开始打包 $PROJECT_NAME"
echo "========================================="

# 1. 检查 config.py 是否有真实 token
CONFIG_FILE="src/core/config.py"
if [ ! -f "$CONFIG_FILE" ]; then
    # 如果不存在，检查config目录
    CONFIG_FILE="config/config.py"
fi

if [ ! -f "$CONFIG_FILE" ]; then
    echo "⚠️  配置文件不存在，跳过token处理"
    BACKUP_TOKEN=""
else
    BACKUP_TOKEN=$(grep 'TUSHARE_TOKEN =' "$CONFIG_FILE" | sed -E 's/.*TUSHARE_TOKEN = "(.*)".*/\1/')
    if [ "$BACKUP_TOKEN" = "你的Token" ] || [ -z "$BACKUP_TOKEN" ]; then
        echo "⚠️  config.py 已经是模板，无需替换"
    else
        echo "✅ 保存当前 token"
    fi

    # 2. 替换为模板内容
    sed -i.bak -E 's/TUSHARE_TOKEN = ".*"/TUSHARE_TOKEN = "你的Token"/' "$CONFIG_FILE"
    rm -f "$CONFIG_FILE.bak"
fi

# 3. 打包（使用项目根目录，向上一级避免文件夹嵌套问题）
cd ..
zip -r "${PROJECT_NAME}.zip" "${PROJECT_NAME}/" \
  -x "${PROJECT_NAME}/data/database/*.db" \
  -x "${PROJECT_NAME}/data/database/*.duckdb" \
  -x "${PROJECT_NAME}/data/database/*.duckdb-wal" \
  -x "${PROJECT_NAME}/data/database/*.duckdb-wal" \
  -x "${PROJECT_NAME}/.venv/*" \
  -x "${PROJECT_NAME}/venv/*" \
  -x "${PROJECT_NAME}/__pycache__/*" \
  -x "${PROJECT_NAME}/**/__pycache__/*" \
  -x "${PROJECT_NAME}/.DS_Store" \
  -x "${PROJECT_NAME}/**/.DS_Store" \
  -x "${PROJECT_NAME}/.git/*" \
  -x "${PROJECT_NAME}/.gitignore" \
  -x "${PROJECT_NAME}/.github_token" \
  -x "${PROJECT_NAME}/web.log" \
  -x "${PROJECT_NAME}/*.pid" \
  -x "${PROJECT_NAME}/release.sh" \
  -x "${PROJECT_NAME}/release.py" \
  -x "${PROJECT_NAME}/upload-github.sh"

# 4. 恢复真实 token
cd "$PROJECT_NAME"
if [ -f "$CONFIG_FILE" ] && [ "$BACKUP_TOKEN" != "你的Token" ] && [ -n "$BACKUP_TOKEN" ]; then
    sed -i.bak -E "s/TUSHARE_TOKEN = \".*\"/TUSHARE_TOKEN = \"$BACKUP_TOKEN\"/" "$CONFIG_FILE"
    rm -f "$CONFIG_FILE.bak"
    echo "✅ Token 已恢复"
fi

echo "========================================="
echo "  📦 打包成功！"
echo "  位置：$(dirname "$(pwd)")/${PROJECT_NAME}.zip"
echo "========================================="
