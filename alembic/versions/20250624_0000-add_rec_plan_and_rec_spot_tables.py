"""Add rec_plan and rec_spot tables

Revision ID: add_rec_tables_001
Revises: add_participants_count_to_pre_info_safe
Create Date: 2025-06-24 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "add_rec_tables_001"
down_revision = "add_participants_safe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema."""

    # Create rec_plan table
    op.create_table(
        "rec_plan",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.String(length=50), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("pre_info_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.ForeignKeyConstraint(
            ["pre_info_id"],
            ["pre_infos.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for rec_plan
    op.create_index(op.f("ix_rec_plan_id"), "rec_plan", ["id"], unique=False)
    op.create_index("idx_rec_plan_plan_id", "rec_plan", ["plan_id"], unique=False)
    op.create_index(
        "idx_rec_plan_version", "rec_plan", ["plan_id", "version"], unique=True
    )

    # Create rec_spot table
    op.create_table(
        "rec_spot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.String(length=50), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("spot_id", sa.String(length=100), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),  # ADD/KEEP/DEL
        sa.Column("similarity_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for rec_spot
    op.create_index(op.f("ix_rec_spot_id"), "rec_spot", ["id"], unique=False)
    op.create_index(
        "idx_rec_spot_plan_version", "rec_spot", ["plan_id", "version"], unique=False
    )
    op.create_index("idx_rec_spot_status", "rec_spot", ["status"], unique=False)
    op.create_index(
        "idx_rec_spot_rank", "rec_spot", ["plan_id", "version", "rank"], unique=False
    )


def downgrade() -> None:
    """Downgrade database schema."""

    # Drop rec_spot table and indexes
    op.drop_index("idx_rec_spot_rank", table_name="rec_spot")
    op.drop_index("idx_rec_spot_status", table_name="rec_spot")
    op.drop_index("idx_rec_spot_plan_version", table_name="rec_spot")
    op.drop_index(op.f("ix_rec_spot_id"), table_name="rec_spot")
    op.drop_table("rec_spot")

    # Drop rec_plan table and indexes
    op.drop_index("idx_rec_plan_version", table_name="rec_plan")
    op.drop_index("idx_rec_plan_plan_id", table_name="rec_plan")
    op.drop_index(op.f("ix_rec_plan_id"), table_name="rec_plan")
    op.drop_table("rec_plan")
