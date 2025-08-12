from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import md5
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from core.config import settings
from domain.models import Satellite


CELESTRAK_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle"


@dataclass
class RefreshResult:
    fetched: int
    updated: int
    skipped: int
    etag: Optional[str]
    source: str


def _cache_dir() -> Path:
    d = Path(settings.TLE_DATA_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _etag_path() -> Path:
    return _cache_dir() / "celestrak_active.etag"


def _tle_cache_path() -> Path:
    return _cache_dir() / "celestrak_active.tle"


def _read_text(p: Path) -> Optional[str]:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return None


async def fetch_celestrak_if_stale(ttl_minutes: int = 60) -> tuple[str, Optional[str], bool]:
    """Fetch active TLEs with ETag and TTL caching.

    Returns (text, etag, from_network)
    """
    etag_old = _read_text(_etag_path())
    text_old = _read_text(_tle_cache_path())

    age_ok = False
    if text_old:
        try:
            mtime = datetime.fromtimestamp(_tle_cache_path().stat().st_mtime, tz=timezone.utc)
            age_ok = datetime.now(timezone.utc) - mtime < timedelta(minutes=ttl_minutes)
        except Exception:
            age_ok = False

    headers = {"If-None-Match": etag_old} if etag_old else {}
    if age_ok and text_old:
        return text_old, etag_old, False

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(CELESTRAK_URL, headers=headers)
        if r.status_code == 304 and text_old:
            return text_old, etag_old, False
        r.raise_for_status()
        etag = r.headers.get("ETag")
        text = r.text
        _tle_cache_path().write_text(text, encoding="utf-8")
        if etag:
            _etag_path().write_text(etag, encoding="utf-8")
        return text, etag, True


def parse_tle_blocks(text: str) -> List[Tuple[str, str, str]]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    triples: List[Tuple[str, str, str]] = []
    for i in range(0, len(lines) - 2, 3):
        if lines[i + 1].startswith("1 ") and lines[i + 2].startswith("2 "):
            triples.append((lines[i], lines[i + 1], lines[i + 2]))
    return triples


def freshness_score(epoch_dt: datetime) -> float:
    age_days = (datetime.now(timezone.utc) - epoch_dt).total_seconds() / 86400.0
    return max(0.0, 1.0 - min(age_days / 14.0, 1.0))  # 1.0 fresh, 0.0 older than 14 days


def upsert_tles(db: Session, tle_triples: List[Tuple[str, str, str]]) -> int:
    updated = 0
    for name, l1, l2 in tle_triples:
        try:
            norad = l1.split()[1]
        except Exception:
            continue
        sat = db.query(Satellite).filter(Satellite.norad_id == norad).first()
        # Extract epoch from line-1 cols 19-32 YYDDD.DDDDDDDD
        try:
            year = int(l1[18:20])
            year += 2000 if year < 57 else 1900
            day_of_year = float(l1[20:32])
            epoch = datetime.fromordinal(datetime(year, 1, 1).toordinal() - 1 + int(day_of_year)).replace(tzinfo=timezone.utc)
        except Exception:
            epoch = datetime.now(timezone.utc)
        if sat:
            if sat.tle_line1 != l1 or sat.tle_line2 != l2:
                sat.tle_line1 = l1
                sat.tle_line2 = l2
                sat.tle_epoch = epoch
                db.add(sat)
                updated += 1
        else:
            sat = Satellite(norad_id=norad, name=name, tle_line1=l1, tle_line2=l2, tle_epoch=epoch)
            db.add(sat)
            updated += 1
    db.commit()
    return updated


async def refresh_active_tles(db: Session, ttl_minutes: int = 60) -> RefreshResult:
    text, etag, from_net = await fetch_celestrak_if_stale(ttl_minutes=ttl_minutes)
    triples = parse_tle_blocks(text)
    updated = upsert_tles(db, triples)
    return RefreshResult(fetched=len(triples), updated=updated, skipped=max(0, len(triples) - updated), etag=etag, source="celestrak")


