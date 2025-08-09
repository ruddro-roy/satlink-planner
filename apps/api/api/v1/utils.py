from __future__ import annotations
from datetime import datetime
from typing import Optional, Tuple
import requests
from sqlalchemy.orm import Session

from domain.models import Satellite

CELESTRAK_TLE_URL = "https://celestrak.org/NORAD/elements/gp.php?CATNR={catnr}&FORMAT=tle"


def _parse_tle_epoch(line1: str) -> datetime:
    epoch_str = line1[18:32]
    year = 2000 + int(epoch_str[:2])
    day_of_year = float(epoch_str[2:])
    base = datetime(year, 1, 1)
    return base + (day_of_year - 1) * (base.replace(month=1, day=2) - base)


def fetch_tle_celestrak(norad_id: str) -> Optional[Tuple[str, str, str, datetime]]:
    try:
        url = CELESTRAK_TLE_URL.format(catnr=norad_id)
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        lines = [ln.strip() for ln in r.text.strip().splitlines() if ln.strip()]
        if len(lines) >= 3:
            name, l1, l2 = lines[0], lines[1], lines[2]
            epoch = _parse_tle_epoch(l1)
            return name, l1, l2, epoch
    except Exception:
        return None
    return None


essential_demo_satellites = {
    # ISS for quick demo
    "25544": "International Space Station",
}


def ensure_satellite_in_db(db: Session, norad_id: str) -> Optional[Satellite]:
    sat = db.query(Satellite).filter(Satellite.norad_id == norad_id).first()
    if sat:
        return sat
    # Try fetch from Celestrak
    fetched = fetch_tle_celestrak(norad_id)
    if not fetched:
        # As last resort, skip creating
        return None
    name, l1, l2, epoch = fetched
    sat = Satellite(
        norad_id=norad_id,
        name=name or essential_demo_satellites.get(norad_id),
        tle_line1=l1,
        tle_line2=l2,
        tle_epoch=epoch,
    )
    db.add(sat)
    db.commit()
    db.refresh(sat)
    return sat
