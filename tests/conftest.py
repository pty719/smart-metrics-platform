"""Pytest fixtures shared across all tests.

- Uses a temp-file SQLite DB (not :memory:) so the same file is
  shared across all connections within one test session.
- Does NOT mock verify_api_key; the real dependency runs so that
  auth-failure tests (401/403) work correctly.
"""
from __future__ import annotations

import pathlib
import tempfile

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.database import Base, get_db
from app.core.security import verify_api_key
from app.main import app as _app

# ── Test database (temp-file SQLite, shared across connections) ─────
_TMP_DB = pathlib.Path(tempfile.gettempdir()) / "smart_metrics_test.db"
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{_TMP_DB}"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_factory = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=True,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_test_tables():
    """Create all tables once per test session; clean up afterwards."""
    _TMP_DB.unlink(missing_ok=True)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await test_engine.dispose()
    _TMP_DB.unlink(missing_ok=True)


@pytest_asyncio.fixture()
async def db_session() -> AsyncSession:
    """Yield a clean DB session; rollback after each test."""
    async with test_session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture()
async def client(db_session: AsyncSession) -> AsyncClient:
    """Return an async HTTP test client with the DB dependency overridden.

    The verify_api_key dependency is NOT overridden here, so the real
    implementation runs and properly rejects missing/invalid tokens.
    Tests that need a valid token must send the Authorization header.
    """
    settings.API_KEY = "test-api-key"

    async def _override_get_db():
        yield db_session

    _app.dependency_overrides[get_db] = _override_get_db
    # Do NOT override verify_api_key — let the real one run.

    async with AsyncClient(
        transport=ASGITransport(app=_app), base_url="http://test"
    ) as ac:
        yield ac

    _app.dependency_overrides.clear()


@pytest.fixture()
def api_key() -> str:
    """Return the API key expected by the test server."""
    return "test-api-key"


@pytest_asyncio.fixture()
async def existing_metric(db_session: AsyncSession) -> dict:
    """Create a metric in the test DB and return its representation."""
    from app.models.metric import Metric

    m = Metric(name="existing_metric", unit="人", description="固固固")
    db_session.add(m)
    await db_session.flush()
    await db_session.refresh(m)
    return {"id": m.id, "name": m.name, "unit": m.unit, "description": m.description}
