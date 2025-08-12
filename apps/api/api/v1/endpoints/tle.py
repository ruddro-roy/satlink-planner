from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Depends
from sqlalchemy.orm import Session

from core.db import get_db
from domain.models import Satellite

router = APIRouter()


@router.get("/{norad_id}")
async def get_tle(norad_id: str = Path(..., description="NORAD ID"), db: Session = Depends(get_db)):
    sat = db.query(Satellite).filter(Satellite.norad_id == norad_id).first()
    if not sat:
        raise HTTPException(status_code=404, detail="Satellite not found")
    return {
        "norad_id": sat.norad_id,
        "name": sat.name,
        "tle_line1": sat.tle_line1,
        "tle_line2": sat.tle_line2,
        "tle_epoch": sat.tle_epoch,
    }


