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

    # Ensure default admin user exists
    try:
        import uuid
        from app.models.user import User, UserRole
        from app.security.auth import hash_password
        async with AsyncSessionLocal() as session:
            admin_email = "ai.abhinavgroup@gmail.com"
            res = await session.execute(text("SELECT id FROM users WHERE email = :email"), {"email": admin_email})
            if not res.fetchone():
                u = User(
                    id=str(uuid.uuid4()),
                    email=admin_email,
                    full_name="Abhinav Group Administrator",
                    hashed_password=hash_password("abhinav@2026@"),
                    role=UserRole.DEVELOPER,
                    is_active=True,
                )
                session.add(u)
                await session.commit()

            # Ensure official projects exist
            res_p = await session.execute(text("SELECT count(*) FROM projects"))
            p_count = res_p.scalar() or 0
            if p_count == 0:
                from app.models.project import Project, ProjectType, ProjectStatus, ApprovalStatus
                projects_to_seed = [
                    Project(
                        id=str(uuid.uuid4()), project_id_slug="samsara", project_name="Samsara",
                        project_type=ProjectType.RESIDENTIAL, project_status=ProjectStatus.ONGOING,
                        location="Mukund Nagar", address="Mukund Nagar, Pune, Maharashtra", city="Pune", state="Maharashtra",
                        configurations="3 BHK Luxury Residences", rera_number="P52100079797", rera_verified=True,
                        price_verified=False, possession_verified=False,
                        description="Luxury 3 BHK residences in the heart of Mukund Nagar, Pune with world-class amenities.",
                        approval_status=ApprovalStatus.APPROVED, is_active=True, is_featured=True,
                    ),
                    Project(
                        id=str(uuid.uuid4()), project_id_slug="pebbles-greenfield", project_name="Pebbles Greenfield",
                        project_type=ProjectType.RESIDENTIAL, project_status=ProjectStatus.ONGOING,
                        location="Tathawade / Wakad", address="Tathawade, Wakad, Pune, Maharashtra", city="Pune", state="Maharashtra",
                        configurations="2 & 3 BHK", rera_number="P52100045923", rera_verified=True,
                        price_verified=False, possession_verified=False,
                        description="Premium 2 & 3 BHK residences with modern landscape amenities and seamless highway connectivity.",
                        approval_status=ApprovalStatus.APPROVED, is_active=True, is_featured=True,
                    ),
                    Project(
                        id=str(uuid.uuid4()), project_id_slug="the-curve", project_name="The Curve",
                        project_type=ProjectType.RESIDENTIAL, project_status=ProjectStatus.ONGOING,
                        location="Virar West", address="Virar West, Mumbai MMR, Maharashtra", city="Virar", state="Maharashtra",
                        configurations="2 & 3 BHK", rera_number="PR1240002600667", rera_verified=True,
                        price_verified=False, possession_verified=False,
                        description="Modern 2 & 3 BHK waterfront-facing apartments in Virar West, Mumbai MMR. Possession target June 2031.",
                        approval_status=ApprovalStatus.APPROVED, is_active=True, is_featured=True,
                    ),
                    Project(
                        id=str(uuid.uuid4()), project_id_slug="pebbles-business-bay", project_name="Pebbles Business Bay",
                        project_type=ProjectType.COMMERCIAL, project_status=ProjectStatus.ONGOING,
                        location="Wakad, Pune", address="Sr. No. 132(P), 121(P), Opp. Phoenix Mall of the Millennium, Near My Car showroom / Bhumkar Chowk, Wakad, Pune - 411057", city="Pune", state="Maharashtra",
                        configurations="Showrooms, Retail Spaces & Corporate Offices", rera_number="Registered", rera_verified=True,
                        price_verified=False, possession_verified=False,
                        description="Premier commercial landmark in Wakad, Pune, opposite Phoenix Mall of the Millennium near Bhumkar Chowk. High-street retail showrooms and corporate office spaces with high footfall and expressway connectivity.",
                        approval_status=ApprovalStatus.APPROVED, is_active=True, is_featured=True,
                    ),
                    Project(
                        id=str(uuid.uuid4()), project_id_slug="aeromall", project_name="Aeromall",
                        project_type=ProjectType.COMMERCIAL, project_status=ProjectStatus.COMPLETED,
                        location="Airport Road, Lohegaon", address="Pune Airport Road, Lohegaon, Pune, Maharashtra", city="Pune", state="Maharashtra",
                        configurations="Retail & Commercial Spaces", rera_number="Commercial Facility", rera_verified=True,
                        price_verified=False, possession_verified=False,
                        description="Pune's first 24x7 integrated shopping, dining, and multi-level parking commercial complex.",
                        approval_status=ApprovalStatus.APPROVED, is_active=True, is_featured=True,
                    ),
                ]
                for p in projects_to_seed:
                    session.add(p)
                await session.commit()
    except Exception:
        pass


async def check_db_connection() -> bool:
    """Health check: verify that the database is reachable."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
