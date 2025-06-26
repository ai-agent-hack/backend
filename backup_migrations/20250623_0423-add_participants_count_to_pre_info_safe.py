"""add_participants_count_to_pre_info_safe

Revision ID: add_participants_safe
Revises: add_pre_info_001
Create Date: 2025-06-23 04:23:00.000000+00:00

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "add_participants_safe"
down_revision = "add_pre_info_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Step 1: Add column with default value (nullable first)
    op.add_column(
        "pre_infos",
        sa.Column("participants_count", sa.Integer(), nullable=True, default=2),
    )

    # Step 2: Update all existing records with default value
    op.execute(
        "UPDATE pre_infos SET participants_count = 2 WHERE participants_count IS NULL"
    )

    # Step 3: Make the column NOT NULL
    op.alter_column("pre_infos", "participants_count", nullable=False)


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_column("pre_infos", "participants_count")
