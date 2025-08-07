from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import math
import requests
from .config import settings

ISO = "%Y-%m-%dT%H:%M:%SZ"

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def parse_iso(s: Optional[str], default: Optional[datetime] = None) -> datetime:
    if s is None:
        if default is not None:
            return default
        return now_utc()
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)

def to_iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime(ISO)

def geocode_address(address: str) -> Tuple[float, float]:
    if not settings.google_maps_api_key:
        raise ValueError("GOOGLE_MAPS_API_KEY not configured on server")
    params = {
        "address": address,
        "key": settings.google_maps_api_key,
    }
    resp = requests.get("https://maps.googleapis.com/maps/api/geocode/json", params=params, timeout=15)
    if resp.status_code != 200:
        raise ValueError(f"Geocoding failed: {resp.status_code}")
    data = resp.json()
    if data.get("status") != "OK" or not data.get("results"):
        raise ValueError("Address not found")
    loc = data["results"][0]["geometry"]["location"]
    return float(loc["lat"]), float(loc["lng"])

# Coordinate transforms
# TEME -> ECEF approximation via GMST rotation
from astropy.time import Time

def teme_to_ecef(r_teme_km: Tuple[float, float, float], t_utc: datetime) -> Tuple[float, float, float]:
    x, y, z = r_teme_km
    t = Time(t_utc)
    gmst = t.sidereal_time('mean', 'greenwich').radian
    cosg = math.cos(gmst)
    sing = math.sin(gmst)
    xe = cosg * x + sing * y
    ye = -sing * x + cosg * y
    ze = z
    return xe, ye, ze

def geodetic_to_ecef(lat_deg: float, lon_deg: float, alt_m: float) -> Tuple[float, float, float]:
    # WGS84
    a = 6378137.0
    e2 = 6.69437999014e-3
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    N = a / math.sqrt(1 - e2 * (math.sin(lat) ** 2))
    x = (N + alt_m) * math.cos(lat) * math.cos(lon)
    y = (N + alt_m) * math.cos(lat) * math.sin(lon)
    z = ((1 - e2) * N + alt_m) * math.sin(lat)
    return x / 1000.0, y / 1000.0, z / 1000.0  # km

def ecef_to_enu(dx_km: float, dy_km: float, dz_km: float, lat_deg: float, lon_deg: float) -> Tuple[float, float, float]:
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    slat, clat = math.sin(lat), math.cos(lat)
    slon, clon = math.sin(lon), math.cos(lon)
    e = -slon * dx_km + clon * dy_km
    n = -slat * clon * dx_km - slat * slon * dy_km + clat * dz_km
    u = clat * clon * dx_km + clat * slon * dy_km + slat * dz_km
    return e, n, u

def enu_to_az_el_range(e_km: float, n_km: float, u_km: float) -> Tuple[float, float, float]:
    slant = math.sqrt(e_km * e_km + n_km * n_km + u_km * u_km)
    horiz = math.sqrt(e_km * e_km + n_km * n_km)
    elev = math.degrees(math.atan2(u_km, horiz))
    az = math.degrees(math.atan2(e_km, n_km))
    if az < 0:
        az += 360.0
    return az, elev, slant
