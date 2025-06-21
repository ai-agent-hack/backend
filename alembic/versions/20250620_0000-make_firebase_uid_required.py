"""Make firebase_uid required and add final indexes

Revision ID: make_firebase_uid_required
Revises: fdba04d79a97
Create Date: 2025-06-20 00:00:00.000000+00:00

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "make_firebase_uid_required"
down_revision = "fdba04d79a97"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Make firebase_uid NOT NULL and add final indexes."""
    # Make firebase_uid NOT NULL (assumes all users have firebase_uid by now)
    op.alter_column("users", "firebase_uid", nullable=False)

    # Add additional indexes for performance (matching current User model)
    op.create_index(
        "idx_user_email_active", "users", ["email", "is_active"], unique=False
    )
    op.create_index(
        "idx_user_username_active", "users", ["username", "is_active"], unique=False
    )


def downgrade() -> None:
    """Make firebase_uid nullable and remove indexes."""
    # Remove additional indexes
    op.drop_index("idx_user_username_active", table_name="users")
    op.drop_index("idx_user_email_active", table_name="users")

    # Make firebase_uid nullable
    op.alter_column("users", "firebase_uid", nullable=True)
