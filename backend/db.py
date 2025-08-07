from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional, Tuple
import time

DB_PATH = Path("satlink.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tles (
  norad_id INTEGER PRIMARY KEY,
  line1 TEXT NOT NULL,
  line2 TEXT NOT NULL,
  fetched_at INTEGER NOT NULL
);
"""

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Initialize schema
with get_conn() as _conn:
    _conn.executescript(SCHEMA_SQL)
    _conn.commit()

def get_cached_tle(norad_id: int, ttl_seconds: int) -> Optional[Tuple[str, str]]:
    now = int(time.time())
    with get_conn() as conn:
        row = conn.execute(
            "SELECT line1, line2, fetched_at FROM tles WHERE norad_id = ?",
            (norad_id,),
        ).fetchone()
        if not row:
            return None
        if now - row["fetched_at"] > ttl_seconds:
            return None
        return row["line1"], row["line2"]

def upsert_tle(norad_id: int, line1: str, line2: str) -> None:
    now = int(time.time())
    with get_conn() as conn:
        conn.execute(
            "REPLACE INTO tles (norad_id, line1, line2, fetched_at) VALUES (?, ?, ?, ?)",
            (norad_id, line1, line2, now),
        )
        conn.commit()
