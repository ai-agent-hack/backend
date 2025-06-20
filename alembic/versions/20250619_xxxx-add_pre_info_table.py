"""Add pre_info table

Revision ID: 20250619xxxx
Revises: fdba04d79a97
Create Date: 2025-06-19 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "add_pre_info_001"
down_revision = "fdba04d79a97"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Create pre_infos table
    op.create_table(
        "pre_infos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("departure_location", sa.String(length=200), nullable=False),
        sa.Column("start_date", sa.DateTime(), nullable=False),
        sa.Column("end_date", sa.DateTime(), nullable=False),
        sa.Column("atmosphere", sa.Text(), nullable=False),
        sa.Column("budget", sa.Integer(), nullable=False),
        sa.Column("region", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("idx_pre_info_budget", "budget"),
        sa.Index("idx_pre_info_dates", "start_date", "end_date"),
        sa.Index("idx_pre_info_region", "region"),
        sa.Index("idx_pre_info_user_id", "user_id"),
    )
    # Create index for id column
    op.create_index(op.f("ix_pre_infos_id"), "pre_infos", ["id"], unique=False)


def downgrade() -> None:
    """Downgrade database schema."""
    # Drop indexes
    op.drop_index(op.f("ix_pre_infos_id"), table_name="pre_infos")
    op.drop_index("idx_pre_info_user_id", table_name="pre_infos")
    op.drop_index("idx_pre_info_region", table_name="pre_infos")
    op.drop_index("idx_pre_info_dates", table_name="pre_infos")
    op.drop_index("idx_pre_info_budget", table_name="pre_infos")

    # Drop table
    op.drop_table("pre_infos")
