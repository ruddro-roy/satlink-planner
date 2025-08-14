"""
Database configuration and session management for the SatLink Digital Twin API.

This module provides:
- Async database session management
- Connection pooling
- Database initialization and migrations
- Security best practices for database access
"""
import logging
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator, Optional, Type, TypeVar, Any

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine, 
    AsyncSession, 
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.orm import sessionmaker, Session, declarative_base, scoped_session
from sqlalchemy.pool import QueuePool

from core.config import settings, get_settings
from core.logging import get_logger

# Configure logger
logger = get_logger(__name__)

# Type variables
T = TypeVar('T', bound=Any)

# Determine if we're using SQLite (for connection args)
IS_SQLITE = settings.DATABASE_URL.startswith("sqlite")

# Connection pool settings
POOL_SIZE = 5
MAX_OVERFLOW = 10
POOL_TIMEOUT = 30
POOL_RECYCLE = 3600  # Recycle connections after 1 hour
POOL_PRE_PING = True  # Enable connection health checks

# Common engine parameters
engine_params = {
    "poolclass": QueuePool,
    "pool_size": POOL_SIZE,
    "max_overflow": MAX_OVERFLOW,
    "pool_timeout": POOL_TIMEOUT,
    "pool_recycle": POOL_RECYCLE,
    "pool_pre_ping": POOL_PRE_PING,
    "echo": settings.DEBUG,  # Echo SQL queries in debug mode
    "future": True,  # Use SQLAlchemy 2.0 style
}

# Configure SQLite specific settings
if IS_SQLITE:
    # Enable WAL mode for better concurrency
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    
    # SQLite specific connection args
    connect_args = {"check_same_thread": False, "timeout": 30.0}
else:
    # PostgreSQL/other database connection args
    connect_args = {}

# Create sync engine (for migrations and sync operations)
sync_engine = create_engine(
    settings.DATABASE_URL,
    **engine_params,
    connect_args=connect_args
)

# Create async engine (for async operations)
async_engine: Optional[AsyncEngine] = None
if not IS_SQLITE and settings.DATABASE_URL.startswith("postgresql"):
    # Convert to asyncpg URL format
    async_db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    async_engine = create_async_engine(
        async_db_url,
        **engine_params,
        connect_args=connect_args
    )

# Session factories
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=sync_engine,
    expire_on_commit=False
)

AsyncSessionLocal = None
if async_engine:
    AsyncSessionLocal = async_sessionmaker(
        bind=async_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        class_=AsyncSession
    )

# Base class for models
Base = declarative_base()

# Dependency for sync database session
@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Dependency function that yields a database session.
    
    This should be used in FastAPI path operations that require database access.
    The session is automatically closed when the request is finished.
    
    Example:
        @app.get("/items/{item_id}")
        def read_item(item_id: int, db: Session = Depends(get_db)):
            return db.query(Item).filter(Item.id == item_id).first()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Dependency for async database session
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async dependency that yields a database session.
    
    This should be used in FastAPI path operations that require async database access.
    The session is automatically closed when the request is finished.
    
    Example:
        @app.get("/items/{item_id}")
        async def read_item(item_id: int, db: AsyncSession = Depends(get_async_db)):
            result = await db.execute(select(Item).filter(Item.id == item_id))
            return result.scalars().first()
    """
    if not AsyncSessionLocal:
        raise RuntimeError("Async database session not available. Check your database configuration.")
    
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database error: {str(e)}", exc_info=True)
            raise
        finally:
            await session.close()

# Database initialization
async def init_db():
    """
    Initialize the database by creating all tables.
    
    In a production environment, you should use migrations (Alembic) instead.
    This is only for development and testing purposes.
    """
    from domain import models  # noqa: F401 Import models to ensure they are registered with SQLAlchemy
    
    logger.info("Initializing database...")
    
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}", exc_info=True)
        raise

# Database health check
async def check_db_connection() -> bool:
    """Check if the database is accessible."""
    try:
        if async_engine:
            async with async_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        else:
            with sync_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {str(e)}")
        return False

# Transaction management
@asynccontextmanager
async def transaction() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database transactions.
    
    Example:
        async with transaction() as db:
            db.add(some_object)
            await db.commit()
    """
    if not AsyncSessionLocal:
        raise RuntimeError("Async database session not available.")
    
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Utility functions
def get_or_create(session: Session, model: Type[T], **kwargs) -> T:
    """Get an instance of the model or create it if it doesn't exist."""
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance
    else:
        instance = model(**kwargs)
        session.add(instance)
        return instance
