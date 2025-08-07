from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from datetime import datetime, timezone

class HealthResponse(BaseModel):
    status: str = "ok"

class PublicConfig(BaseModel):
    google_maps_api_key: Optional[str] = None

class PassesRequest(BaseModel):
    norad_id: int = Field(..., ge=1)
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lon: Optional[float] = Field(None, ge=-180, le=180)
    address: Optional[str] = None
    mask_deg: float = Field(10.0, ge=0, le=90)
    start_iso: Optional[str] = None
    end_iso: Optional[str] = None
    step_seconds: int = Field(10, ge=1, le=120)
    altitude_m: float = Field(0.0, ge=-430.0, le=9000.0)

    @field_validator("start_iso", "end_iso")
    @classmethod
    def validate_iso8601(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            # parse; raise if bad
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception as exc:
            raise ValueError("Invalid ISO8601 time") from exc
        return v

class PassSample(BaseModel):
    t: str  # ISO time UTC
    elev_deg: float
    az_deg: float
    range_km: float

class PassSummary(BaseModel):
    aos_utc: str
    los_utc: str
    max_elev_deg: float
    max_elev_time_utc: str
    samples: List[PassSample]

class PassesResponse(BaseModel):
    norad_id: int
    passes: List[PassSummary]

class MarginRequest(BaseModel):
    # Either provide pass samples or parameters to recompute quickly
    samples: List[PassSample]
    # RF params
    band: str = Field("UHF")  # UHF, VHF, S, X, Ku, Ka
    tx_power_dbw: float = Field(10.0)
    tx_gain_dbi: float = Field(5.0)
    rx_gain_dbi: float = Field(20.0)
    bandwidth_hz: float = Field(20000.0, gt=0)
    system_noise_temp_k: float = Field(290.0, gt=0)
    noise_figure_db: float = Field(2.0, ge=0)
    rain_loss_db: float = Field(0.0, ge=0)
    atm_loss_db: float = Field(1.0, ge=0)
    required_snr_db: float = Field(3.0)
    pointing_loss_db: float = Field(0.5, ge=0)

class MarginPoint(BaseModel):
    t: str
    snr_db: float
    margin_db: float

class MarginResponse(BaseModel):
    points: List[MarginPoint]

class ExportRequest(BaseModel):
    norad_id: int
    passes: List[PassSummary]
    title: str = "Satellite Passes"

class ICSText(BaseModel):
    ics: str
