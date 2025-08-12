from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel, Field, validator, HttpUrl
from sqlalchemy.orm import Session

from core.db import get_db
from domain.repositories import get_repository
from services.orbit import OrbitPredictor
from domain.models import Satellite, HorizonMask
from api.v1.utils import ensure_satellite_in_db

router = APIRouter()

class PassWindow(BaseModel):
    rise: datetime
    max_elevation_time: datetime
    set: datetime
    duration_s: float
    max_elevation_deg: float
    
    class Config:
        json_encoders = {
            datetime: lambda dt: dt.isoformat() + 'Z' if dt.tzinfo else dt.isoformat() + 'Z'
        }

class PassesResponse(BaseModel):
    passes: List[PassWindow]
    tle_epoch: datetime
    tle_age_days: float
    tle_source: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda dt: dt.isoformat() + 'Z' if dt.tzinfo else dt.isoformat() + 'Z'
        }

@router.get("/", response_model=PassesResponse)
async def get_passes(
    norad_id: str = Query(..., description="NORAD ID of the satellite"),
    lat: float = Query(..., ge=-90, le=90, description="Observer latitude in degrees"),
    lon: float = Query(..., ge=-180, le=180, description="Observer longitude in degrees"),
    elevation: float = Query(0.0, description="Observer elevation in meters"),
    mask: float = Query(10.0, ge=0, le=90, description="Elevation mask in degrees"),
    mask_id: Optional[int] = Query(None, description="Optional horizon mask id"),
    start_time: Optional[datetime] = Query(None, description="Start time for pass search (UTC)"),
    end_time: Optional[datetime] = Query(None, description="End time for pass search (UTC), max 30 days"),
    max_passes: int = Query(10, ge=1, le=100, description="Maximum number of passes to return"),
    db: Session = Depends(get_db)
):
    """
    Get pass windows for a satellite from a ground station.
    
    Returns a list of pass windows containing rise, max elevation, and set times,
    along with the TLE epoch and age.
    """
    try:
        # Get satellite TLE data from database
        satellite_repo = get_repository('satellite', db)
        satellite = satellite_repo.get_by_norad_id(norad_id)
        
        if not satellite:
            # Try to auto-populate from public TLE source for a smooth UX
            satellite = ensure_satellite_in_db(db, norad_id)
            if not satellite:
                raise HTTPException(
                    status_code=404,
                    detail=f"Satellite with NORAD ID {norad_id} not found and could not auto-fetch TLE"
                )
        
        # Validate TLE data
        if not all([satellite.tle_line1, satellite.tle_line2, satellite.tle_epoch]):
            raise HTTPException(
                status_code=400,
                detail=f"Incomplete TLE data for satellite {norad_id}"
            )
        
        # Initialize orbit predictor
        predictor = OrbitPredictor(
            tle_line1=satellite.tle_line1,
            tle_line2=satellite.tle_line2,
            tle_epoch=satellite.tle_epoch
        )
        
        # Set default time range if not provided
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        if not start_time:
            start_time = now
        if not end_time:
            end_time = start_time + timedelta(days=7)
        
        # Validate time range
        if start_time >= end_time:
            raise HTTPException(
                status_code=400,
                detail="End time must be after start time"
            )
        
        if (end_time - start_time) > timedelta(days=30):
            raise HTTPException(
                status_code=400,
                detail="Time range cannot exceed 30 days"
            )
        
        # Find passes
        passes = []
        current_time = start_time
        
        # Optional static horizon mask
        mask_elevs = None
        if mask_id is not None:
            hm = db.query(HorizonMask).get(mask_id)
            if hm and hm.elevations_deg and len(hm.elevations_deg) == 360:
                mask_elevs = hm.elevations_deg
        
        while len(passes) < max_passes and current_time < end_time:
            # Find next pass
            pass_data = predictor.find_next_pass(
                lat=lat,
                lon=lon,
                elevation=elevation,
                start_time=current_time,
                end_time=end_time,
                min_elevation=mask,
                time_step=60.0  # 1 minute steps for initial search
            )
            
            if not pass_data:
                break
            
            # Apply horizon mask by rejecting passes whose max elevation is below the mask at TCA azimuth
            if mask_elevs is not None:
                # compute az at max time
                try:
                    az_tca, el_tca, _ = predictor.get_az_el_range(
                        time=pass_data['max_elevation_time'], lat=lat, lon=lon, elevation=elevation
                    )
                    az_idx = int(round(az_tca)) % 360
                    if el_tca < mask_elevs[az_idx]:
                        current_time = pass_data['set_time'] + timedelta(minutes=5)
                        continue
                except Exception:
                    pass

            # Add pass to results
            passes.append(PassWindow(
                rise=pass_data['rise_time'],
                max_elevation_time=pass_data['max_elevation_time'],
                set=pass_data['set_time'],
                duration_s=pass_data['duration_s'],
                max_elevation_deg=pass_data['max_elevation']
            ))
            
            # Move search window to after this pass
            current_time = pass_data['set_time'] + timedelta(minutes=5)
        
        # Calculate TLE age
        tle_age_days = (now - satellite.tle_epoch).total_seconds() / 86400.0
        
        return PassesResponse(
            passes=passes,
            tle_epoch=satellite.tle_epoch,
            tle_age_days=tle_age_days,
            tle_source=satellite.tle_source if hasattr(satellite, 'tle_source') else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating pass windows: {str(e)}"
        )
