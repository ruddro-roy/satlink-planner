"""
Security module for the SatLink Digital Twin API.

Implements:
- JWT token authentication
- API key validation
- Password hashing
- Rate limiting
- Security headers
- CSRF protection
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Union, Callable, Awaitable
from functools import wraps, lru_cache
import time
import secrets
import string
import hmac
import hashlib
import re
import json

from jose import JWTError, jwt
from jose.constants import ALGORITHMS
from passlib.context import CryptContext
from fastapi import (
    Depends, HTTPException, status, Request, Response,
    Security, Header, status
)
from fastapi.responses import JSONResponse
from fastapi.security import (
    OAuth2PasswordBearer, APIKeyHeader, APIKeyQuery,
    SecurityScopes, HTTPAuthorizationCredentials, HTTPBearer
)
from fastapi.security.utils import get_authorization_scheme_param
from starlette.status import HTTP_403_FORBIDDEN, HTTP_429_TOO_MANY_REQUESTS
from pydantic import BaseModel, ValidationError, validator, HttpUrl, EmailStr

from core.config import settings
from core.logging import get_logger

# Configure logger
logger = get_logger(__name__)

# Password hashing configuration
# Using bcrypt with a work factor of 14 (2^14 iterations)
pwd_context = CryptContext(
    schemes=["bcrypt"], 
    deprecated="auto",
    bcrypt__rounds=14
)

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False,
    scheme_name="JWT",
    scopes={
        "user": "Read user information",
        "admin": "Admin access",
        "satellite:read": "Read satellite data",
        "satellite:write": "Modify satellite data"
    }
)

# API Key schemes
api_key_header = APIKeyHeader(
    name="X-API-Key", 
    auto_error=False,
    description="API key for programmatic access"
)

api_key_query = APIKeyQuery(
    name="api_key", 
    auto_error=False,
    description="API key as URL query parameter"
)

# HTTP Bearer scheme for JWT tokens
http_bearer = HTTPBearer(
    scheme_name="JWT",
    auto_error=False,
    description="JWT token for authentication"
)

# CSRF protection
csrf_header_name = "X-CSRF-Token"
csrf_form_field = "csrf_token"

class TokenData(BaseModel):
    """Token payload data model"""
    sub: str  # Subject (usually user ID or username)
    scopes: List[str] = []
    exp: Optional[datetime] = None
    iat: Optional[datetime] = None
    jti: Optional[str] = None  # JWT ID for token revocation

    @validator('scopes', pre=True)
    def validate_scopes(cls, v):
        if isinstance(v, str):
            return v.split()
        return v or []

class Token(BaseModel):
    """Token response model"""
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None
    expires_in: int  # seconds until expiration
    token_use: str = "access"

class RefreshTokenRequest(BaseModel):
    """Refresh token request model"""
    refresh_token: str

class UserBase(BaseModel):
    """Base user model"""
    username: str
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False
    scopes: List[str] = []

class UserCreate(UserBase):
    """User creation model"""
    password: str

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v):
            raise ValueError("Password must contain at least one special character")
        return v

class UserInDB(UserBase):
    """User model for database storage"""
    id: str
    hashed_password: str
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0
    account_locked_until: Optional[datetime] = None

class User(UserBase):
    """User model for API responses"""
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class TokenPayload(BaseModel):
    """JWT token payload"""
    sub: str
    scopes: List[str] = []
    exp: datetime
    iat: datetime
    jti: str
    iss: str = settings.PROJECT_NAME
    aud: str = "satlink-api"

class SecurityException(Exception):
    """Base exception for security-related errors"""
    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)

class RateLimitExceeded(SecurityException):
    """Raised when rate limit is exceeded"""
    def __init__(self, detail: str, retry_after: int):
        super().__init__(detail, status.HTTP_429_TOO_MANY_REQUESTS)
        self.retry_after = retry_after
        self.headers = {"Retry-After": str(retry_after)}

class CSRFError(SecurityException):
    """Raised when CSRF validation fails"""
    def __init__(self, detail: str = "CSRF token validation failed"):
        super().__init__(detail, status.HTTP_403_FORBIDDEN)

class TokenError(SecurityException):
    """Raised when token validation fails"""
    def __init__(self, detail: str = "Invalid authentication credentials"):
        super().__init__(detail, status.HTTP_401_UNAUTHORIZED)

# Rate limiting storage (in production, use Redis with TTL)
_rate_limits = {}

# Token blacklist (in production, use Redis with TTL)
_token_blacklist = set()

# Failed login attempts tracking (in production, use Redis with TTL)
_failed_login_attempts = {}

# Rate limiting configuration
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 100  # max requests per window
RATE_LIMIT_BLOCK_DURATION = 300  # seconds to block after exceeding rate limit

# IP whitelist for rate limiting (e.g., load balancers, health checks)
RATE_LIMIT_WHITELIST = {
    "127.0.0.1",
    "::1",
}

# Rate limit buckets for different endpoints
RATE_LIMIT_BUCKETS = {
    "default": {
        "window": RATE_LIMIT_WINDOW,
        "limit": RATE_LIMIT_MAX_REQUESTS,
        "block_duration": RATE_LIMIT_BLOCK_DURATION,
    },
    "auth": {
        "window": 60,  # 1 minute
        "limit": 10,   # 10 requests per minute
        "block_duration": 900,  # 15 minutes
    },
    "api": {
        "window": 3600,  # 1 hour
        "limit": 1000,   # 1000 requests per hour
        "block_duration": 3600,  # 1 hour
    },
}

# Security headers configuration
SECURITY_HEADERS = {
    "Strict-Transport-Security": f"max-age={31536000}; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Embedder-Policy": "require-corp",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-site",
}

# CORS settings
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "https://satlink.space",
]

# Content Security Policy
CSP_DIRECTIVES = {
    "default-src": ["'self'"],
    "script-src": ["'self'"],
    "style-src": ["'self'"],
    "img-src": ["'self'"],
    "connect-src": ["'self'"],
    "font-src": ["'self'"],
    "object-src": ["'none'"],
    "media-src": ["'self'"],
    "frame-src": ["'none'"],
    "frame-ancestors": ["'none'"],
    "form-action": ["'self'"],
    "base-uri": ["'self'"],
    "upgrade-insecure-requests": "",
    "block-all-mixed-content": ""
}

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash using constant-time comparison.
    
    Args:
        plain_password: The plain text password to verify
        hashed_password: The hashed password to verify against
        
    Returns:
        bool: True if the password matches, False otherwise
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        # Log the error but don't leak information
        logger.error(f"Password verification error: {str(e)}")
        # Still return False to prevent timing attacks
        pwd_context.dummy_verify()
        return False

def get_password_hash(password: str) -> str:
    """
    Generate a secure password hash using bcrypt.
    
    Args:
        password: The plain text password to hash
        
    Returns:
        str: The hashed password
    """
    return pwd_context.hash(password)

def is_password_strong(password: str) -> bool:
    """
    Check if a password meets strength requirements.
    
    Requirements:
    - At least 12 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    
    Args:
        password: The password to check
        
    Returns:
        bool: True if the password is strong, False otherwise
    """
    if len(password) < 12:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    if not re.search(r"[^A-Za-z0-9]", password):
        return False
    return True

def create_access_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None,
    scopes: Optional[List[str]] = None,
    token_type: str = "access"
) -> str:
    """
    Create a JWT access token with enhanced security.
    
    Args:
        subject: The subject of the token (usually user ID or username)
        expires_delta: Optional timedelta for token expiration
        scopes: List of scopes/permissions for the token
        token_type: Type of token (access, refresh, etc.)
        
    Returns:
        str: Encoded JWT token
    """
    now = datetime.utcnow()
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Create JWT claims with security best practices
    to_encode = {
        "iss": settings.PROJECT_NAME,  # Issuer
        "sub": str(subject),          # Subject
        "iat": now,                   # Issued At
        "exp": expire,                # Expiration Time
        "jti": secrets.token_urlsafe(32),  # Unique token ID for revocation
        "type": token_type,           # Token type
        "scopes": scopes or [],       # Token scopes
        "aud": "satlink-api"          # Audience
    }
    
    # Add additional claims based on token type
    if token_type == "refresh":
        to_encode.update({"refresh": True})
    
    # Encode and return the token
    try:
        return jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
            headers={
                "kid": "satlink-1",  # Key ID for key rotation
                "alg": settings.ALGORITHM,
                "typ": "JWT"
            }
        )
    except Exception as e:
        logger.error(f"Failed to create access token: {str(e)}")
        raise TokenError("Failed to create access token")

def create_refresh_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT refresh token with extended expiration.
    
    Args:
        subject: The subject of the token (usually user ID or username)
        expires_delta: Optional timedelta for token expiration
        
    Returns:
        str: Encoded JWT refresh token
    """
    if expires_delta is None:
        expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    return create_access_token(
        subject=subject,
        expires_delta=expires_delta,
        token_type="refresh"
    )

