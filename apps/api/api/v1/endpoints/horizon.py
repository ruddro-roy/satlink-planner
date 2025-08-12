from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.db import get_db
from passes.horizon import SRTMTiles, compute_horizon_mask_from_dem
from domain.models import HorizonMask

router = APIRouter()


class ComputeMaskRequest(BaseModel):
    name: Optional[str] = None
    lat: float
    lon: float
    search_radius_km: float = 50.0
    azimuth_step_deg: int = 1
    sample_step_km: float = 0.5


class MaskResponse(BaseModel):
    id: int
    name: Optional[str]
    elevations_deg: List[float]


@router.post("/compute", response_model=MaskResponse)
async def compute_mask(req: ComputeMaskRequest, db: Session = Depends(get_db)):
    dem = SRTMTiles(cache_dir=".cache/srtm")  # stubbed DEM
    mask = compute_horizon_mask_from_dem(
        dem=dem,
        gs_lat_deg=req.lat,
        gs_lon_deg=req.lon,
        search_radius_km=req.search_radius_km,
        azimuth_step_deg=req.azimuth_step_deg,
        sample_step_km=req.sample_step_km,
    )
    elevations = [float(x) for x in mask.elevations_deg.tolist()]
    if len(elevations) != 360:
        # Normalize to 360 entries
        full = [0.0] * 360
        for i, v in enumerate(elevations):
            full[i] = v
        elevations = full

    hm = HorizonMask(name=req.name, latitude=req.lat, longitude=req.lon, elevations_deg=elevations)
    db.add(hm)
    db.commit()
    db.refresh(hm)
    return MaskResponse(id=hm.id, name=hm.name, elevations_deg=hm.elevations_deg)


class SaveMaskRequest(BaseModel):
    name: Optional[str] = None
    elevations_deg: List[float] = Field(..., min_items=360, max_items=360)


@router.post("/save", response_model=MaskResponse)
async def save_mask(req: SaveMaskRequest, db: Session = Depends(get_db)):
    hm = HorizonMask(name=req.name, elevations_deg=[float(x) for x in req.elevations_deg])
    db.add(hm)
    db.commit()
    db.refresh(hm)
    return MaskResponse(id=hm.id, name=hm.name, elevations_deg=hm.elevations_deg)


@router.get("/{mask_id}", response_model=MaskResponse)
async def get_mask(mask_id: int, db: Session = Depends(get_db)):
    hm = db.query(HorizonMask).get(mask_id)
    if not hm:
        raise HTTPException(status_code=404, detail="Mask not found")
    return MaskResponse(id=hm.id, name=hm.name, elevations_deg=hm.elevations_deg)


