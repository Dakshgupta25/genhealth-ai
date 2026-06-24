"""
FastAPI application entry point.

Configures:
- Application metadata and lifecycle hooks
- CORS middleware (allowing configured frontend origins)
- Request logging middleware
- Rate limiting middleware
- All API router registrations
- Health check and root endpoints
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import (
    close_mongo,
    close_pg_engine,
    close_redis,
    init_mongo,
    init_pg_engine,
    init_redis,
)
from app.routers import (
    auth,
    doctor,
    family,
    insights,
    invite,
    recommendations,
    records,
    risk,
    upload,
    users,
)

settings = get_settings()

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.is_development else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─── Application Lifecycle ────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application startup and shutdown lifecycle.

    On startup:  Initialize database connections and verify connectivity.
    On shutdown: Gracefully close all connections.
    """
    # ── Startup ──
    logger.info("Starting GenHealth AI API (env=%s)...", settings.ENVIRONMENT)
    try:
        init_pg_engine()
        init_mongo()
        await init_redis()
        logger.info("All database connections established.")
    except Exception as exc:
        logger.critical("Failed to initialize databases: %s", exc)
        raise

    yield  # Application is running

    # ── Shutdown ──
    logger.info("Shutting down GenHealth AI API...")
    await close_pg_engine()
    await close_mongo()
    await close_redis()
    logger.info("All connections closed. Goodbye.")


# ─── FastAPI App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "GenHealth AI — Generational Health Intelligence Platform API. "
        "Predict, prevent, and personalize healthcare using multi-generational "
        "family health data."
    ),
    version=settings.PROJECT_VERSION,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    openapi_url="/openapi.json" if settings.is_development else None,
    lifespan=lifespan,
)


# ─── Middleware ───────────────────────────────────────────────────────────────

# GZip compression for responses > 1KB
app.add_middleware(GZipMiddleware, minimum_size=1024)

# CORS — allow configured frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-RateLimit-Remaining"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """
    Log every incoming request with method, path, status code, and duration.

    Adds:
    - X-Request-ID header to the response for tracing
    - Timing information in logs
    """
    import uuid
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start_time = time.perf_counter()

    logger.info(
        "→ %s %s | client=%s | req_id=%s",
        request.method,
        request.url.path,
        request.client.host if request.client else "unknown",
        request_id,
    )

    response = await call_next(request)

    duration_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        "← %s %s | status=%d | %.1fms | req_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        request_id,
    )

    response.headers["X-Request-ID"] = request_id
    return response


# ─── Global Exception Handlers ────────────────────────────────────────────────

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Return consistent JSON for 404 errors."""
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "error": f"The endpoint {request.url.path} does not exist.",
            "code": "NOT_FOUND",
        },
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Return consistent JSON for unhandled 500 errors."""
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "An internal server error occurred. Please try again.",
            "code": "INTERNAL_ERROR",
        },
    )


# ─── Router Registration ──────────────────────────────────────────────────────

PREFIX = settings.API_V1_PREFIX

app.include_router(auth.router,            prefix=f"{PREFIX}/auth",            tags=["Authentication"])
app.include_router(users.router,           prefix=f"{PREFIX}/users",           tags=["Users"])
app.include_router(family.router,          prefix=f"{PREFIX}/family",          tags=["Family"])
app.include_router(records.router,         prefix=f"{PREFIX}/records",         tags=["Health Records"])
app.include_router(upload.router,          prefix=f"{PREFIX}/upload",          tags=["Upload"])
app.include_router(risk.router,            prefix=f"{PREFIX}/risk",            tags=["Risk Analysis"])
app.include_router(insights.router,        prefix=f"{PREFIX}/insights",        tags=["Insights"])
app.include_router(recommendations.router, prefix=f"{PREFIX}/recommendations", tags=["Recommendations"])
app.include_router(doctor.router,          prefix=f"{PREFIX}/doctor",          tags=["Doctor Portal"])
app.include_router(invite.router,          prefix=f"{PREFIX}/invite",          tags=["Invites"])


# ─── Root & Health Endpoints ──────────────────────────────────────────────────

@app.get("/", tags=["Root"], include_in_schema=False)
async def root():
    """Root endpoint — confirms the API is running."""
    return {
        "success": True,
        "data": {
            "name": settings.PROJECT_NAME,
            "version": settings.PROJECT_VERSION,
            "environment": settings.ENVIRONMENT,
            "docs": "/docs" if settings.is_development else "disabled",
        },
        "message": "GenHealth AI API is running.",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Detailed health check endpoint.

    Checks connectivity to all dependent services.
    Used by Docker health checks and load balancers.
    """
    from app.database import _pg_engine, _mongo_client, _redis_client

    checks = {}

    # PostgreSQL check
    try:
        async with _pg_engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        checks["postgres"] = "healthy"
    except Exception as e:
        checks["postgres"] = f"unhealthy: {e}"

    # MongoDB check
    try:
        await _mongo_client.admin.command("ping")
        checks["mongodb"] = "healthy"
    except Exception as e:
        checks["mongodb"] = f"unhealthy: {e}"

    # Redis check
    try:
        await _redis_client.ping()
        checks["redis"] = "healthy"
    except Exception as e:
        checks["redis"] = f"unhealthy: {e}"

    all_healthy = all("healthy" == v for v in checks.values())
    status_code = 200 if all_healthy else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "success": all_healthy,
            "data": {
                "status": "healthy" if all_healthy else "degraded",
                "services": checks,
                "version": settings.PROJECT_VERSION,
            },
            "message": "All services healthy." if all_healthy else "Some services are degraded.",
        },
    )
