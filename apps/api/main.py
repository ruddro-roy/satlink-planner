from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
import uvicorn
import os
import sys
# Ensure that the 'core' package inside apps/api is discoverable when running the app
sys.path.append(os.path.dirname(__file__))
from contextlib import asynccontextmanager

from core.config import settings
from api.v1.api import api_router
from routers import digital_twin

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
    title="SatLink Digital Twin API",
    description="""
    Digital Twin API for Satellite Operations
    
    This API provides comprehensive satellite operations management including:
    - TLE management and Space-Track.org integration
    - Collision risk assessment (COLA)
    - Frequency coordination and ITU-R compliance
    - Adaptive Coding and Modulation (ACM)
    - Network topology planning
    - Handover scheduling
    - Anomaly detection and AI-powered response
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"]
)

# Include API routers
app.include_router(api_router, prefix="/api/v1")
app.include_router(digital_twin.router, prefix="/api/v1")

@app.get("/")
async def root():
    """Redirect root to API docs for a clean landing page"""
    return RedirectResponse(url="/api/docs")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "time_utc": datetime.now(timezone.utc).isoformat()
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        workers=4
    )
