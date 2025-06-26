"""add_spot_details_to_rec_spot_table

Revision ID: a5003a65d3f8
Revises: 60045f7b5de9
Create Date: 2025-06-25 05:43:38.626002+00:00

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a5003a65d3f8"
down_revision = "60045f7b5de9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Add spot details columns to rec_spot table
    op.add_column("rec_spot", sa.Column("time_slot", sa.String(10), nullable=True))
    op.add_column("rec_spot", sa.Column("latitude", sa.Numeric(10, 8), nullable=True))
    op.add_column("rec_spot", sa.Column("longitude", sa.Numeric(11, 8), nullable=True))
    op.add_column("rec_spot", sa.Column("spot_name", sa.String(200), nullable=True))
    op.add_column("rec_spot", sa.Column("spot_details", sa.JSON(), nullable=True))
    op.add_column(
        "rec_spot", sa.Column("recommendation_reason", sa.Text(), nullable=True)
    )
    op.add_column("rec_spot", sa.Column("image_url", sa.Text(), nullable=True))
    op.add_column("rec_spot", sa.Column("website_url", sa.Text(), nullable=True))
    op.add_column(
        "rec_spot", sa.Column("selected", sa.Boolean(), nullable=True, default=False)
    )

    # Add indexes for performance
    op.create_index(
        "idx_rec_spot_time_slot", "rec_spot", ["plan_id", "version", "time_slot"]
    )


def downgrade() -> None:
    """Downgrade database schema."""
    # Drop indexes
    op.drop_index("idx_rec_spot_time_slot", "rec_spot")

    # Drop columns
    op.drop_column("rec_spot", "selected")
    op.drop_column("rec_spot", "website_url")
    op.drop_column("rec_spot", "image_url")
    op.drop_column("rec_spot", "recommendation_reason")
    op.drop_column("rec_spot", "spot_details")
    op.drop_column("rec_spot", "spot_name")
    op.drop_column("rec_spot", "longitude")
    op.drop_column("rec_spot", "latitude")
    op.drop_column("rec_spot", "time_slot")
