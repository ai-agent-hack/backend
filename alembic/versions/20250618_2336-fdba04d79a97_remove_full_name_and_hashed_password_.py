"""Remove full_name and hashed_password columns

Revision ID: fdba04d79a97
Revises: 6a4c1503d8f1
Create Date: 2025-06-18 23:36:34.447635+00:00

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "fdba04d79a97"
down_revision = "6a4c1503d8f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Remove full_name column
    op.drop_column("users", "full_name")

    # Remove hashed_password column
    op.drop_column("users", "hashed_password")


def downgrade() -> None:
    """Downgrade database schema."""
    # Add back hashed_password column
    op.add_column("users", sa.Column("hashed_password", sa.VARCHAR(), nullable=True))

    # Add back full_name column
    op.add_column(
        "users", sa.Column("full_name", sa.VARCHAR(length=100), nullable=True)
    )
