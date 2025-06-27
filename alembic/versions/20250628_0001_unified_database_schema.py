"""Unified database schema - all tables with final structure

Revision ID: 20250628_0001
Revises:
Create Date: 2025-06-28 00:01:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20250628_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables with final structure."""

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("firebase_uid", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_user_email_active", "users", ["email", "is_active"], unique=False
    )
    op.create_index("idx_user_firebase_uid", "users", ["firebase_uid"], unique=False)
    op.create_index(
        "idx_user_username_active", "users", ["username", "is_active"], unique=False
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(
        op.f("ix_users_firebase_uid"), "users", ["firebase_uid"], unique=True
    )
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    # Create pre_infos table (WITHOUT departure_location)
    op.create_table(
        "pre_infos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.DateTime(), nullable=False),
        sa.Column("end_date", sa.DateTime(), nullable=False),
        sa.Column("atmosphere", sa.Text(), nullable=False),
        sa.Column("budget", sa.Integer(), nullable=False),
        sa.Column(
            "participants_count", sa.Integer(), server_default="2", nullable=False
        ),
        sa.Column("region", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_pre_info_budget", "pre_infos", ["budget"], unique=False)
    op.create_index(
        "idx_pre_info_dates", "pre_infos", ["start_date", "end_date"], unique=False
    )
    op.create_index("idx_pre_info_region", "pre_infos", ["region"], unique=False)
    op.create_index("idx_pre_info_user_id", "pre_infos", ["user_id"], unique=False)
    op.create_index(op.f("ix_pre_infos_id"), "pre_infos", ["id"], unique=False)
    op.create_index(
        op.f("ix_pre_infos_user_id"), "pre_infos", ["user_id"], unique=False
    )

    # Create rec_plan table
    op.create_table(
        "rec_plan",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.String(length=50), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("pre_info_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["pre_info_id"],
            ["pre_infos.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_rec_plan_plan_id", "rec_plan", ["plan_id"], unique=False)
    op.create_index(
        "idx_rec_plan_version", "rec_plan", ["plan_id", "version"], unique=True
    )
    op.create_index(op.f("ix_rec_plan_id"), "rec_plan", ["id"], unique=False)

    # Create rec_spot table
    op.create_table(
        "rec_spot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.String(length=50), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("spot_id", sa.String(length=100), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("similarity_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("time_slot", sa.String(length=10), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=10, scale=8), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=11, scale=8), nullable=True),
        sa.Column("spot_name", sa.String(length=200), nullable=True),
        sa.Column("spot_details", sa.JSON(), nullable=True),
        sa.Column("recommendation_reason", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("website_url", sa.Text(), nullable=True),
        sa.Column("selected", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_rec_spot_plan_version", "rec_spot", ["plan_id", "version"], unique=False
    )
    op.create_index(
        "idx_rec_spot_rank", "rec_spot", ["plan_id", "version", "rank"], unique=False
    )
    op.create_index("idx_rec_spot_status", "rec_spot", ["status"], unique=False)
    op.create_index(
        "idx_rec_spot_time_slot",
        "rec_spot",
        ["plan_id", "version", "time_slot"],
        unique=False,
    )
    op.create_index(op.f("ix_rec_spot_id"), "rec_spot", ["id"], unique=False)

    # Create routes table
    op.create_table(
        "routes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.String(length=50), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("total_days", sa.Integer(), nullable=False),
        sa.Column("departure_location", sa.String(length=200), nullable=True),
        sa.Column("hotel_location", sa.String(length=200), nullable=True),
        sa.Column("total_distance_km", sa.DECIMAL(precision=8, scale=2), nullable=True),
        sa.Column("total_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("total_spots_count", sa.Integer(), nullable=True),
        sa.Column("calculated_at", sa.DateTime(), nullable=False),
        sa.Column(
            "google_maps_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "version", name="uq_routes_plan_version"),
    )
    op.create_index(
        "idx_routes_plan_version", "routes", ["plan_id", "version"], unique=False
    )
    op.create_index(op.f("ix_routes_id"), "routes", ["id"], unique=False)

    # Create route_days table (WITH CASCADE DELETE)
    op.create_table(
        "route_days",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("route_id", sa.Integer(), nullable=False),
        sa.Column("day_number", sa.Integer(), nullable=False),
        sa.Column("start_location", sa.String(length=200), nullable=True),
        sa.Column("end_location", sa.String(length=200), nullable=True),
        sa.Column("day_distance_km", sa.DECIMAL(precision=8, scale=2), nullable=True),
        sa.Column("day_duration_minutes", sa.Integer(), nullable=True),
        sa.Column(
            "ordered_spots", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "route_geometry", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("route_id", "day_number", name="uq_route_days_route_day"),
    )
    op.create_index(
        "idx_route_days_route_id",
        "route_days",
        ["route_id", "day_number"],
        unique=False,
    )
    op.create_index(op.f("ix_route_days_id"), "route_days", ["id"], unique=False)

    # Create route_segments table (WITH CASCADE DELETE)
    op.create_table(
        "route_segments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("route_day_id", sa.Integer(), nullable=False),
        sa.Column("segment_order", sa.Integer(), nullable=False),
        sa.Column("from_location", sa.String(length=200), nullable=True),
        sa.Column("to_spot_id", sa.String(length=100), nullable=True),
        sa.Column("to_spot_name", sa.String(length=200), nullable=True),
        sa.Column("distance_meters", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("travel_mode", sa.String(length=20), nullable=False),
        sa.Column(
            "directions_steps", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["route_day_id"], ["route_days.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_route_segments_day_order",
        "route_segments",
        ["route_day_id", "segment_order"],
        unique=False,
    )
    op.create_index(
        op.f("ix_route_segments_id"), "route_segments", ["id"], unique=False
    )


def downgrade() -> None:
    """Drop all tables."""
    op.drop_index(op.f("ix_route_segments_id"), table_name="route_segments")
    op.drop_index("idx_route_segments_day_order", table_name="route_segments")
    op.drop_table("route_segments")

    op.drop_index(op.f("ix_route_days_id"), table_name="route_days")
    op.drop_index("idx_route_days_route_id", table_name="route_days")
    op.drop_table("route_days")

    op.drop_index(op.f("ix_routes_id"), table_name="routes")
    op.drop_index("idx_routes_plan_version", table_name="routes")
    op.drop_table("routes")

    op.drop_index(op.f("ix_rec_spot_id"), table_name="rec_spot")
    op.drop_index("idx_rec_spot_time_slot", table_name="rec_spot")
    op.drop_index("idx_rec_spot_status", table_name="rec_spot")
    op.drop_index("idx_rec_spot_rank", table_name="rec_spot")
    op.drop_index("idx_rec_spot_plan_version", table_name="rec_spot")
    op.drop_table("rec_spot")

    op.drop_index(op.f("ix_rec_plan_id"), table_name="rec_plan")
    op.drop_index("idx_rec_plan_version", table_name="rec_plan")
    op.drop_index("idx_rec_plan_plan_id", table_name="rec_plan")
    op.drop_table("rec_plan")

    op.drop_index(op.f("ix_pre_infos_user_id"), table_name="pre_infos")
    op.drop_index(op.f("ix_pre_infos_id"), table_name="pre_infos")
    op.drop_index("idx_pre_info_user_id", table_name="pre_infos")
    op.drop_index("idx_pre_info_region", table_name="pre_infos")
    op.drop_index("idx_pre_info_dates", table_name="pre_infos")
    op.drop_index("idx_pre_info_budget", table_name="pre_infos")
    op.drop_table("pre_infos")

    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_index(op.f("ix_users_firebase_uid"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_index("idx_user_username_active", table_name="users")
    op.drop_index("idx_user_firebase_uid", table_name="users")
    op.drop_index("idx_user_email_active", table_name="users")
    op.drop_table("users")
