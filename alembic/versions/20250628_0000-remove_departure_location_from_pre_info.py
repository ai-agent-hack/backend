"""Remove departure_location from pre_infos table

Revision ID: 20250628_0000
Revises: cd495f22435e
Create Date: 2025-06-28 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250628_0000"
down_revision = "cd495f22435e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove departure_location column from pre_infos table"""
    op.drop_column("pre_infos", "departure_location")


def downgrade() -> None:
    """Add back departure_location column to pre_infos table"""
    op.add_column(
        "pre_infos",
        sa.Column("departure_location", sa.String(length=200), nullable=True),
    )
    # Fill with default values to avoid constraint issues
    op.execute(
        "UPDATE pre_infos SET departure_location = 'Seoul' WHERE departure_location IS NULL"
    )
    # Make it non-nullable
    op.alter_column("pre_infos", "departure_location", nullable=False)
