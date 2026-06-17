#!/bin/bash
# ════════════════════════════════════════════════════════════
#  end.command — 停止 ATMstockMarket 前后端服务
#  · uvicorn 应用 — 停止(按 PID 文件,缺失则按端口兜底)
#  · Redis(brew 服务) — 停止
#  · PostgreSQL — 保持运行(按你的选择,避免影响其他数据库)
#  双击即可运行。
# ════════════════════════════════════════════════════════════
set -u
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
cd "$(dirname "$0")" || exit 1

G='\033[0;32m'; Y='\033[0;33m'; B='\033[0;36m'; N='\033[0m'
msg(){ printf "%b\n" "$1"; }
PORT="${APP_PORT:-5656}"

msg "\n${B}═══ ATMstockMarket 停止 ═══${N}\n"

# ── 1. 停止 uvicorn ──
STOPPED=0
if [ -f .uvicorn.pid ]; then
  PID="$(cat .uvicorn.pid 2>/dev/null)"
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    kill "$PID" 2>/dev/null
    for _ in 1 2 3 4 5; do kill -0 "$PID" 2>/dev/null || break; sleep 0.5; done
    kill -0 "$PID" 2>/dev/null && kill -9 "$PID" 2>/dev/null
    msg "${G}✓${N} 已停止 uvicorn (pid $PID)"
    STOPPED=1
  else
    msg "${Y}!${N} PID 文件里的进程已不在 (pid ${PID:-?})"
  fi
  rm -f .uvicorn.pid
fi
# 兜底:按端口找(若没用 start.command 启动,或 PID 文件丢失)
PORT_PID="$(lsof -ti tcp:"$PORT" 2>/dev/null)"
if [ -n "$PORT_PID" ]; then
  kill $PORT_PID 2>/dev/null
  for _ in 1 2 3 4 5; do lsof -ti tcp:"$PORT" >/dev/null 2>&1 || break; sleep 0.5; done
  msg "${G}✓${N} 已按端口 $PORT 停止残留进程 (pid $PORT_PID)"
  STOPPED=1
elif [ "$STOPPED" -eq 0 ]; then
  msg "${Y}!${N} 未发现运行中的 uvicorn"
fi

# ── 2. 停止 Redis ──
if brew services list 2>/dev/null | awk '{print $1,$2}' | grep -q '^redis started'; then
  brew services stop redis >/dev/null 2>&1
  msg "${G}✓${N} 已停止 Redis"
else
  msg "${Y}!${N} Redis 未在运行"
fi

# ── 3. 确认端口释放 ──
if lsof -ti tcp:"$PORT" >/dev/null 2>&1; then
  msg "${Y}!${N} 端口 $PORT 仍被占用,可能需手动处理 (lsof -i :$PORT)"
else
  msg "${G}✓${N} 端口 $PORT 已释放"
fi

msg "\n${G}✓${N} 全部停止完成。${Y}PostgreSQL 保持运行${N}(按你的选择未动)。\n"
msg "${G}═══ 停止完成 ═══${N}"
read -t 15 -r -p "按回车关闭窗口(15秒自动关闭)..." 2>/dev/null || true
exit 0
