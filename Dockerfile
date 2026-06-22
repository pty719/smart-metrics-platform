# ============================================================
# Multi-stage Dockerfile for Smart Metrics Platform
# ============================================================
#
# Stage 1 — builder
#   Installs build tools (gcc, libpq-dev) and compiles all Python
#   wheels.  This stage is discarded in the final image.
#
# Stage 2 — runtime
#   Copies only the compiled packages into a minimal slim image.
#   Result: ~40% smaller image, no build toolchain in production.
#
# Build for production:
#   docker build --target runtime -t smart-metrics:latest .
#
# Build for dev (includes all layers, used by docker-compose.yml):
#   docker build -t smart-metrics:dev .
# ============================================================

# ── Stage 1: builder ─────────────────────────────────────────
FROM docker.m.daocloud.io/library/python:3.11-slim AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build-time system dependencies needed to compile asyncpg / psycopg wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies into an isolated prefix so they can be
# copied cleanly to the runtime stage.
COPY requirements/ requirements/
RUN pip install --prefix=/install -r requirements/prod.txt

# ── Stage 2: runtime ─────────────────────────────────────────
FROM docker.m.daocloud.io/library/python:3.11-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Tell Python where the extra packages live
    PYTHONPATH=/app

# Only the runtime shared library is needed (libpq.so.5), not the headers.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy compiled Python packages from the builder stage
COPY --from=builder /install /usr/local

# ── Security: run as non-root ─────────────────────────────────
RUN groupadd --system appgroup \
    && useradd --system --gid appgroup --no-create-home appuser

# Copy application source code (owned by the non-root user)
COPY --chown=appuser:appgroup . .

USER appuser

EXPOSE 8000

# Default: single Uvicorn worker (suitable for dev / small deployments).
# In production, override with Gunicorn via docker-compose.prod.yml.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
