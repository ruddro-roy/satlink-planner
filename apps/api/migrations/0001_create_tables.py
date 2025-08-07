"""Initial DB schema for SatLink Planner.

Revision ID: 0001_create_tables
Revises: 
Create Date: 2025-08-07
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision = "0001_create_tables"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    """Apply the migration – create all tables defined in SQLAlchemy models."""
    # Rather than manually recreating each table, we reuse the SQLAlchemy
    # metadata. This keeps Alembic scripts simple while the schema is young.
    from core.db import Base  # pylint: disable=import-error
    from domain import models  # noqa: F401  # ensure all models imported

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    """Revert the migration – drop all tables."""
    from core.db import Base  # pylint: disable=import-error

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)

