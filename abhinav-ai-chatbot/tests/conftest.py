"""
Pytest configuration — sets up async event loop and test database.
"""
import asyncio
import os
import sys

import pytest
import pytest_asyncio

# Ensure backend is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# Test environment
os.environ["APP_ENV"] = "development"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_abhinav_phase2.db"
os.environ["AI_PROVIDER"] = "mock"
os.environ["MDOC_ENABLED"] = "false"
os.environ["CELERY_ENABLED"] = "false"
os.environ["APP_SECRET_KEY"] = "test_secret_key_32_chars_minimum_here"
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_32_chars_min_here"


@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()


@pytest_asyncio.fixture(scope="session")
async def initialize_db():
    """Initialize database tables once for the entire test session."""
    # Clear lru_cache so test env vars take effect
    from app.core.config import get_settings
    get_settings.cache_clear()
    
    from app.database.session import init_db
    await init_db()
    yield
    # Cleanup test db
    import aiosqlite
    db_path = "./test_abhinav_phase2.db"
    if os.path.exists(db_path):
        os.remove(db_path)
