# ── Stage 1: build the React SPA (served by the backend via spa_fallback) ──
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# VITE_API_TOKEN baked at build so the deployed SPA can do authenticated
# write-ops (refresh data). Passed as a build arg from the runtime API_TOKEN
# via docker-compose. Empty -> read-only build (no write-ops from the SPA).
ARG VITE_API_TOKEN=""
RUN VITE_API_TOKEN="${VITE_API_TOKEN}" npm run build

# ── Stage 2: Python backend ──
FROM python:3.12-slim
LABEL maintainer="ATMstockMarket Team"

WORKDIR /app

# ── Runtime system dependencies ──
# libpq5: runtime library for psycopg2 (used via psycopg2-binary wheels)
# curl:   health check probes
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies (stable layer, Docker caches this) ──
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Entrypoint script ──
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# ── Application code ──
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY data/ ./data/
COPY pyproject.toml .
COPY .env.example .env.example

# Create empty .env so load_dotenv doesn't fail
RUN touch .env

# ── Built SPA from stage 1 → /app/frontend/dist (app.py spa_fallback serves it) ──
COPY --from=frontend /frontend/dist ./frontend/dist

# ── Health check ──
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:5656/health || exit 1

EXPOSE 5656

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "src.web.app:app", "--host", "0.0.0.0", "--port", "5656"]
