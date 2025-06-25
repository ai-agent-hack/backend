from sqlalchemy import (
    Column,
    Integer,
    String,
    DECIMAL,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from typing import List, Optional, Dict, Any
from decimal import Decimal

from app.models.base import Base


class RouteDay(Base):
    """
    RouteDay model representing daily routes within a multi-day trip.
    Follows Single Responsibility Principle - only handles daily route data.
    """

    __tablename__ = "route_days"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    route_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("routes.id", ondelete="CASCADE"), nullable=False
    )
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # 일차별 경로 정보
    start_location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    end_location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    day_distance_km: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(precision=8, scale=2), nullable=True
    )
    day_duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 일차별 경로 순서 (TSP 결과)
    ordered_spots: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    route_geometry: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )

    # Override Base's created_at and updated_at
    created_at = None
    updated_at = None

    # Relationships
    route: Mapped["Route"] = relationship("Route", back_populates="route_days")
    route_segments: Mapped[List["RouteSegment"]] = relationship(
        "RouteSegment",
        back_populates="route_day",
        cascade="all, delete-orphan",
        order_by="RouteSegment.segment_order",
    )

    # Database indexes for performance
    __table_args__ = (
        Index("idx_route_days_route_id", "route_id", "day_number"),
        UniqueConstraint("route_id", "day_number", name="uq_route_days_route_day"),
    )

    def __repr__(self) -> str:
        return f"<RouteDay(id={self.id}, route_id={self.route_id}, day_number={self.day_number})>"

    @property
    def spots_count(self) -> int:
        """이 일차에 포함된 스팟 수"""
        if isinstance(self.ordered_spots, list):
            return len(self.ordered_spots)
        elif isinstance(self.ordered_spots, dict) and "spots" in self.ordered_spots:
            return len(self.ordered_spots["spots"])
        return 0

    @property
    def average_time_per_spot(self) -> Optional[float]:
        """스팟당 평균 소요 시간 (분)"""
        if self.day_duration_minutes and self.spots_count > 0:
            return float(self.day_duration_minutes) / self.spots_count
        return None

    @property
    def segments_count(self) -> int:
        """이 일차의 구간 수"""
        return len(self.route_segments)

    def get_spots_by_time_slot(self, time_slot: str) -> List[Dict[str, Any]]:
        """특정 시간대의 스팟들 조회"""
        spots = []
        if isinstance(self.ordered_spots, list):
            spots = [
                spot
                for spot in self.ordered_spots
                if spot.get("time_slot") == time_slot
            ]
        elif isinstance(self.ordered_spots, dict) and "spots" in self.ordered_spots:
            spots = [
                spot
                for spot in self.ordered_spots["spots"]
                if spot.get("time_slot") == time_slot
            ]
        return spots

    def get_morning_spots(self) -> List[Dict[str, Any]]:
        """아침 시간대 스팟들"""
        return self.get_spots_by_time_slot("MORNING")

    def get_afternoon_spots(self) -> List[Dict[str, Any]]:
        """점심 시간대 스팟들"""
        return self.get_spots_by_time_slot("AFTERNOON")

    def get_evening_spots(self) -> List[Dict[str, Any]]:
        """저녁 시간대 스팟들"""
        return self.get_spots_by_time_slot("NIGHT")

    def get_spot_by_order(self, order: int) -> Optional[Dict[str, Any]]:
        """방문 순서로 스팟 조회"""
        if isinstance(self.ordered_spots, list):
            for spot in self.ordered_spots:
                if spot.get("order") == order:
                    return spot
        elif isinstance(self.ordered_spots, dict) and "spots" in self.ordered_spots:
            for spot in self.ordered_spots["spots"]:
                if spot.get("order") == order:
                    return spot
        return None

    def to_detail_dict(self) -> Dict[str, Any]:
        """일차별 상세 정보를 딕셔너리로 반환"""
        return {
            "route_day_id": self.id,
            "route_id": self.route_id,
            "day_number": self.day_number,
            "start_location": self.start_location,
            "end_location": self.end_location,
            "day_distance_km": (
                float(self.day_distance_km) if self.day_distance_km else None
            ),
            "day_duration_minutes": self.day_duration_minutes,
            "spots_count": self.spots_count,
            "segments_count": self.segments_count,
            "average_time_per_spot": self.average_time_per_spot,
            "ordered_spots": self.ordered_spots,
            "route_geometry": self.route_geometry,
            "time_slots": {
                "morning": len(self.get_morning_spots()),
                "afternoon": len(self.get_afternoon_spots()),
                "evening": len(self.get_evening_spots()),
            },
        }
