from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

class Settings(BaseModel):
    app_env: str = os.getenv("APP_ENV", "development")
    log_level: str = os.getenv("LOG_LEVEL", "info")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./satlink.db")

    # Public key injected server-side and optionally exposed by /config/public
    google_maps_api_key: Optional[str] = os.getenv("GOOGLE_MAPS_API_KEY")

    # TLE cache TTL (seconds)
    tle_cache_ttl: int = int(os.getenv("TLE_CACHE_TTL", "86400"))

    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))

    serve_static: bool = os.getenv("SERVE_STATIC", "0") in {"1", "true", "True"}

settings = Settings()