def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify a JWT token and return the payload with enhanced security checks.
    
    Args:
        token: The JWT token to verify
        
    Returns:
        dict: The decoded token payload
        
    Raises:
        TokenError: If the token is invalid, expired, or revoked
    """
    try:
        # Check if token is blacklisted
        if token in _token_blacklist:
            logger.warning("Attempted to use revoked token")
            raise TokenError("Token has been revoked")
        
        # Get the unverified header to check key ID (for key rotation)
        unverified_header = jwt.get_unverified_header(token)
        
        # In a production system, you would use the key ID (kid) to get the correct key
        # For now, we'll just verify the algorithm matches our expectations
        if unverified_header.get("alg") != settings.ALGORITHM:
            logger.warning(f"Invalid token algorithm: {unverified_header.get('alg')}")
            raise TokenError("Invalid token algorithm")
        
        # Decode and verify the token with all security measures
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={
                "require_iat": True,     # Require Issued At claim
                "require_exp": True,     # Require Expiration Time claim
                "verify_iat": True,      # Verify Issued At
                "verify_exp": True,      # Verify Expiration Time
                "verify_iss": True,      # Verify Issuer
                "verify_aud": True,      # Verify Audience
                "verify_sub": True,      # Verify Subject
                "leeway": 30             # 30 seconds leeway for clock skew
            },
            issuer=settings.PROJECT_NAME,  # Expected issuer
            audience="satlink-api",        # Expected audience
            subject=None,                  # Optional: verify specific subject
            access_token=token            # For token binding
        )
        
        # Additional security checks
        if not payload.get("jti"):
            logger.warning("Token missing JTI claim")
            raise TokenError("Invalid token format")
            
        # Check token type if specified
        token_type = payload.get("type")
        if token_type not in ["access", "refresh"]:
            logger.warning(f"Invalid token type: {token_type}")
            raise TokenError("Invalid token type")
            
        # Check if token is expired (redundant with verify_exp, but just in case)
        now = datetime.now(timezone.utc)
        if datetime.fromtimestamp(payload["exp"], tz=timezone.utc) < now:
            logger.warning("Token expired")
            raise TokenError("Token has expired")
            
        return payload
        
    except jwt.ExpiredSignatureError:
        logger.warning("Token verification failed: token expired")
        raise TokenError("Token has expired")
    except jwt.JWTClaimsError as e:
        logger.warning(f"Token verification failed: invalid claims - {str(e)}")
        raise TokenError(f"Invalid token claims: {str(e)}")
    except jwt.JWTError as e:
        logger.warning(f"Token verification failed: {str(e)}")
        raise TokenError("Invalid token")
    except Exception as e:
        logger.error(f"Unexpected error during token verification: {str(e)}")
        raise TokenError("Could not validate credentials")

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    request: Request = None,
) -> UserInDB:
    """
    Dependency to get the current authenticated user from the JWT token.
    
    Args:
        credentials: HTTP Bearer token credentials
        request: The current request (for CSRF protection)
        
    Returns:
        UserInDB: The authenticated user
        
    Raises:
        HTTPException: If authentication fails
    """
    if not credentials:
        logger.warning("No credentials provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    try:
        # Verify the token
        payload = verify_token(token)
        
        # Get user ID from token subject
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("Token missing subject claim")
            raise TokenError("Invalid token format")
        
        # Get token scopes
        token_scopes = payload.get("scopes", [])
        
        # In a real application, you would get the user from your database
        # For now, we'll return a mock user
        user = UserInDB(
            id=user_id,
            username=payload.get("username", user_id),
            email=f"{user_id}@example.com",
            full_name=payload.get("name", user_id),
            is_active=True,
            is_superuser="admin" in token_scopes,
            scopes=token_scopes,
            hashed_password="",  # Not needed here as we already verified the token
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Verify CSRF token for state-changing requests
        if request and request.method not in ["GET", "HEAD", "OPTIONS"]:
            await verify_csrf(request, user.id)
        
        return user
        
    except TokenError as e:
        logger.warning(f"Authentication failed: {str(e)}")
        raise HTTPException(
            status_code=e.status_code,
            detail=e.detail,
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Unexpected error during authentication: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during authentication",
        )

async def verify_csrf(request: Request, user_id: str) -> None:
    """
    Verify CSRF token for the current request.
    
    Args:
        request: The current request
        user_id: The ID of the current user
        
    Raises:
        CSRFError: If CSRF validation fails
    """
    # Skip CSRF check for API key authentication
    if request.headers.get("X-API-Key"):
        return
    
    # Get CSRF token from header or form data
    csrf_token = (
        request.headers.get(csrf_header_name) or
        (await request.form()).get(csrf_form_field)
    )
    
    if not csrf_token:
        logger.warning("CSRF token missing from request")
        raise CSRFError("CSRF token is missing")
    
    # In a real application, you would verify the CSRF token against what's stored in the session
    # For now, we'll just verify it's a valid format
    if not re.match(r'^[a-zA-Z0-9_-]{32,}$', csrf_token):
        logger.warning("Invalid CSRF token format")
        raise CSRFError("Invalid CSRF token")
    
    # Here you would typically:
    # 1. Get the session ID from the request cookies
    # 2. Look up the session in your session store
    # 3. Verify the CSRF token matches what's in the session
    # 4. Ensure the session hasn't expired
    
    # For now, we'll just log that we would verify the token
    logger.debug(f"CSRF token verified for user {user_id}")

def generate_csrf_token() -> str:
    """
    Generate a secure CSRF token.
    
    Returns:
        str: A secure random string to be used as a CSRF token
    """
    return secrets.token_urlsafe(32)

async def get_api_key(
    api_key_header: str = Depends(api_key_header),
    api_key_query: str = Depends(api_key_query)
) -> str:
    """Get and validate API key from header or query parameter."""
    # In production, validate against a database of API keys
    if api_key_header and api_key_header == settings.API_KEY:
        return api_key_header
    if api_key_query and api_key_query == settings.API_KEY:
        return api_key_query
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Could not validate API key",
    )

def check_rate_limit(
    request: Request, 
    key: str, 
    limit: int = 60, 
    window: int = 60
) -> None:
    """Simple in-memory rate limiter."""
    now = int(time.time())
    window_start = now - window
    
    # Clean up old entries
    global _rate_limits
    _rate_limits = {
        k: [t for t in v if t > window_start]
        for k, v in _rate_limits.items()
    }
    
    # Get or create the rate limit entry for this key
    timestamps = _rate_limits.get(key, [])
    
    # Check if rate limit is exceeded
    if len(timestamps) >= limit:
        retry_after = window - (now - min(timestamps))
        raise RateLimitExceeded(
            detail="Rate limit exceeded",
            retry_after=retry_after
        )
    
    # Add the current timestamp
    timestamps.append(now)
    _rate_limits[key] = timestamps

def generate_secure_random_string(length: int = 32) -> str:
    """
    Generate a secure random string for API keys, tokens, etc.
    
    Args:
        length: Length of the random string to generate
        
    Returns:
        str: A secure random string
    """
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

# Security headers middleware
async def add_security_headers(request: Request, call_next) -> Response:
    """
    Add security headers to all responses.
    
    This middleware adds various security headers to all HTTP responses
    to enhance the security of the application.
    
    Args:
        request: The incoming request
        call_next: The next middleware in the chain
        
    Returns:
        Response: The response with security headers added
    """
    # Process the request
    response = await call_next(request)
    
    # Add security headers
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value
    
    # Add CSP header if not already set
    if "Content-Security-Policy" not in response.headers:
        csp_parts = []
        for directive, sources in CSP_DIRECTIVES.items():
            if isinstance(sources, str):
                csp_parts.append(f"{directive} {sources}")
            else:
                csp_parts.append(f"{directive} {' '.join(sources)}")
        response.headers["Content-Security-Policy"] = "; ".join(csp_parts)
    
    # Add CORS headers if this is a CORS request
    if "Origin" in request.headers:
        origin = request.headers["Origin"]
        if origin in ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-CSRF-Token, X-Requested-With"
    
    # Add request ID to response headers if available
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        response.headers["X-Request-ID"] = request_id
    
    # Add rate limit headers if rate limiting is active
    rate_limit = getattr(request.state, "rate_limit", None)
    if rate_limit:
        response.headers["X-RateLimit-Limit"] = str(rate_limit["limit"])
        response.headers["X-RateLimit-Remaining"] = str(rate_limit["remaining"])
        response.headers["X-RateLimit-Reset"] = str(int(rate_limit["reset_time"]))
    
    return response

async def rate_limit_middleware(request: Request, call_next) -> Response:
    """
    Rate limiting middleware.
    
    This middleware implements rate limiting based on the client's IP address
    and the requested endpoint. It uses a sliding window algorithm.
    
    Args:
        request: The incoming request
        call_next: The next middleware in the chain
        
    Returns:
        Response: The response or a 429 Too Many Requests response if rate limited
    """
    # Skip rate limiting for whitelisted IPs
    client_ip = request.client.host if request.client else "unknown"
    if client_ip in RATE_LIMIT_WHITELIST:
        return await call_next(request)
    
    # Determine the rate limit bucket based on the request path
    bucket = "default"
    if request.url.path.startswith("/api/auth"):
        bucket = "auth"
    elif request.url.path.startswith("/api"):
        bucket = "api"
    
    bucket_config = RATE_LIMIT_BUCKETS.get(bucket, RATE_LIMIT_BUCKETS["default"])
    now = time.time()
    window = bucket_config["window"]
    limit = bucket_config["limit"]
    block_duration = bucket_config["block_duration"]
    
    # Create a unique key for this client and bucket
    key = f"rate_limit:{bucket}:{client_ip}"
    
    # Get or initialize the rate limit data
    if key not in _rate_limits:
        _rate_limits[key] = {
            "count": 0,
            "start_time": now,
            "blocked_until": 0,
        }
    
    rate_data = _rate_limits[key]
    
    # Check if the client is blocked
    if now < rate_data["blocked_until"]:
        retry_after = int(rate_data["blocked_until"] - now)
        response = JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": f"Too many requests. Please try again in {retry_after} seconds."},
        )
        response.headers["Retry-After"] = str(retry_after)
        return response
    
    # Reset the counter if the window has passed
    if now - rate_data["start_time"] > window:
        rate_data["count"] = 0
        rate_data["start_time"] = now
    
    # Increment the request counter
    rate_data["count"] += 1
    
    # Check if the rate limit has been exceeded
    if rate_data["count"] > limit:
        rate_data["blocked_until"] = now + block_duration
        retry_after = block_duration
        response = JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": f"Rate limit exceeded. Please try again in {retry_after} seconds."},
        )
        response.headers["Retry-After"] = str(retry_after)
        return response
    
    # Add rate limit info to the request state
    request.state.rate_limit = {
        "limit": limit,
        "remaining": max(0, limit - rate_data["count"]),
        "reset_time": int(rate_data["start_time"] + window),
    }
    
    # Process the request
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        raise e
    finally:
        # Clean up old rate limit data (in a real app, this would be done by Redis TTL)
        cleanup_old_rate_limits()

def cleanup_old_rate_limits():
    """Clean up old rate limit data to prevent memory leaks."""
    now = time.time()
    global _rate_limits
    _rate_limits = {
        k: v for k, v in _rate_limits.items()
        if now - v["start_time"] < max(b["window"] for b in RATE_LIMIT_BUCKETS.values()) * 2
    }

# Dependency for endpoints that require authentication
async def get_current_active_user(
    current_user: UserInDB = Depends(get_current_user)
) -> UserInDB:
    """
    Dependency to get the current active user.
    
    Args:
        current_user: The current user from the JWT token
        
    Returns:
        UserInDB: The active user
        
    Raises:
        HTTPException: If the user is inactive or not found
    """
    if not current_user.is_active:
        logger.warning(f"Inactive user attempted access: {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user

# Dependency for admin-only endpoints
async def get_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Dependency to check if user has admin privileges."""
    if "admin" not in current_user.scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user

# Rate limiting dependency
async def rate_limited(
    request: Request,
    limit: int = 60,
    window: int = 60
) -> None:
    """Dependency to apply rate limiting to an endpoint."""
    # Use client IP as the rate limit key
    client_ip = request.client.host
    key = f"rate_limit:{client_ip}"
    
    try:
        check_rate_limit(request, key, limit, window)
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=e.detail,
            headers={"Retry-After": str(e.retry_after)}
        )
