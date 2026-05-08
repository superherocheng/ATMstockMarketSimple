# ── Stage 1: Build React frontend ──
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --cache /tmp/npm-cache && npm cache clean --force
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python backend + serve React build ──
FROM python:3.12-slim AS backend
WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY utils/ ./utils/
COPY data/ ./data/
COPY pyproject.toml .

# Copy frontend build from previous stage
COPY --from=frontend-builder /app/src/web/static/react/ ./src/web/static/react/

# Create .env placeholder (real values come from runtime env vars)
RUN touch .env

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Run with uvicorn
CMD ["python", "-m", "uvicorn", "src.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
