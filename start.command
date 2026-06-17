#!/bin/bash
# ════════════════════════════════════════════════════════════
#  start.command — 启动 ATMstockMarket 前后端服务
#  · Redis(brew 服务) — 若未运行则启动
#  · uvicorn 应用    — 后台启动,端口 5656
#  · PostgreSQL      — brew 常驻,本脚本不动(避免影响其他数据库)
#  双击即可运行;日志: logs/uvicorn.log   停止: end.command
# ════════════════════════════════════════════════════════════
set -u
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
cd "$(dirname "$0")" || exit 1

G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; B='\033[0;36m'; N='\033[0m'
msg(){ printf "%b\n" "$1"; }

PORT="${APP_PORT:-5656}"

# 选择安装了 uvicorn/fastapi 的 Python
# (本机 homebrew python3.14 无依赖,需用 /usr/bin/python3 即系统 3.9)
PYTHON=""
for cand in /usr/bin/python3 python3; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import uvicorn, fastapi' >/dev/null 2>&1; then
    PYTHON="$cand"; break
  fi
done
if [ -z "$PYTHON" ]; then
  msg "${R}✗${N} 未找到安装了 uvicorn/fastapi 的 python3!"
  msg "   请运行: /usr/bin/python3 -m pip install --user uvicorn fastapi pandas scipy sqlalchemy"
  read -t 20 -r -p "按回车关闭..." 2>/dev/null || true
  exit 1
fi
msg "${G}✓${N} Python: $("$PYTHON" -c 'import sys; print(sys.version.split()[0])' 2>/dev/null) ($PYTHON)"

msg "\n${B}═══ ATMstockMarket 启动 ═══${N}\n"

# ── 1. PostgreSQL(仅检查,不管理) ──
if pg_isready -h localhost -p 5432 >/dev/null 2>&1; then
  msg "${G}✓${N} PostgreSQL 已就绪 (5432)"
else
  msg "${R}✗${N} PostgreSQL 未响应! 请先启动: brew services start postgresql@15"
  msg "   (本脚本按你的选择不动 PostgreSQL)"
fi

# ── 2. Redis ──
if brew services list 2>/dev/null | awk '{print $1,$2}' | grep -q '^redis started'; then
  msg "${G}✓${N} Redis 已在运行"
else
  msg "${Y}→${N} 启动 Redis..."
  brew services start redis >/dev/null 2>&1 && sleep 1
fi
if redis-cli ping 2>/dev/null | grep -q PONG; then
  msg "${G}✓${N} Redis 就绪 (6379)"
else
  msg "${Y}!${N} Redis 暂未就绪,缓存将回退到内存(不阻断启动)"
fi

# ── 3. 加载环境变量 ──
if [ -f .env ]; then
  set -a; . ./.env; set +a
  msg "${G}✓${N} 已加载 .env"
else
  export DATABASE_URL="${DATABASE_URL:-postgresql://atmbrandnew@localhost:5432/atm_stock_market}"
  msg "${Y}!${N} 未找到 .env,使用默认 DATABASE_URL"
fi

# ── 4. 端口占用检查 ──
if lsof -ti tcp:"$PORT" >/dev/null 2>&1; then
  msg "${Y}!${N} 端口 $PORT 已被占用 — 服务可能已在运行。"
  msg "    如需重启,请先双击 ${B}end.command${N}。"
  msg "\n${G}→${N} 访问: http://localhost:$PORT/rotation"
  read -t 20 -r -p "按回车关闭窗口(20秒自动关闭)..." 2>/dev/null || true
  exit 0
fi

# ── 5. 启动 uvicorn(后台) ──
mkdir -p logs
msg "${Y}→${N} 启动 uvicorn (端口 $PORT)..."
nohup "$PYTHON" -m uvicorn src.web.app:app --host 127.0.0.1 --port "$PORT" \
    --log-level info > "logs/uvicorn.log" 2>&1 &
APP_PID=$!
echo "$APP_PID" > .uvicorn.pid
disown "$APP_PID" 2>/dev/null || true

# ── 6. 等待健康检查 ──
for i in $(seq 1 30); do
  if curl -sf -o /dev/null "http://127.0.0.1:$PORT/health" 2>/dev/null; then
    msg "${G}✓${N} 服务就绪! (pid $APP_PID)\n"
    msg "   ${B}首页${N}      : http://localhost:$PORT"
    msg "   ${B}轮动策略${N}  : http://localhost:$PORT/rotation"
    msg "   ${B}投资建议${N}  : http://localhost:$PORT/analysis/investment-recommendation"
    msg "\n   日志: tail -f logs/uvicorn.log   |   停止: 双击 end.command"
    msg "\n${G}═══ 启动完成 ═══${N}"
    read -t 20 -r -p "按回车关闭窗口(20秒自动关闭,服务继续后台运行)..." 2>/dev/null || true
    exit 0
  fi
  sleep 1
done

msg "\n${R}✗${N} 启动超时。请查看日志: logs/uvicorn.log"
tail -n 20 logs/uvicorn.log 2>/dev/null
read -t 30 -r -p "按回车关闭..." 2>/dev/null || true
exit 1
