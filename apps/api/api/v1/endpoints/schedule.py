from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.db import get_db
from services.orbit import OrbitPredictor
from domain.models import Satellite
from domain.repositories import get_repository
from scheduling.optimizer import PassCandidate, optimize_schedule

router = APIRouter()


class AvailabilityWindow(BaseModel):
    start: datetime
    end: datetime


class ScheduleRequest(BaseModel):
    norad_ids: List[str]
    lat: float
    lon: float
    elevation_m: float = 0.0
    min_elevation_deg: float = 10.0
    availability: List[AvailabilityWindow] = Field(default_factory=list)
    max_concurrent: int = 1


class ScheduledPass(BaseModel):
    norad_id: str
    start: datetime
    end: datetime
    max_el: float


class ScheduleResponse(BaseModel):
    selected: List[ScheduledPass]
    objective_bits: float


@router.post("/")
async def create_schedule(req: ScheduleRequest, db: Session = Depends(get_db)) -> ScheduleResponse:
    sats = (
        db.query(Satellite)
        .filter(Satellite.norad_id.in_(req.norad_ids))
        .all()
    )
    if not sats:
        raise HTTPException(status_code=404, detail="No satellites found")

    candidates: list[PassCandidate] = []
    for sat in sats:
        predictor = OrbitPredictor(sat.tle_line1, sat.tle_line2, sat.tle_epoch)
        # Very simple: find up to 5 passes in next 24h within availability
        from datetime import timedelta, timezone

        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        end = now + timedelta(days=1)
        search_start = now
        found = 0
        while search_start < end and found < 5:
            p = predictor.find_next_pass(
                lat=req.lat,
                lon=req.lon,
                elevation=req.elevation_m,
                start_time=search_start,
                end_time=end,
                min_elevation=req.min_elevation_deg,
                time_step=60.0,
            )
            if not p:
                break
            # Filter by availability
            ok = True
            if req.availability:
                ok = any(win.start <= p["rise_time"] and p["set_time"] <= win.end for win in req.availability)
            if ok:
                bitrate = 120_000.0  # placeholder bitrate
                candidates.append(
                    PassCandidate(
                        sat_id=sat.norad_id,
                        start=p["rise_time"],
                        end=p["set_time"],
                        min_el_deg=p["max_elevation"],
                        bitrate_bps=bitrate,
                        weight=1.0,
                    )
                )
                found += 1
            search_start = p["set_time"]

    if not candidates:
        return ScheduleResponse(selected=[], objective_bits=0.0)

    res = optimize_schedule(candidates, max_concurrent=req.max_concurrent)
    selected = [
        ScheduledPass(
            norad_id=candidates[i].sat_id,
            start=candidates[i].start,
            end=candidates[i].end,
            max_el=candidates[i].min_el_deg,
        )
        for i in res.selected_indices
    ]
    return ScheduleResponse(selected=selected, objective_bits=res.objective_bits)


