#!/bin/bash
set -e

cd /Users/atmbrandnew/Desktop/SOLOProject/ATMstockMarket
LOG_DIR="logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/data_update_$(date +%Y%m%d_%H%M%S).log"

echo "========================================" | tee -a "$LOG_FILE"
echo "ATMstockMarket 数据更新脚本" | tee -a "$LOG_FILE"
echo "开始时间: $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# 1. 检查并停止 Web 服务器
echo "" | tee -a "$LOG_FILE"
echo "[步骤 1/5] 检查 Web 服务器状态..." | tee -a "$LOG_FILE"
if pgrep -f "uvicorn src.web.app:app" > /dev/null; then
    echo "  发现运行中的 Web 服务器，正在停止..." | tee -a "$LOG_FILE"
    pkill -f "uvicorn src.web.app:app"
    sleep 3
    
    # 确认已停止
    if pgrep -f "uvicorn src.web.app:app" > /dev/null; then
        echo "  ✗ 无法停止 Web 服务器" | tee -a "$LOG_FILE"
        exit 1
    else
        echo "  ✓ Web 服务器已停止" | tee -a "$LOG_FILE"
    fi
else
    echo "  ✓ Web 服务器未运行" | tee -a "$LOG_FILE"
fi

# 2. 清理可能的锁文件
echo "" | tee -a "$LOG_FILE"
echo "[步骤 2/5] 清理数据库锁文件..." | tee -a "$LOG_FILE"
WAL_FILE="data/database/analysis.duckdb.wal"
if [ -f "$WAL_FILE" ]; then
    rm -f "$WAL_FILE"
    echo "  ✓ 已删除 WAL 锁文件" | tee -a "$LOG_FILE"
else
    echo "  ✓ 无需清理" | tee -a "$LOG_FILE"
fi

# 3. 运行 Tushare 数据获取
echo "" | tee -a "$LOG_FILE"
echo "[步骤 3/5] 获取 Tushare 数据..." | tee -a "$LOG_FILE"
echo "----------------------------------------" | tee -a "$LOG_FILE"
PYTHONPATH=$(pwd) /Library/Developer/CommandLineTools/usr/bin/python3 \
    src/data_fetchers/tushare_fetcher.py 2>&1 | tee -a "$LOG_FILE"
echo "----------------------------------------" | tee -a "$LOG_FILE"
echo "  ✓ Tushare 数据获取完成" | tee -a "$LOG_FILE"

# 4. 运行 AKShare 数据获取
echo "" | tee -a "$LOG_FILE"
echo "[步骤 4/5] 获取 AKShare 数据..." | tee -a "$LOG_FILE"
echo "----------------------------------------" | tee -a "$LOG_FILE"
PYTHONPATH=$(pwd) /Library/Developer/CommandLineTools/usr/bin/python3 \
    src/data_fetchers/akshare_fetcher.py 2>&1 | tee -a "$LOG_FILE"
echo "----------------------------------------" | tee -a "$LOG_FILE"
echo "  ✓ AKShare 数据获取完成" | tee -a "$LOG_FILE"

# 5. 重启 Web 服务器
echo "" | tee -a "$LOG_FILE"
echo "[步骤 5/5] 重启 Web 服务器..." | tee -a "$LOG_FILE"
PYTHONPATH=$(pwd) /Library/Developer/CommandLineTools/usr/bin/python3 \
    -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000 >> "$LOG_FILE" 2>&1 &

sleep 3

# 确认 Web 服务器已启动
if pgrep -f "uvicorn src.web.app:app" > /dev/null; then
    echo "  ✓ Web 服务器已启动 (PID: $(pgrep -f 'uvicorn src.web.app:app'))" | tee -a "$LOG_FILE"
    echo "  访问地址: http://localhost:8000" | tee -a "$LOG_FILE"
else
    echo "  ✗ Web 服务器启动失败，请检查日志: $LOG_FILE" | tee -a "$LOG_FILE"
    exit 1
fi

echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "数据更新完成！" | tee -a "$LOG_FILE"
echo "结束时间: $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOG_FILE"
echo "日志文件: $LOG_FILE" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
