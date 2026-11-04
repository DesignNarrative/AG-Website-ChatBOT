"""
Abhinav Group AI Chatbot — FastAPI Application Entry Point
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.database.session import check_db_connection, init_db

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Application Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("starting_up", env=settings.app_env, debug=settings.debug)

    # Initialize database tables on startup (dev convenience; prod uses Alembic)
    if settings.app_env == "development":
        await init_db()
        logger.info("database_initialized")

    db_ok = await check_db_connection()
    logger.info("database_health", connected=db_ok)

    yield  # Application runs here

    logger.info("shutting_down")


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Abhinav Group AI Chatbot API",
    description=(
        "Backend API for the Abhinav Group property sales AI chatbot. "
        "Handles conversations, lead capture, knowledge retrieval, and admin operations."
    ),
    version="1.0.0",
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
    openapi_url="/api/openapi.json" if settings.debug else None,
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
# CORS — allow WordPress website, admin dashboard, and local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# GZip compression for responses > 1KB
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.middleware("http")
async def add_request_timing(request: Request, call_next):
    """Add X-Response-Time header to every response."""
    start = time.monotonic()
    response: Response = await call_next(request)
    elapsed_ms = int((time.monotonic() - start) * 1000)
    response.headers["X-Response-Time"] = f"{elapsed_ms}ms"
    return response


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to every response."""
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", exc_type=type(exc).__name__, path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again later."},
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
from app.api.v1 import router as api_v1_router  # noqa: E402

app.include_router(api_v1_router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Health Check (unauthenticated)
# ---------------------------------------------------------------------------
@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check endpoint for load balancers and monitoring."""
    db_ok = await check_db_connection()
    return {
        "status": "healthy" if db_ok else "degraded",
        "version": "1.0.0",
        "env": settings.app_env,
        "database": "connected" if db_ok else "disconnected",
        "ai_provider": settings.ai_provider,
    }


# ---------------------------------------------------------------------------
# Static Files & Local Test Endpoints
# ---------------------------------------------------------------------------
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_WIDGET_DIST = os.path.join(_BASE_DIR, "frontend", "chatbot-widget", "dist")
_WIDGET_HTML = os.path.join(_BASE_DIR, "frontend", "chatbot-widget", "test.html")
_ADMIN_DIST = os.path.join(_BASE_DIR, "frontend", "admin-dashboard", "dist")

if os.path.isdir(_WIDGET_DIST):
    app.mount("/static", StaticFiles(directory=_WIDGET_DIST), name="static")

if os.path.isdir(_ADMIN_DIST):
    app.mount("/admin", StaticFiles(directory=_ADMIN_DIST, html=True), name="admin")

@app.get("/widget-test", include_in_schema=False)
async def widget_test_page():
    """Serves the test page with the floating chatbot widget."""
    if os.path.isfile(_WIDGET_HTML):
        return FileResponse(_WIDGET_HTML)
    return {"message": "Widget test file not found"}

@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Abhinav Group AI Chatbot API is Running",
        "docs": "/api/docs",
        "widget_test_page": "/widget-test",
        "admin_dashboard": "/admin/",
        "health": "/health",
    }
