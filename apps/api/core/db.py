"""Database utilities (engine, session maker, migrations helpers).

This file centralises SQLAlchemy and Alembic primitives so they can be
imported both by the application code and by Alembic's env.py.
"""
from __future__ import annotations

import os
import subprocess
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from core.config import settings

# ---------------------------------------------------------------------------
# SQLAlchemy engine / session
# ---------------------------------------------------------------------------

# NOTE: SQLite needs the ``check_same_thread`` flag for multithreaded usage
connect_args = (
    {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
)

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative base that will be shared across all models
Base = declarative_base()


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Helper functions for DB initialisation
# ---------------------------------------------------------------------------

def create_all() -> None:
    """Create all tables (development convenience function).

    This should only be executed in *development* environments. In any other
    environment the app should rely on Alembic migrations instead.
    """
    # Importing models ensures they are registered on the Base metadata before
    # ``create_all`` is invoked.
    from domain import models  # noqa: F401  # pylint: disable=unused-import

    print("[DB] Creating all tables via SQLAlchemy metadata …")
    Base.metadata.create_all(bind=engine)
    print("[DB] Tables created.")


def run_migrations() -> None:
    """Run Alembic migrations up to *head*.

    This is intended for *non-development* environments and mirrors the logic
    performed in Docker / CI. The function shells out to the *alembic* CLI for
    simplicity.
    """
    print("[DB] Running Alembic migrations …")
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    print("[DB] Alembic migrations completed.")

