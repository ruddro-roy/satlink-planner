from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from enum import Enum
from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel, Field, validator, HttpUrl
from sqlalchemy.orm import Session
import numpy as np

from core.db import get_db
from domain.repositories import get_repository
from services.orbit import OrbitPredictor
from services.link_budget import LinkBudgetCalculator, LinkBudgetParameters, FrequencyBand
from domain.models import Satellite

router = APIRouter()

class MarginPoint(BaseModel):
    timestamp: datetime
    snr_db: float
    margin_db: float
    range_km: float
    elevation_deg: float
    azimuth_deg: float
    
    class Config:
        json_encoders = {
            datetime: lambda dt: dt.isoformat() + 'Z' if dt.tzinfo else dt.isoformat() + 'Z'
        }

class MarginResponse(BaseModel):
    points: List[MarginPoint]
    tle_epoch: datetime
    tle_age_days: float
    tle_source: Optional[str] = None
    parameters: Dict[str, Any]
    
    class Config:
        json_encoders = {
            datetime: lambda dt: dt.isoformat() + 'Z' if dt.tzinfo else dt.isoformat() + 'Z'
        }

@router.get("/", response_model=MarginResponse)
async def get_margin(
    norad_id: str = Query(..., description="NORAD ID of the satellite"),
    lat: float = Query(..., ge=-90, le=90, description="Observer latitude in degrees"),
    lon: float = Query(..., ge=-180, le=180, description="Observer longitude in degrees"),
    elevation: float = Query(0.0, description="Observer elevation in meters"),
    band: FrequencyBand = Query(..., description="Frequency band (ku or ka)"),
    rain_rate_mmh: float = Query(0.0, ge=0, le=100, description="Rain rate in mm/h"),
    tx_power_dbm: float = Query(40.0, description="Transmitter power in dBm"),
    tx_antenna_gain_dbi: float = Query(30.0, description="Transmitter antenna gain in dBi"),
    rx_antenna_gain_dbi: Optional[float] = Query(None, description="Receiver antenna gain in dBi (default based on band)"),
    system_noise_temp_k: Optional[float] = Query(None, description="System noise temperature in Kelvin (default based on band)"),
    bandwidth_mhz: float = Query(10.0, gt=0, description="Bandwidth in MHz"),
    required_cn0_db_hz: Optional[float] = Query(None, description="Required C/N0 in dB-Hz (defaults to theoretical minimum)"),
    start_time: datetime = Query(..., description="Start time for margin calculation (UTC)"),
    end_time: datetime = Query(..., description="End time for margin calculation (UTC)"),
    step_s: int = Query(60, ge=1, le=3600, description="Time step in seconds"),
    db: Session = Depends(get_db)
):
    """
    Calculate link margin over time for a satellite pass.
    
    Returns SNR and margin data points at regular intervals, along with range,
    elevation, and azimuth information.
    """
    try:
        # Validate time range
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        if start_time >= end_time:
            raise HTTPException(status_code=400, detail="End time must be after start time")
        
        if (end_time - start_time) > timedelta(days=7):
            raise HTTPException(status_code=400, detail="Time range cannot exceed 7 days")
        
        # Get satellite TLE data from database
        satellite_repo = get_repository('satellite', db)
        satellite = satellite_repo.get_by_norad_id(norad_id)
        
        if not satellite:
            raise HTTPException(
                status_code=404,
                detail=f"Satellite with NORAD ID {norad_id} not found in database"
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
        
        # Set default receiver parameters based on band if not provided
        band_params = LinkBudgetCalculator.get_band_parameters(band)
        if rx_antenna_gain_dbi is None:
            rx_antenna_gain_dbi = band_params.get('rx_antenna_gain_dbi', 35.0)
        
        if system_noise_temp_k is None:
            system_noise_temp_k = band_params.get('system_noise_temp_k', 150.0)
        
        # Create link budget parameters
        link_params = LinkBudgetParameters(
            frequency_ghz=band_params.get('frequency_ghz', 11.5 if band == FrequencyBand.KU else 20.0),
            tx_power_dbm=tx_power_dbm,
            tx_antenna_gain_dbi=tx_antenna_gain_dbi,
            rx_antenna_gain_dbi=rx_antenna_gain_dbi,
            system_noise_temp_k=system_noise_temp_k,
            bandwidth_mhz=bandwidth_mhz,
            rain_margin_db=0.0,  # We'll handle rain rate separately
            other_margins_db={
                'pointing_loss': 0.5,  # dB
                'polarization_loss': 0.5,  # dB
                'atmospheric_loss': 0.2,  # dB (base value, will be updated)
            }
        )
        
        # Generate time points
        time_points = []
        current_time = start_time
        while current_time <= end_time:
            time_points.append(current_time)
            current_time += timedelta(seconds=step_s)
        
        # Calculate link margin for each time point
        points = []
        
        for t in time_points:
            try:
                # Get satellite position and range
                az, el, rng = predictor.get_az_el_range(
                    time=t,
                    lat=lat,
                    lon=lon,
                    elevation=elevation
                )
                
                # Skip points below horizon
                if el < 0:
                    continue
                
                # Calculate link budget
                result = LinkBudgetCalculator.calculate_link_margin(
                    params=link_params,
                    distance_km=rng,
                    elevation_deg=el,
                    rain_rate_mmph=rain_rate_mmh,
                    required_cn0_db_hz=required_cn0_db_hz
                )
                
                # Create margin point
                point = MarginPoint(
                    timestamp=t,
                    snr_db=result['cn0_db_hz'] - 10 * np.log10(bandwidth_mhz * 1e6),  # Convert to SNR in bandwidth
                    margin_db=result['margin_db'],
                    range_km=rng,
                    elevation_deg=el,
                    azimuth_deg=az
                )
                points.append(point)
                
            except Exception as e:
                # Log error but continue with other points
                print(f"Error calculating margin at {t}: {str(e)}")
                continue
        
        # Calculate TLE age
        tle_age_days = (now - satellite.tle_epoch).total_seconds() / 86400.0
        
        # Prepare response with parameters
        response = MarginResponse(
            points=points,
            tle_epoch=satellite.tle_epoch,
            tle_age_days=tle_age_days,
            tle_source=getattr(satellite, 'tle_source', None),
            parameters={
                'frequency_ghz': link_params.frequency_ghz,
                'tx_power_dbm': tx_power_dbm,
                'tx_antenna_gain_dbi': tx_antenna_gain_dbi,
                'rx_antenna_gain_dbi': rx_antenna_gain_dbi,
                'system_noise_temp_k': system_noise_temp_k,
                'bandwidth_mhz': bandwidth_mhz,
                'rain_rate_mmh': rain_rate_mmh,
                'required_cn0_db_hz': required_cn0_db_hz or 'auto',
                'elevation_mask_deg': 0.0,
                'implementation_loss_db': link_params.implementation_loss_db,
                'other_margins_db': dict(link_params.other_margins_db)
            }
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating link margin: {str(e)}"
        )
