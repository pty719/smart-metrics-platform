"""FastAPI application entry point.

Run with::

    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.exceptions import app_exception_handler
from app.api.v1.router import router as v1_router
from app.config import settings
from app.core.database import engine
from app.core.exceptions import AppException
from app.core.logging import setup_logging
from app.core.redis_client import close_redis, get_redis

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup / shutdown lifecycle.

    On startup:
    - Initialise structured logging.
    - Warm up the Redis connection pool.

    On shutdown:
    - Dispose the SQLAlchemy engine connection pool.
    - Close the Redis client.
    """
    setup_logging(settings.LOG_LEVEL)
    logger.info("starting_up", app=settings.APP_NAME, debug=settings.DEBUG)

    # Warm up Redis (creates the singleton client)
    get_redis()

    yield  # ← application is running

    logger.info("shutting_down", app=settings.APP_NAME)
    await engine.dispose()
    await close_redis()


app = FastAPI(
    title="Smart Metrics Analytics Platform",
    description=(
        "智能指标分析平台 API — 轻量级、API优先的时序指标分析引擎。\n\n"
        "## 认证\n"
        "所有端点（`/health` 除外）需要在 `Authorization` 头中携带 Bearer Token：\n"
        "```\nAuthorization: Bearer <your-api-key>\n```"
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    # In production, restrict to specific domains via CORS_ORIGINS env var.
    # Development default is ["*"] (all origins allowed).
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception handlers ────────────────────────────────────────────────────────
app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(v1_router, prefix="/api/v1")
