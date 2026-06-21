"""Pytest fixtures shared across all tests.

Phase 0 provides the database/client plumbing; individual test modules
will add more specific fixtures as needed.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.security import verify_api_key
from app.main import app

# ── Test database (SQLite in-memory, async) ───────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_factory = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_test_tables():
    """Create all tables once per test session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture()
async def db_session() -> AsyncSession:
    """Yield a clean DB session for each test (rolled back after the test)."""
    async with test_session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture()
async def client(db_session: AsyncSession) -> AsyncClient:
    """Return an async HTTP test client with the DB dependency overridden."""

    async def _override_get_db():
        yield db_session

    async def _override_verify_api_key():
        return "test-api-key"

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[verify_api_key] = _override_verify_api_key

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture()
def api_key() -> str:
    return "test-api-key"
