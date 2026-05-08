#!/bin/bash
# ATMstockMarket 快速数据更新脚本（简化版）
# 用法: ./scripts/quick_update.sh

set -e

cd /Users/atmbrandnew/Desktop/SOLOProject/ATMstockMarket

echo "========================================"
echo "  ATMstockMarket 数据更新"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"

# 1. 停止 Web 服务器
echo ""
echo "[1/3] 停止 Web 服务器..."
pkill -f uvicorn || true
sleep 2
echo "  ✓ 完成"

# 2. 运行数据获取
echo ""
echo "[2/3] 获取数据..."
PYTHONPATH=$(pwd) /Library/Developer/CommandLineTools/usr/bin/python3 -u src/data_fetchers/tushare_fetcher.py
PYTHONPATH=$(pwd) /Library/Developer/CommandLineTools/usr/bin/python3 -u src/data_fetchers/akshare_fetcher.py
echo "  ✓ 完成"

# 3. 重启 Web 服务器
echo ""
echo "[3/3] 重启 Web 服务器..."
PYTHONPATH=$(pwd) /Library/Developer/CommandLineTools/usr/bin/python3 -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000 &
sleep 3
echo "  ✓ 完成"
echo "  访问: http://localhost:8000"

echo ""
echo "========================================"
echo "  全部完成！"
echo "========================================"
