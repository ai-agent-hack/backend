"""Initial baseline migration

Revision ID: 20250628_0000
Revises:
Create Date: 2025-06-28 00:00:00.000000

This is a baseline (empty) migration whose purpose is to anchor the migration
history when deploying to environments that still hold the old revision
"20250628_0000".  It performs no schema changes.
"""

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

# revision identifiers, used by Alembic.
revision = "20250628_0000"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Baseline upgrade – no-op."""
    pass


def downgrade():
    """Baseline downgrade – no-op."""
    pass
