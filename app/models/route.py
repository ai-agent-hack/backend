from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    DECIMAL,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from typing import List, Optional, Dict, Any
from decimal import Decimal

from app.models.base import Base


class Route(Base):
    """
    Route model representing optimized travel routes for trip plans.
    Follows Single Responsibility Principle - only handles route optimization data.
    """

    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plan_id: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    # 여행 기본 정보
    total_days: Mapped[int] = mapped_column(Integer, nullable=False)
    departure_location: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True
    )
    hotel_location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # 전체 경로 요약
    total_distance_km: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(precision=8, scale=2), nullable=True
    )
    total_duration_minutes: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    total_spots_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 메타데이터
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    google_maps_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )

    # Override Base's created_at and updated_at (Route uses calculated_at instead)
    created_at = None
    updated_at = None

    # Relationships
    route_days: Mapped[List["RouteDay"]] = relationship(
        "RouteDay",
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="RouteDay.day_number",
    )

    # Database indexes and constraints
    __table_args__ = (
        Index("idx_routes_plan_version", "plan_id", "version"),
        UniqueConstraint("plan_id", "version", name="uq_routes_plan_version"),
    )

    def __repr__(self) -> str:
        return f"<Route(id={self.id}, plan_id='{self.plan_id}', version={self.version}, total_days={self.total_days})>"

    @property
    def average_distance_per_day(self) -> Optional[float]:
        """일평균 이동 거리 계산 (km)"""
        if self.total_distance_km and self.total_days > 0:
            return float(self.total_distance_km) / self.total_days
        return None

    @property
    def average_duration_per_day(self) -> Optional[float]:
        """일평균 이동 시간 계산 (분)"""
        if self.total_duration_minutes and self.total_days > 0:
            return float(self.total_duration_minutes) / self.total_days
        return None

    @property
    def is_single_day_trip(self) -> bool:
        """당일치기 여행 여부"""
        return self.total_days == 1

    @property
    def is_multi_day_trip(self) -> bool:
        """다일차 여행 여부"""
        return self.total_days > 1

    def get_day_route(self, day_number: int) -> Optional["RouteDay"]:
        """특정 일차의 경로 조회"""
        for route_day in self.route_days:
            if route_day.day_number == day_number:
                return route_day
        return None

    def get_total_segments_count(self) -> int:
        """전체 구간 수 계산"""
        total = 0
        for route_day in self.route_days:
            total += len(route_day.route_segments)
        return total

    def to_summary_dict(self) -> Dict[str, Any]:
        """경로 요약 정보를 딕셔너리로 반환"""
        return {
            "route_id": self.id,
            "plan_id": self.plan_id,
            "version": self.version,
            "total_days": self.total_days,
            "departure_location": self.departure_location,
            "hotel_location": self.hotel_location,
            "total_distance_km": (
                float(self.total_distance_km) if self.total_distance_km else None
            ),
            "total_duration_minutes": self.total_duration_minutes,
            "total_spots_count": self.total_spots_count,
            "average_distance_per_day": self.average_distance_per_day,
            "average_duration_per_day": self.average_duration_per_day,
            "calculated_at": (
                self.calculated_at.isoformat() if self.calculated_at else None
            ),
            "days_count": len(self.route_days),
            "segments_count": self.get_total_segments_count(),
        }
