"""
SatLink Digital Twin API - Main Application

This is the main entry point for the SatLink Digital Twin API.
It sets up the FastAPI application with all necessary middleware, routes, and security features.
"""
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from starlette.middleware.sessions import SessionMiddleware

# Add the current directory to Python path
sys.path.append(os.path.dirname(__file__))

# Import core components
from core.config import settings, get_settings
from core.security import (
    add_security_headers,
    rate_limited,
    get_api_key,
    RateLimitExceeded
)
from core.logging import setup_logging

# Import API routers
from api.v1.api import api_router
from routers import digital_twin

# Configure logging
logger = logging.getLogger(__name__)
setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events"""
    # Startup: Initialize resources
    print("Starting SatLink Planner API…")

    # ------------------------------------------------------------------
    # Database initialisation
    # ------------------------------------------------------------------
    from core import db as _db  # lazy import to avoid circular deps

    env = os.getenv("ENV", "dev")
    try:
        if env == "dev":
            _db.create_all()
        else:
            _db.run_migrations()
    except Exception as exc:  # pragma: no cover
        # Log the error but continue starting up so that we can still inspect
        # the server. In production you might want to re-raise.
        print(f"[DB] Initialisation failed: {exc}")

    yield
    
    # Shutdown: Clean up resources
    print("Shutting down SatLink Planner API...")

# Create the FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="""
    Digital Twin API for Satellite Operations
    
    ## Overview
    This API provides comprehensive satellite operations management including:
    - TLE management and Space-Track.org integration
    - Collision risk assessment (COLA)
    - Frequency coordination and ITU-R compliance
    - Adaptive Coding and Modulation (ACM)
    - Network topology planning
    - Handover scheduling
    - Anomaly detection and AI-powered response
    
    ## Authentication
    - API Key: Include `X-API-Key` header or `api_key` query parameter
    - JWT Token: Use `/api/v1/auth/login` to get a token and include it in the `Authorization: Bearer <token>` header
    
    ## Rate Limiting
    - Default: 100 requests per minute
    - Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
    - Response: 429 Too Many Requests with `Retry-After` header when limit is exceeded
    
    ## Security
    - All endpoints require authentication
    - HTTPS enforced in production
    - Security headers (CSP, HSTS, etc.)
    - Input validation and sanitization
    """,
    version=settings.VERSION,
    contact={
        "name": "SatLink Support",
        "email": "support@satlink.space"
    },
    license_info={
        "name": "Proprietary",
        "url": "https://satlink.space/terms"
    },
    lifespan=lifespan,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    openapi_url="/api/openapi.json" if settings.DEBUG else None,
    openapi_tags=[
        {
            "name": "auth",
            "description": "Authentication and user management"
        },
        {
            "name": "satellites",
            "description": "Satellite tracking and management"
        },
        {
            "name": "passes",
            "description": "Satellite pass prediction and planning"
        },
        {
            "name": "analysis",
            "description": "Link budget and performance analysis"
        }
    ]
)

# Security middleware
if settings.SECURE_HEADERS:
    app.middleware("http")(add_security_headers)

# CORS middleware - only allow configured origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "X-API-Key",
        "Authorization",
        "X-Requested-With",
        "X-CSRF-Token"
    ],
    expose_headers=[
        "Content-Disposition",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset"
    ]
)

# Session middleware for authentication
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="satlink_session",
    max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # seconds
    https_only=not settings.DEBUG,
    same_site="lax"
)

# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if not settings.RATE_LIMIT_ENABLED:
        return await call_next(request)
    
    try:
        # Apply rate limiting to all endpoints
        await rate_limited(request)
        response = await call_next(request)
        
        # Add rate limit headers to responses
        # Note: This is a simplified example - in production, you'd track this per endpoint/client
        response.headers["X-RateLimit-Limit"] = "100"
        response.headers["X-RateLimit-Remaining"] = "99"  # This would be dynamic in production
        response.headers["X-RateLimit-Reset"] = str(int(datetime.now(timezone.utc).timestamp()) + 60)
        
        return response
    except RateLimitExceeded as e:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": str(e)},
            headers={"Retry-After": str(e.retry_after)}
        )
    except Exception as e:
        logger.error(f"Error in rate_limit_middleware: {str(e)}", exc_info=True)
        return await call_next(request)

# Include API routers with security dependencies
app.include_router(
    api_router,
    prefix=settings.API_V1_STR,
    dependencies=[Depends(get_api_key)]  # Require API key for all API endpoints
)

# Include digital twin router
app.include_router(
    digital_twin.router,
    prefix=f"{settings.API_V1_STR}/digital-twin",
    tags=["digital-twin"],
    dependencies=[Depends(get_api_key)]
)

# Mount static files (if any)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", include_in_schema=False)
async def root():
    """
    Redirect root to API docs for a clean landing page.
    In production, this would redirect to your frontend or documentation site.
    """
    if settings.DEBUG:
        return RedirectResponse(url="/api/docs")
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "documentation": "https://api.satlink.space/docs"
    }


@app.get("/health", include_in_schema=False)
async def health_check():
    """
    Health check endpoint.
    
    Returns the current status of the API and its dependencies.
    """
    status = {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "database": "ok",  # Add actual database check
        "services": {
            "space_track": "ok" if settings.SPACE_TRACK_USERNAME else "disabled"
        }
    }
    
    # Add database status check
    try:
        from sqlalchemy import text
        from core.database import SessionLocal
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        status["database"] = "error"
        status["error"] = str(e)
    
    return status

# Error handler for rate limiting
@app.exception_handler(RateLimitExceeded)
async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": str(exc)},
        headers={"Retry-After": str(exc.retry_after)}
    )

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler that returns a JSON response for all unhandled exceptions."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    
    # Don't expose internal errors in production
    detail = str(exc) if settings.DEBUG else "Internal server error"
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": detail}
    )

# Startup event
@app.on_event("startup")
async def startup_event():
    """Run startup tasks."""
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} in {settings.ENVIRONMENT} mode")
    
    # Initialize database
    try:
        from core.database import init_db
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}", exc_info=True)
        raise

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Run shutdown tasks."""
    logger.info("Shutting down application...")

# Run the application with uvicorn when executed directly
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        workers=settings.WORKERS,
        log_level=settings.LOG_LEVEL.lower(),
        # Security-related uvicorn settings
        headers=[
            ("X-Content-Type-Options", "nosniff"),
            ("X-Frame-Options", "DENY"),
            ("X-XSS-Protection", "1; mode=block"),
            ("Referrer-Policy", "strict-origin-when-cross-origin")
        ]
    )
