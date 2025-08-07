from __future__ import annotations

from typing import List, Tuple
from datetime import datetime, timedelta, timezone
from sgp4.api import Satrec, jday
from .models import PassesRequest, PassSummary, PassSample
from .utils import parse_iso, now_utc, to_iso, geocode_address, teme_to_ecef, geodetic_to_ecef, ecef_to_enu, enu_to_az_el_range


def _propagate_teme_km(sat: Satrec, t: datetime) -> Tuple[float, float, float]:
    jd, fr = jday(t.year, t.month, t.day, t.hour, t.minute, t.second + t.microsecond * 1e-6)
    e, r, v = sat.sgp4(jd, fr)
    if e != 0:
        raise ValueError(f"SGP4 error code: {e}")
    return r[0], r[1], r[2]


def compute_passes(line1: str, line2: str, req: PassesRequest) -> List[PassSummary]:
    # Resolve coords if needed
    if (req.lat is None or req.lon is None) and req.address:
        lat, lon = geocode_address(req.address)
    elif req.lat is not None and req.lon is not None:
        lat, lon = req.lat, req.lon
    else:
        raise ValueError("Provide lat/lon or address")

    start = parse_iso(req.start_iso, default=now_utc())
    end = parse_iso(req.end_iso, default=(start + timedelta(hours=24)))
    if end <= start:
        raise ValueError("end_iso must be after start_iso")

    step = timedelta(seconds=req.step_seconds)

    sat = Satrec.twoline2rv(line1, line2)

    # Precompute observer ECEF
    obs_ecef = geodetic_to_ecef(lat, lon, req.altitude_m)

    times: List[datetime] = []
    elevs: List[float] = []
    azes: List[float] = []
    ranges: List[float] = []

    t = start
    while t <= end:
        r_teme = _propagate_teme_km(sat, t)
        r_ecef = teme_to_ecef(r_teme, t)
        dx = r_ecef[0] - obs_ecef[0]
        dy = r_ecef[1] - obs_ecef[1]
        dz = r_ecef[2] - obs_ecef[2]
        e, n, u = ecef_to_enu(dx, dy, dz, lat, lon)
        az, el, slant = enu_to_az_el_range(e, n, u)
        times.append(t)
        elevs.append(el)
        azes.append(az)
        ranges.append(slant)
        t += step

    # Identify passes above mask
    passes: List[PassSummary] = []
    mask = req.mask_deg
    in_pass = False
    pass_start_idx = 0

    for i in range(len(times)):
        above = elevs[i] >= mask
        if above and not in_pass:
            in_pass = True
            pass_start_idx = i
        elif not above and in_pass:
            in_pass = False
            pass_end_idx = i
            passes.append(_build_pass(times, elevs, azes, ranges, pass_start_idx, pass_end_idx))

    # If ends while still in pass
    if in_pass:
        passes.append(_build_pass(times, elevs, azes, ranges, pass_start_idx, len(times) - 1))

    return passes


def _build_pass(times, elevs, azes, ranges, i0, i1) -> PassSummary:
    # Slice inclusive segments
    tseg = times[i0:i1 + 1]
    eseg = elevs[i0:i1 + 1]
    aseg = azes[i0:i1 + 1]
    rseg = ranges[i0:i1 + 1]

    # Max elevation
    max_idx = max(range(len(eseg)), key=lambda k: eseg[k])
    max_elev = eseg[max_idx]
    max_time = tseg[max_idx]

    samples: List[PassSample] = [
        PassSample(t=to_iso(tseg[i]), elev_deg=eseg[i], az_deg=aseg[i], range_km=rseg[i])
        for i in range(len(tseg))
    ]

    return PassSummary(
        aos_utc=to_iso(tseg[0]),
        los_utc=to_iso(tseg[-1]),
        max_elev_deg=max_elev,
        max_elev_time_utc=to_iso(max_time),
        samples=samples,
    )
