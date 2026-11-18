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
from app.security.rate_limiter import rate_limiter

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Application Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("starting_up", env=settings.app_env, debug=settings.debug)

    # Initialize database tables on startup (creates tables safely if missing)
    try:
        await init_db()
        logger.info("database_initialized")
    except Exception as exc:
        logger.warning("database_init_failed", error=str(exc))

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
async def add_security_headers(request: Request, call_next):
    """Add OWASP production security headers and mask server identity."""
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"

    # HSTS in production or HTTPS
    if settings.app_env in ("production", "staging") or request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    # Content Security Policy (allows embedding widget on official domain)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self' 'unsafe-inline' https:; "
        "img-src 'self' data: https: blob:; "
        "connect-src 'self' https: http://localhost:* http://127.0.0.1:*; "
        "frame-ancestors 'self' https://abhinavgroup.co.in https://*.abhinavgroup.co.in http://localhost:* http://127.0.0.1:*;"
    )

    # Mask server identification
    if "server" in response.headers:
        del response.headers["server"]
    if "Server" in response.headers:
        del response.headers["Server"]

    return response


@app.middleware("http")
async def add_request_timing(request: Request, call_next):
    """Add X-Response-Time header to every response."""
    start = time.monotonic()
    response: Response = await call_next(request)
    elapsed_ms = int((time.monotonic() - start) * 1000)
    response.headers["X-Response-Time"] = f"{elapsed_ms}ms"
    return response


@app.middleware("http")
async def enforce_request_size_limit(request: Request, call_next):
    """Prevent memory exhaustion by blocking oversized request payloads (>1MB)."""
    content_length = request.headers.get("content-length")
    max_size = getattr(settings, "max_request_size_bytes", 1048576)
    if content_length and content_length.isdigit():
        if int(content_length) > max_size:
            return JSONResponse(
                status_code=413,
                content={"detail": "Payload too large. Maximum allowed size is 1MB."},
            )
    return await call_next(request)


@app.middleware("http")
async def enforce_rate_limits(request: Request, call_next):
    """Sliding-window rate limiter per client IP to prevent flooding, DoS, and brute-force."""
    if not getattr(settings, "rate_limit_enabled", True):
        return await call_next(request)

    # Resolve client IP (supporting reverse proxies)
    client_ip = (
        request.headers.get("CF-Connecting-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else "127.0.0.1")
    )

    allowed, retry_after = rate_limiter.is_allowed(client_ip, request.url.path)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": f"Too many requests. Please try again in {retry_after} seconds."},
            headers={"Retry-After": str(retry_after)},
        )

    return await call_next(request)


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
_BACKEND_STATIC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))
_WIDGET_DIST = os.path.join(_BASE_DIR, "frontend", "chatbot-widget", "dist")
_WIDGET_HTML = os.path.join(_BASE_DIR, "frontend", "chatbot-widget", "test.html")
_ADMIN_DIST = os.path.join(_BASE_DIR, "frontend", "admin-dashboard", "dist")

_STATIC_DIR = _WIDGET_DIST if os.path.isdir(_WIDGET_DIST) else (_BACKEND_STATIC if os.path.isdir(_BACKEND_STATIC) else None)
if _STATIC_DIR:
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

if os.path.isdir(_ADMIN_DIST):
    _assets_dir = os.path.join(_ADMIN_DIST, "assets")
    if os.path.isdir(_assets_dir):
        app.mount("/admin/assets", StaticFiles(directory=_assets_dir), name="admin_assets")

    @app.get("/admin", include_in_schema=False)
    @app.get("/admin/{full_path:path}", include_in_schema=False)
    async def admin_spa(full_path: str = ""):
        candidate = os.path.join(_ADMIN_DIST, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(_ADMIN_DIST, "index.html"))

@app.get("/widget-test", include_in_schema=False)
async def widget_test_page():
    """Serves the test page with the floating chatbot widget."""
    if os.path.isfile(_WIDGET_HTML):
        return FileResponse(_WIDGET_HTML)
    backend_test = os.path.join(_BACKEND_STATIC, "test.html") if _BACKEND_STATIC else ""
    if backend_test and os.path.isfile(backend_test):
        return FileResponse(backend_test)
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
