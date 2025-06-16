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
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Add firebase_uid column
    op.add_column("users", sa.Column("firebase_uid", sa.String(), nullable=True))

    # Make hashed_password nullable
    op.alter_column("users", "hashed_password", nullable=True)

    # Create index for firebase_uid
    op.create_index("idx_user_firebase_uid", "users", ["firebase_uid"], unique=False)

    # Update firebase_uid to be unique (after data migration if needed)
    # For now, we'll leave it as non-unique to allow migration
    # op.create_unique_constraint('uq_users_firebase_uid', 'users', ['firebase_uid'])


def downgrade() -> None:
    """Downgrade database schema."""
    # Remove firebase_uid index
    op.drop_index("idx_user_firebase_uid", table_name="users")

    # Make hashed_password not nullable
    op.alter_column("users", "hashed_password", nullable=False)

    # Remove firebase_uid column
    op.drop_column("users", "firebase_uid")
