"""
Abhinav Group AI Chatbot — Database Session Management
Supports SQLite (development) and PostgreSQL (staging/production).
"""
from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from app.core.config import settings


# ---------------------------------------------------------------------------
# Base model class — all ORM models inherit from this
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Engine creation — SQLite for dev, PostgreSQL for staging/production
# ---------------------------------------------------------------------------
def _make_engine():
    """Create the SQLAlchemy engine based on the configured DATABASE_URL."""
    url = settings.database_url

    if settings.is_sqlite:
        # Ensure the URL uses the aiosqlite driver for async operations.
        # Accepts both "sqlite:///..." and "sqlite+aiosqlite:///..." inputs.
        if "aiosqlite" not in url:
            async_url = url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        else:
            async_url = url
        sync_url = url.replace("sqlite+aiosqlite:///", "sqlite:///", 1)

        # NullPool: each async task gets its own connection — avoids Windows deadlock
        # with StaticPool + aiosqlite (which runs SQLite in a background thread).
        engine = create_async_engine(
            async_url,
            connect_args={"check_same_thread": False},
            poolclass=NullPool,
            echo=settings.debug,
        )

        # Enable WAL mode and foreign keys on every new SQLite connection.
        # NullPool creates fresh connections, so the event fires cleanly each time.
        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_pragmas(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine, sync_url

    else:
        # Async PostgreSQL URL: postgresql+asyncpg://...
        async_url = url.replace("postgresql+psycopg2://", "postgresql+asyncpg://").replace(
            "postgresql://", "postgresql+asyncpg://"
        )
        engine = create_async_engine(
            async_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=settings.debug,
        )
        return engine, url


async_engine, _sync_url = _make_engine()

# Async session factory used throughout the application
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ---------------------------------------------------------------------------
# Synchronous engine for Alembic migrations
# ---------------------------------------------------------------------------
def get_sync_engine():
    """Return a synchronous engine for Alembic migrations."""
    if settings.is_sqlite:
        return create_engine(
            _sync_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_engine(_sync_url, pool_pre_ping=True)


# ---------------------------------------------------------------------------
# FastAPI dependency — yields an async database session
# ---------------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides a database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Database initialization — create tables if they don't exist
# ---------------------------------------------------------------------------
async def init_db() -> None:
    """Create all database tables. Called on application startup."""
    # Import all models so SQLAlchemy knows about them before creating tables
    from app.models import (  # noqa: F401
        audit_log, conversation, document, image, knowledge, lead, project, user
    )

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def check_db_connection() -> bool:
    """Health check: verify that the database is reachable."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
