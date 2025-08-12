from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from math import atan2, degrees, hypot
from pathlib import Path
from typing import Iterable, List, Protocol, Sequence

import numpy as np


class DEMSource(Protocol):
    def elevation_m(self, lat_deg: float, lon_deg: float) -> float: ...


@dataclass
class StaticMask:
    angles_deg: np.ndarray  # 0..359 integer degrees
    elevations_deg: np.ndarray  # horizon elevation for each azimuth

    def elevation_at(self, azimuth_deg: float) -> float:
        i = int(round(azimuth_deg)) % 360
        return float(self.elevations_deg[i])


class SRTMTiles(DEMSource):
    """Very small stub that reads sampled elevations from a CSV cache.
    Real SRTM reader can be plugged in later.
    """

    def __init__(self, cache_dir: str | Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @lru_cache(maxsize=1024)
    def elevation_m(self, lat_deg: float, lon_deg: float) -> float:
        # Stub: use a deterministic pseudo-elevation based on coords
        return 100.0 + 20.0 * np.sin(np.radians(lat_deg)) + 10.0 * np.cos(np.radians(lon_deg))


def compute_horizon_mask_from_dem(
    dem: DEMSource,
    gs_lat_deg: float,
    gs_lon_deg: float,
    search_radius_km: float = 50.0,
    azimuth_step_deg: int = 1,
    sample_step_km: float = 0.5,
) -> StaticMask:
    angles = np.arange(0, 360, azimuth_step_deg, dtype=int)
    elevations = np.zeros_like(angles, dtype=float)

    gs_elev = dem.elevation_m(gs_lat_deg, gs_lon_deg)

    # Radial scan in each direction and keep max apparent elevation angle
    for idx, az in enumerate(angles):
        max_el = 0.0
        # March outward up to radius
        steps = int(max(1, search_radius_km / sample_step_km))
        for s in range(1, steps + 1):
            r_km = s * sample_step_km
            # Simple equirectangular step (fine for small radii)
            dlat = (r_km / 111.0) * np.cos(np.radians(az))
            dlon = (r_km / (111.0 * np.cos(np.radians(gs_lat_deg)))) * np.sin(np.radians(az))
            lat = gs_lat_deg + dlat
            lon = gs_lon_deg + dlon
            elev = dem.elevation_m(lat, lon)
            # Apparent elevation angle above tangent plane
            dh = elev - gs_elev
            el = degrees(atan2(dh, r_km * 1000.0))
            if el > max_el:
                max_el = el
        elevations[idx] = max(0.0, max_el)

    return StaticMask(angles_deg=angles, elevations_deg=elevations)


def is_visible_with_mask(elevation_deg: float, azimuth_deg: float, mask: StaticMask | None) -> bool:
    if mask is None:
        return elevation_deg >= 0.0
    return elevation_deg >= mask.elevation_at(azimuth_deg)


