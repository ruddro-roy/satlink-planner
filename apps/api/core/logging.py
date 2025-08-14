"""
Logging configuration for the SatLink Digital Twin API.

This module provides a centralized logging configuration with support for:
- Structured JSON logging in production
- Human-readable console output in development
- File-based logging with rotation
- Correlation IDs for request tracing
- Integration with FastAPI's request context
"""
import logging
import logging.config
import logging.handlers
import os
import sys
import json
from typing import Any, Dict, Optional, Union, cast
from pathlib import Path
import uuid
from datetime import datetime

from fastapi import Request, Response

class RequestIdFilter(logging.Filter):
    """Add request_id to log records if available in the request state."""
    def __init__(self, name: str = "") -> None:
        super().__init__(name)
        self.request_id = ""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = self.request_id or "system"  # type: ignore
        return True

class JsonFormatter(logging.Formatter):
    """
    Format log records as JSON for structured logging.
    
    In production, logs are emitted as JSON for easier parsing by log aggregation
    systems. In development, a more human-readable format is used.
    """
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.is_prod = os.getenv("ENVIRONMENT", "development").lower() == "production"
        super().__init__(*args, **kwargs)

    def format(self, record: logging.LogRecord) -> str:
        if not self.is_prod:
            return super().format(record)
            
        log_record: Dict[str, Any] = {
            "timestamp": f"{datetime.utcnow().isoformat()}Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "system"),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_record, ensure_ascii=False)

def setup_logging() -> None:
    """
    Configure logging for the application.
    
    Sets up console and file handlers with appropriate formatters
    based on the environment (development/production).
    """
    from core.config import settings
    
    # Create logs directory if it doesn't exist
    logs_dir = Path(__file__).parent.parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # Base logging configuration
    log_config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "core.logging.JsonFormatter",
                "fmt": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "console": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "file": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "DEBUG",
                "formatter": "console",
                "stream": "ext://sys.stdout"
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "file",
                "filename": str(logs_dir / "satlink.log"),
                "maxBytes": 10 * 1024 * 1024,  # 10MB
                "backupCount": 5,
                "encoding": "utf-8"
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "WARNING",
                "formatter": "file",
                "filename": str(logs_dir / "error.log"),
                "maxBytes": 10 * 1024 * 1024,  # 10MB
                "backupCount": 5,
                "encoding": "utf-8"
            }
        },
        "loggers": {
            "": {  # root logger
                "handlers": ["console", "file", "error_file"],
                "level": settings.LOG_LEVEL,
                "propagate": False
            },
            "uvicorn": {
                "handlers": ["console", "file"],
                "level": "INFO",
                "propagate": False
            },
            "uvicorn.error": {
                "handlers": ["console", "error_file"],
                "level": "WARNING",
                "propagate": False
            },
            "sqlalchemy": {
                "handlers": ["console", "file"],
                "level": "WARNING",
                "propagate": False
            },
            "aiosqlite": {
                "handlers": ["console", "file"],
                "level": "WARNING",
                "propagate": False
            }
        }
    }
    
    # Apply the configuration
    logging.config.dictConfig(log_config)
    
    # Set log level for all loggers
    for logger_name in logging.root.manager.loggerDict:  # type: ignore
        logger = logging.getLogger(logger_name)
        logger.setLevel(settings.LOG_LEVEL)
    
    # Add request ID filter to root logger
    request_id_filter = RequestIdFilter()
    for handler in logging.root.handlers:
        handler.addFilter(request_id_filter)
    
    # Configure uvicorn logging
    logging.getLogger("uvicorn.access").handlers = logging.root.handlers
    logging.getLogger("uvicorn.error").handlers = logging.root.handlers

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: The name of the logger. If None, returns the root logger.
        
    Returns:
        A configured logger instance.
    """
    return logging.getLogger(name)

def log_request(request: Request, response: Optional[Response] = None, error: Optional[Exception] = None) -> None:
    """
    Log an HTTP request with its response or error.
    
    Args:
        request: The FastAPI Request object.
        response: The FastAPI Response object (if successful).
        error: Any exception that occurred during request processing.
    """
    logger = get_logger("http")
    
    # Generate a unique request ID if not present
    request_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    setattr(request.state, "correlation_id", request_id)
    
    # Set request ID in thread-local storage for logging
    for handler in logging.root.handlers:  # type: ignore
        for filter_item in handler.filters:
            if isinstance(filter_item, RequestIdFilter):
                filter_item.request_id = request_id
    
    # Log the request
    client_host = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    if error:
        status_code = getattr(error, "status_code", 500)
        logger.error(
            "Request failed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "client": client_host,
                "user_agent": user_agent,
                "status_code": status_code,
                "error": str(error)
            }
        )
    elif response:
        response_size = len(response.body) if hasattr(response, "body") else 0
        logger.info(
            "Request processed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "client": client_host,
                "user_agent": user_agent,
                "status_code": response.status_code,
                "response_size": response_size
            }
        )
    else:
        logger.info(
            "Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "client": client_host,
                "user_agent": user_agent
            }
        )
