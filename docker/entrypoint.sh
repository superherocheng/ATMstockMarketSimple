#!/bin/bash
set -e

# ──────────────────────────────────────────────────
# ATMstockMarket Docker Entrypoint
# ──────────────────────────────────────────────────
# 1. Waits for PostgreSQL to be ready
# 2. Runs Alembic database migrations
# 3. Starts the uvicorn application
# ──────────────────────────────────────────────────

if [ -t 1 ]; then
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    NC='\033[0m'
else
    GREEN=''; YELLOW=''; RED=''; NC=''
fi

echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}  ATMstockMarket Docker Entrypoint${NC}"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"

# ── Step 1: Wait for PostgreSQL ──
DB_HOST=$(echo "$DATABASE_URL" | sed -E 's/.*@([^:/]+).*/\1/')
DB_PORT=$(echo "$DATABASE_URL" | sed -E 's/.*:([0-9]+)\/.*/\1/')
DB_PORT=${DB_PORT:-5432}

echo -e "${YELLOW}[1/3]${NC} Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."

for i in $(seq 1 30); do
    if python -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('${DB_HOST}', ${DB_PORT})); s.close()" 2>/dev/null; then
        echo -e "${GREEN}  ✓ PostgreSQL is ready${NC}"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo -e "${RED}  ✗ PostgreSQL not reachable after 30 attempts, continuing...${NC}"
    else
        echo "  Waiting... ($i/30)"
        sleep 2
    fi
done

# ── Step 2: Run database migrations ──
echo -e "${YELLOW}[2/3]${NC} Running Alembic database migrations..."

if alembic upgrade head 2>&1; then
    echo -e "${GREEN}  ✓ Database migrations completed${NC}"
else
    echo -e "${RED}  ⚠ Migration failed, continuing anyway...${NC}"
fi

# ── Step 3: Start application ──
echo -e "${YELLOW}[3/3]${NC} Starting uvicorn application..."
echo -e "${GREEN}═══════════════════════════════════════════${NC}"

exec "$@"
