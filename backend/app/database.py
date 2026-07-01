"""
Database connection management.

Sets up:
- PostgreSQL via SQLAlchemy 2.0 async engine + session factory
- MongoDB via Motor async client
- Redis async client

All connections are initialized at application startup and closed on shutdown.
"""

import logging
from typing import AsyncGenerator, Optional

import redis.asyncio as aioredis
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ─── SQLAlchemy Base ──────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    __allow_unmapped__ = True


# ─── PostgreSQL ───────────────────────────────────────────────────────────────

def create_pg_engine() -> AsyncEngine:
    """
    Create the async PostgreSQL engine.

    Pool settings are tuned for moderate concurrency. Adjust for production
    based on expected connection counts.
    """
    return create_async_engine(
        settings.DATABASE_URL,
        echo=settings.is_development,       # Log SQL in dev mode
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_pre_ping=True,                  # Detect stale connections
        future=True,
    )


# Module-level engine and session factory (initialized at startup)
_pg_engine: Optional[AsyncEngine] = None
_AsyncSessionLocal: Optional[async_sessionmaker] = None


def init_pg_engine() -> None:
    """Initialize the PostgreSQL engine and session factory."""
    global _pg_engine, _AsyncSessionLocal
    _pg_engine = create_pg_engine()
    _AsyncSessionLocal = async_sessionmaker(
        _pg_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    logger.info("PostgreSQL engine initialized.")


def get_session_maker() -> async_sessionmaker:
    """Return the initialized PostgreSQL async session maker factory."""
    if _AsyncSessionLocal is None:
        init_pg_engine()
    return _AsyncSessionLocal


async def close_pg_engine() -> None:
    """Dispose the PostgreSQL connection pool gracefully."""
    global _pg_engine
    if _pg_engine:
        await _pg_engine.dispose()
        logger.info("PostgreSQL engine disposed.")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async database session.

    Usage:
        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    if _AsyncSessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_pg_engine() first.")

    async with _AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ─── MongoDB ─────────────────────────────────────────────────────────────────

_mongo_client: Optional[AsyncIOMotorClient] = None
_mongo_db: Optional[AsyncIOMotorDatabase] = None


def init_mongo() -> None:
    """Initialize the async MongoDB client."""
    global _mongo_client, _mongo_db
    _mongo_client = AsyncIOMotorClient(
        settings.MONGODB_URL,
        serverSelectionTimeoutMS=5000,
    )
    _mongo_db = _mongo_client[settings.MONGODB_DB_NAME]
    logger.info("MongoDB client initialized (db: %s).", settings.MONGODB_DB_NAME)


async def close_mongo() -> None:
    """Close the MongoDB client."""
    global _mongo_client
    if _mongo_client:
        _mongo_client.close()
        logger.info("MongoDB client closed.")


def get_mongo_db() -> AsyncIOMotorDatabase:
    """
    Return the MongoDB database instance.

    Usage:
        @router.get("/docs")
        async def list_docs(mongo: AsyncIOMotorDatabase = Depends(get_mongo_db)):
            collection = mongo["ocr_results"]
            ...
    """
    if _mongo_db is None:
        raise RuntimeError("MongoDB not initialized. Call init_mongo() first.")
    return _mongo_db


# ─── Redis ───────────────────────────────────────────────────────────────────

_redis_client: Optional[aioredis.Redis] = None


async def init_redis() -> None:
    """Initialize the async Redis client."""
    global _redis_client
    _redis_client = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    # Verify connectivity
    await _redis_client.ping()
    logger.info("Redis client initialized.")


async def close_redis() -> None:
    """Close the Redis client connection pool."""
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        logger.info("Redis client closed.")


def get_redis() -> aioredis.Redis:
    """
    Return the Redis client instance.

    Usage:
        @router.post("/cache")
        async def set_value(redis: aioredis.Redis = Depends(get_redis)):
            await redis.set("key", "value", ex=60)
    """
    if _redis_client is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis_client
