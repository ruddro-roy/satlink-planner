from __future__ import annotations

import requests
from typing import Tuple
from .db import get_cached_tle, upsert_tle
from .config import settings

CELESTRAK_URL = "https://celestrak.org/NORAD/elements/gp.php"

class TLEError(Exception):
    pass

def fetch_tle(norad_id: int) -> Tuple[str, str]:
    # Check cache first
    cached = get_cached_tle(norad_id, settings.tle_cache_ttl)
    if cached:
        return cached

    params = {"CATNR": str(norad_id), "FORMAT": "TLE"}
    try:
        resp = requests.get(CELESTRAK_URL, params=params, timeout=15)
    except Exception as exc:
        raise TLEError(f"Network error fetching TLE: {exc}")

    if resp.status_code != 200:
        raise TLEError(f"Celestrak returned {resp.status_code}")

    text = resp.text.strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # Expect 3-line TLE: name, line1, line2; or 2-line if name missing
    if len(lines) < 2:
        raise TLEError("Invalid TLE format from Celestrak")

    if len(lines) >= 3 and lines[1].startswith("1 ") and lines[2].startswith("2 "):
        line1, line2 = lines[1], lines[2]
    elif len(lines) >= 2 and lines[0].startswith("1 ") and lines[1].startswith("2 "):
        line1, line2 = lines[0], lines[1]
    else:
        # Try last two
        line1, line2 = lines[-2], lines[-1]

    upsert_tle(norad_id, line1, line2)
    return line1, line2
