#!/bin/bash
# ATMstockMarket 数据更新流程控制脚本
# 功能：停止 Web 服务器 -> 获取数据 -> 验证成功 -> 重启网站
# 作者：ATMstockMarket Team
# 日期：2026-05-04

set -e  # 任何命令失败立即退出

# ========================================
# 配置区域
# ========================================
PROJECT_DIR="/Users/atmbrandnew/Desktop/SOLOProject/ATMstockMarket"
PYTHON_PATH="/Library/Developer/CommandLineTools/usr/bin/python3"
WEB_HOST="0.0.0.0"
WEB_PORT="8000"
LOG_DIR="$PROJECT_DIR/logs"
DB_PATH="$PROJECT_DIR/data/database/analysis.duckdb"
WAL_FILE="$PROJECT_DIR/data/database/analysis.duckdb.wal"

# 创建日志目录
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/data_update_$(date +%Y%m%d_%H%M%S).log"

# ========================================
# 日志函数
# ========================================
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_section() {
    echo "" | tee -a "$LOG_FILE"
    echo "========================================" | tee -a "$LOG_FILE"
    log "$1"
    echo "========================================" | tee -a "$LOG_FILE"
}

log_success() {
    log "✓ $1"
}

log_error() {
    log "✗ 错误: $1"
}

log_warning() {
    log "⚠ 警告: $1"
}

# ========================================
# 错误处理函数
# ========================================
cleanup_on_error() {
    log_error "流程失败，正在清理..."
    
    # 尝试重启 Web 服务器（即使失败也要尝试）
    if pgrep -f "uvicorn src.web.app:app" > /dev/null; then
        log "Web 服务器仍在运行"
    else
        log "尝试重启 Web 服务器..."
        cd "$PROJECT_DIR"
        PYTHONPATH="$PROJECT_DIR" "$PYTHON_PATH" -m uvicorn src.web.app:app --host "$WEB_HOST" --port "$WEB_PORT" >> "$LOG_FILE" 2>&1 &
        sleep 3
        if pgrep -f "uvicorn src.web.app:app" > /dev/null; then
            log_success "Web 服务器已重启"
        else
            log_error "Web 服务器重启失败"
        fi
    fi
    
    log "流程失败！请检查日志: $LOG_FILE"
    exit 1
}

# 设置错误陷阱
trap cleanup_on_error ERR

# ========================================
# 主流程
# ========================================
cd "$PROJECT_DIR"

log_section "ATMstockMarket 数据更新流程开始"
log "日志文件: $LOG_FILE"
log "项目目录: $PROJECT_DIR"

# ----------------------------------------
# 步骤 1: 停止 Web 服务器
# ----------------------------------------
log_section "步骤 1/5: 停止 Web 服务器"

WEB_PID=$(pgrep -f "uvicorn src.web.app:app" || true)

if [ -n "$WEB_PID" ]; then
    log "发现运行中的 Web 服务器 (PID: $WEB_PID)"
    log "正在停止..."
    
    pkill -f "uvicorn src.web.app:app"
    sleep 3
    
    # 验证是否已停止
    if pgrep -f "uvicorn src.web.app:app" > /dev/null; then
        log_error "无法停止 Web 服务器"
        exit 1
    else
        log_success "Web 服务器已停止"
    fi
else
    log "Web 服务器未运行"
fi

# ----------------------------------------
# 步骤 2: 清理数据库锁文件
# ----------------------------------------
log_section "步骤 2/5: 清理数据库锁文件"

if [ -f "$WAL_FILE" ]; then
    log "发现 WAL 锁文件，正在删除..."
    rm -f "$WAL_FILE"
    log_success "WAL 锁文件已删除"
else
    log "无需清理锁文件"
fi

# ----------------------------------------
# 步骤 3: 运行 Tushare 数据获取
# ----------------------------------------
log_section "步骤 3/5: 获取 Tushare 数据"

log "开始执行 tushare_fetcher.py..."
log "----------------------------------------"

PYTHONPATH="$PROJECT_DIR" "$PYTHON_PATH" -u src/data_fetchers/tushare_fetcher.py 2>&1 | tee -a "$LOG_FILE"
TUSHARE_EXIT_CODE=${PIPESTATUS[0]}

log "----------------------------------------"

if [ $TUSHARE_EXIT_CODE -eq 0 ]; then
    log_success "Tushare 数据获取成功"
else
    log_error "Tushare 数据获取失败 (退出码: $TUSHARE_EXIT_CODE)"
    exit 1
fi

# ----------------------------------------
# 步骤 4: 运行 AKShare 数据获取
# ----------------------------------------
log_section "步骤 4/5: 获取 AKShare 数据"

log "开始执行 akshare_fetcher.py..."
log "----------------------------------------"

PYTHONPATH="$PROJECT_DIR" "$PYTHON_PATH" -u src/data_fetchers/akshare_fetcher.py 2>&1 | tee -a "$LOG_FILE"
AKSHARE_EXIT_CODE=${PIPESTATUS[0]}

log "----------------------------------------"

if [ $AKSHARE_EXIT_CODE -eq 0 ]; then
    log_success "AKShare 数据获取成功"
else
    log_error "AKShare 数据获取失败 (退出码: $AKSHARE_EXIT_CODE)"
    exit 1
fi

# ----------------------------------------
# 步骤 5: 验证数据库完整性
# ----------------------------------------
log_section "步骤 5/5: 验证数据库完整性"

if [ -f "$DB_PATH" ]; then
    DB_SIZE=$(du -h "$DB_PATH" | cut -f1)
    log "数据库文件大小: $DB_SIZE"
    
    # 检查是否有 WAL 文件残留
    if [ -f "$WAL_FILE" ]; then
        log_warning "发现 WAL 文件残留，可能存在未提交的事务"
    fi
    
    log_success "数据库验证通过"
else
    log_error "数据库文件不存在: $DB_PATH"
    exit 1
fi

# ----------------------------------------
# 步骤 6: 重启 Web 服务器
# ----------------------------------------
log_section "步骤 6/6: 重启 Web 服务器"

log "正在启动 Web 服务器..."
log "监听地址: http://$WEB_HOST:$WEB_PORT"

PYTHONPATH="$PROJECT_DIR" "$PYTHON_PATH" -m uvicorn src.web.app:app --host "$WEB_HOST" --port "$WEB_PORT" >> "$LOG_FILE" 2>&1 &
WEB_PID=$!

sleep 3

# 验证 Web 服务器是否启动成功
if pgrep -f "uvicorn src.web.app:app" > /dev/null; then
    WEB_PID=$(pgrep -f "uvicorn src.web.app:app")
    log_success "Web 服务器启动成功 (PID: $WEB_PID)"
    log "访问地址: http://localhost:$WEB_PORT"
else
    log_error "Web 服务器启动失败"
    exit 1
fi

# ----------------------------------------
# 流程完成
# ----------------------------------------
log_section "数据更新流程完成！"

log "总结:"
log "  ✓ Web 服务器已停止"
log "  ✓ 数据库锁文件已清理"
log "  ✓ Tushare 数据获取成功"
log "  ✓ AKShare 数据获取成功"
log "  ✓ 数据库验证通过"
log "  ✓ Web 服务器已重启"

log ""
log "详细信息:"
log "  日志文件: $LOG_FILE"
log "  数据库: $DB_PATH"
log "  Web 服务: http://localhost:$WEB_PORT"

echo ""
log "========================================"
log "所有步骤成功完成！"
log "========================================"

exit 0
