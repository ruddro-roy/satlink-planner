"""Configuration settings for the SatLink Digital Twin API."""
from pydantic_settings import BaseSettings
from typing import List, Optional, Union
import os
import secrets
from pathlib import Path
from functools import lru_cache

class Settings(BaseSettings):
    # Application
    PROJECT_NAME: str = "SatLink Digital Twin API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    RELOAD: bool = True
    
    # API
    API_PREFIX: str = "/api"
    API_KEY: str
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: int = 24
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    
    # Database
    DATABASE_URL: str = "sqlite:///./satlink.db"
    DATABASE_TEST_URL: str = "sqlite:///./test_satlink.db"
    
    # TLE data
    TLE_DATA_DIR: str = str(Path(__file__).parent.parent / "data" / "tle")
    
    # Security Headers
    SECURE_HEADERS: bool = True
    HSTS_ENABLED: bool = True
    HSTS_MAX_AGE: int = 31536000  # 1 year
    CSP_ENABLED: bool = True
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT: str = "100/minute"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # External Services
    SPACE_TRACK_USERNAME: Optional[str] = None
    SPACE_TRACK_PASSWORD: Optional[str] = None
    
    # Email (for notifications)
    SMTP_TLS: bool = True
    SMTP_PORT: Optional[int] = None
    SMTP_HOST: Optional[str] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_ENABLED: bool = False
    EMAIL_FROM: Optional[str] = None
    EMAIL_FROM_NAME: Optional[str] = None
    
    # First Superuser
    FIRST_SUPERUSER: str = "admin@satlink.space"
    FIRST_SUPERUSER_PASSWORD: str = "changeme"
    
    class Config:
        case_sensitive = True
        env_file = ".env"
        env_file_encoding = 'utf-8'

# Generate a secure random secret key if not set
DEFAULT_SECRET_KEY = "changeme" + secrets.token_urlsafe(32)
DEFAULT_API_KEY = "sk_test_" + secrets.token_urlsafe(32)

# Update settings with defaults if not set in environment
settings = Settings(
    SECRET_KEY=os.getenv("SECRET_KEY") or DEFAULT_SECRET_KEY,
    API_KEY=os.getenv("API_KEY") or DEFAULT_API_KEY
)

# Fail closed in non-development if insecure defaults are detected
if (settings.ENVIRONMENT not in ("development", "dev")):
    if settings.SECRET_KEY.startswith("changeme"):
        raise RuntimeError("SECURITY: SECRET_KEY must be set securely in non-development environments.")
    if settings.API_KEY.startswith("sk_test_"):
        raise RuntimeError("SECURITY: API_KEY must be a production value in non-development environments.")

def get_settings() -> Settings:
    """Get application settings with dependency injection support."""
    return settings

# For use with FastAPI's Depends
get_settings_dep = lru_cache(get_settings)

# Generate .env file if it doesn't exist
def generate_env_file():
    """Generate a .env file with default values if it doesn't exist."""
    env_path = Path(__file__).parent.parent.parent / ".env"
    if not env_path.exists():
        with open(env_path, "w") as f:
            f.write(f"""# SatLink Digital Twin API Configuration
# Generated automatically - update with your actual values

# Application
ENVIRONMENT=development
DEBUG=True

# Security
SECRET_KEY={DEFAULT_SECRET_KEY}
API_KEY={DEFAULT_API_KEY}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080  # 7 days

# Database
DATABASE_URL=sqlite:///./satlink.db
DATABASE_TEST_URL=sqlite:///./test_satlink.db

# CORS
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://localhost:8000"]

# External Services (optional)
# SPACE_TRACK_USERNAME=your_username
# SPACE_TRACK_PASSWORD=your_password

# Email (optional)
# SMTP_TLS=True
# SMTP_PORT=587
# SMTP_HOST=smtp.example.com
# SMTP_USER=user@example.com
# SMTP_PASSWORD=password
# EMAILS_ENABLED=True
# EMAIL_FROM=no-reply@example.com
# EMAIL_FROM_NAME="SatLink Notifications"
""")
        print(f"Generated .env file at {env_path}")

# Generate .env file only in development if it doesn't exist
if settings.ENVIRONMENT in ("development", "dev") and os.getenv("GENERATE_ENV_FILE", "true").lower() in ("1", "true"): 
    generate_env_file()
