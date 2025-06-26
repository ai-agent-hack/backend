"""Add firebase_uid to user model

Revision ID: 6a4c1503d8f1
Revises:
Create Date: 2025-06-16 07:09:34.995568+00:00

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "6a4c1503d8f1"
down_revision = "initial_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Add firebase_uid column (initially nullable to allow migration)
    op.add_column("users", sa.Column("firebase_uid", sa.String(), nullable=True))

    # Create unique index for firebase_uid
    op.create_index("idx_user_firebase_uid", "users", ["firebase_uid"], unique=True)

    # NOTE: After adding firebase_uid values, you should make it NOT NULL
    # op.alter_column("users", "firebase_uid", nullable=False)


def downgrade() -> None:
    """Downgrade database schema."""
    # Remove firebase_uid index
    op.drop_index("idx_user_firebase_uid", table_name="users")

    # Remove firebase_uid column
    op.drop_column("users", "firebase_uid")
