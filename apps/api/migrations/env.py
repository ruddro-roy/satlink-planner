"""Alembic environment configuration file.

This minimal *env.py* allows Alembic to discover the application's SQLAlchemy
metadata so that autogeneration as well as offline/online migrations work.
"""
from __future__ import annotations

import logging.config
import os
import sys
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# ---------------------------------------------------------------------------
# Ensure project root is on PYTHONPATH so `core` and `domain` modules resolve.
# ---------------------------------------------------------------------------
# env.py lives in apps/api/migrations
PROJECT_ROOT = Path(__file__).resolve().parents[3]  # project root
sys.path.append(str(PROJECT_ROOT / "apps" / "api"))
sys.path.append(str(PROJECT_ROOT))

# Import metadata AFTER path manipulation
from core.db import Base  # noqa: E402
from core.config import settings  # noqa: E402

# Import models so that their tables are linked to Base.metadata
from domain import models  # noqa: F401, E402  pylint: disable=unused-import

# ---------------------------------------------------------------------------
# Alembic Config object
# ---------------------------------------------------------------------------
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    logging.config.fileConfig(config.config_file_name)

# Provide metadata object for 'autogenerate'

target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_url() -> str:
    """Return the database URL from the application settings."""
    return settings.DATABASE_URL


def run_migrations_offline() -> None:
    """Run migrations in *offline* mode."""
    context.configure(url=get_url(), target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in *online* mode."""
    connectable = engine_from_config(
        {**config.get_section(config.config_ini_section), "sqlalchemy.url": get_url()},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

