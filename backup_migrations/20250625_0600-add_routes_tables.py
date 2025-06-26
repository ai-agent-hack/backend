"""Add routes tables for multi-day route optimization

Revision ID: add_routes_tables_001
Revises: a5003a65d3f8
Create Date: 2025-06-25 06:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "add_routes_tables_001"
down_revision = "a5003a65d3f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema - Add routes tables."""

    # 1. Create routes table (메인 경로 정보)
    op.create_table(
        "routes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.String(length=50), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        # 여행 기본 정보
        sa.Column("total_days", sa.Integer(), nullable=False),
        sa.Column("departure_location", sa.String(length=200), nullable=True),
        sa.Column("hotel_location", sa.String(length=200), nullable=True),
        # 전체 경로 요약
        sa.Column("total_distance_km", sa.DECIMAL(precision=8, scale=2), nullable=True),
        sa.Column("total_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("total_spots_count", sa.Integer(), nullable=True),
        # 메타데이터
        sa.Column(
            "calculated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "google_maps_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["plan_id", "version"],
            ["rec_plan.plan_id", "rec_plan.version"],
            name="fk_routes_plan_version",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "version", name="uq_routes_plan_version"),
    )

    # 2. Create route_days table (일차별 경로)
    op.create_table(
        "route_days",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("route_id", sa.Integer(), nullable=False),
        sa.Column("day_number", sa.Integer(), nullable=False),
        # 일차별 경로 정보
        sa.Column("start_location", sa.String(length=200), nullable=True),
        sa.Column("end_location", sa.String(length=200), nullable=True),
        sa.Column("day_distance_km", sa.DECIMAL(precision=8, scale=2), nullable=True),
        sa.Column("day_duration_minutes", sa.Integer(), nullable=True),
        # 일차별 경로 순서 (TSP 결과)
        sa.Column(
            "ordered_spots", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "route_geometry", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["route_id"],
            ["routes.id"],
            ondelete="CASCADE",
            name="fk_route_days_route_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("route_id", "day_number", name="uq_route_days_route_day"),
    )

    # 3. Create route_segments table (구간별 상세 정보)
    op.create_table(
        "route_segments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("route_day_id", sa.Integer(), nullable=False),
        sa.Column("segment_order", sa.Integer(), nullable=False),
        # 구간 정보
        sa.Column("from_location", sa.String(length=200), nullable=True),
        sa.Column("to_spot_id", sa.String(length=100), nullable=True),
        sa.Column("to_spot_name", sa.String(length=200), nullable=True),
        # 이동 정보
        sa.Column("distance_meters", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "travel_mode",
            sa.String(length=20),
            nullable=False,
            server_default="DRIVING",
        ),
        # 상세 경로 안내
        sa.Column(
            "directions_steps", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["route_day_id"],
            ["route_days.id"],
            ondelete="CASCADE",
            name="fk_route_segments_route_day_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # 4. Create indexes for performance
    op.create_index(op.f("ix_routes_id"), "routes", ["id"], unique=False)
    op.create_index(
        "idx_routes_plan_version", "routes", ["plan_id", "version"], unique=False
    )

    op.create_index(op.f("ix_route_days_id"), "route_days", ["id"], unique=False)
    op.create_index(
        "idx_route_days_route_id",
        "route_days",
        ["route_id", "day_number"],
        unique=False,
    )

    op.create_index(
        op.f("ix_route_segments_id"), "route_segments", ["id"], unique=False
    )
    op.create_index(
        "idx_route_segments_day_order",
        "route_segments",
        ["route_day_id", "segment_order"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade database schema - Drop routes tables."""

    # Drop indexes first
    op.drop_index("idx_route_segments_day_order", table_name="route_segments")
    op.drop_index(op.f("ix_route_segments_id"), table_name="route_segments")

    op.drop_index("idx_route_days_route_id", table_name="route_days")
    op.drop_index(op.f("ix_route_days_id"), table_name="route_days")

    op.drop_index("idx_routes_plan_version", table_name="routes")
    op.drop_index(op.f("ix_routes_id"), table_name="routes")

    # Drop tables in reverse order (due to foreign key dependencies)
    op.drop_table("route_segments")
    op.drop_table("route_days")
    op.drop_table("routes")
