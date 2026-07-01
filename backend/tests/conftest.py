"""
pytest configuration and shared fixtures.

Provides:
  - Async test database session (in-memory SQLite for isolation)
  - Async Redis mock
  - FastAPI TestClient with dependency overrides
  - Factory functions for common test objects
"""

import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(element, compiler, **kw):
    return "JSON"

from app.database import Base, get_db, get_redis
from app.main import app

# Import all models to ensure they are registered on Base.metadata before create_all
from app.models.user import User
from app.models.family import FamilyMember
from app.models.health_record import HealthRecord, ExtractedEntity
from app.models.prescription import Prescription
from app.models.risk_prediction import RiskPrediction
from app.models.doctor import DoctorAccess, FamilyInvite
from app.services.auth_service import hash_password, create_access_token


# ─── Event Loop ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Use a single event loop for the entire test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ─── Test Database ─────────────────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a test database session that is rolled back after each test.

    Uses a savepoint to allow nested transactions within tests.
    """
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        async with session.begin():
            yield session
            await session.rollback()


# ─── Redis Mock ───────────────────────────────────────────────────────────────

@pytest.fixture
def mock_redis():
    """Provide a mock Redis client for unit tests."""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=1)
    redis_mock.incr = AsyncMock(return_value=1)
    redis_mock.expire = AsyncMock(return_value=True)
    redis_mock.ttl = AsyncMock(return_value=60)
    redis_mock.ping = AsyncMock(return_value=True)
    return redis_mock


# ─── Test Client ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client(db_session: AsyncSession, mock_redis) -> AsyncGenerator[AsyncClient, None]:
    """
    Provide an async HTTP test client with DB and Redis overrides.

    All routes use the in-memory test database and mock Redis.
    """
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: mock_redis

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ─── Test User Factories ──────────────────────────────────────────────────────

async def create_test_user(
    db: AsyncSession,
    email: str = "test@example.com",
    full_name: str = "Test User",
    role: str = "patient",
    is_verified: bool = True,
) -> User:
    """Create and persist a test user in the test database."""
    user = User(
        email=email,
        password_hash=hash_password("TestPass1"),
        full_name=full_name,
        role=role,
        is_verified=is_verified,
    )
    db.add(user)
    await db.flush()
    return user


def auth_headers(user: User) -> dict:
    """Return Authorization headers for a given test user."""
    token = create_access_token(str(user.id), user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def test_user(db_session) -> User:
    """A verified patient user for use in tests."""
    return await create_test_user(db_session)


@pytest_asyncio.fixture
async def test_doctor(db_session) -> User:
    """A doctor user for use in tests."""
    return await create_test_user(
        db_session,
        email="doctor@example.com",
        full_name="Dr. Test",
        role="doctor",
    )
