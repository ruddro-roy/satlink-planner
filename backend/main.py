from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional
from pathlib import Path

from .config import settings
from .models import (
    HealthResponse,
    PublicConfig,
    PassesRequest,
    PassesResponse,
    MarginRequest,
    MarginResponse,
    ExportRequest,
    ICSText,
)
from .tle import fetch_tle, TLEError
from .passes import compute_passes
from .margin import compute_margin
from .exporters import build_ics, build_pdf

app = FastAPI(title="satlink-planner", version="1.0.0")

# CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api")

@api.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()

@api.get("/config/public", response_model=PublicConfig)
async def public_config() -> PublicConfig:
    return PublicConfig(google_maps_api_key=settings.google_maps_api_key)

@api.get("/tle/{norad_id}")
async def get_tle(norad_id: int):
    try:
        line1, line2 = fetch_tle(norad_id)
    except TLEError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"line1": line1, "line2": line2}

@api.post("/passes", response_model=PassesResponse)
async def passes(req: PassesRequest) -> PassesResponse:
    try:
        line1, line2 = fetch_tle(req.norad_id)
        passes = compute_passes(line1, line2, req)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return PassesResponse(norad_id=req.norad_id, passes=passes)

@api.post("/margin", response_model=MarginResponse)
async def margin(req: MarginRequest) -> MarginResponse:
    try:
        return compute_margin(req)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@api.post("/export/ics", response_model=ICSText)
async def export_ics(req: ExportRequest) -> ICSText:
    try:
        ics = build_ics(req.norad_id, req.passes, req.title)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ICSText(ics=ics)

@api.post("/export/pdf")
async def export_pdf(req: ExportRequest):
    out = Path("exports")
    out.mkdir(exist_ok=True)
    pdf_path = out / f"pass_report_{req.norad_id}.pdf"
    try:
        build_pdf(str(pdf_path), req.norad_id, req.passes, req.title)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return FileResponse(str(pdf_path), media_type="application/pdf", filename=pdf_path.name)

# Include API router
app.include_router(api)

# Static serving in production mode (after vite build copied under frontend/dist)
FRONT_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if settings.serve_static and FRONT_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONT_DIST), html=True), name="static")
