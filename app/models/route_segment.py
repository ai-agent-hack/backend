from sqlalchemy import Column, Integer, String, ForeignKey, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional, Dict, Any

from app.models.base import Base


class RouteSegment(Base):
    """
    RouteSegment model representing individual segments within a daily route.
    Follows Single Responsibility Principle - only handles route segment data.
    """

    __tablename__ = "route_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    route_day_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("route_days.id", ondelete="CASCADE"), nullable=False
    )
    segment_order: Mapped[int] = mapped_column(Integer, nullable=False)

    # 구간 정보
    from_location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    to_spot_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    to_spot_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # 이동 정보
    distance_meters: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    travel_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="DRIVING"
    )

    # 상세 경로 안내
    directions_steps: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )

    # Relationships
    route_day: Mapped["RouteDay"] = relationship(
        "RouteDay", back_populates="route_segments"
    )

    # Database indexes for performance
    __table_args__ = (
        Index("idx_route_segments_day_order", "route_day_id", "segment_order"),
    )

    def __repr__(self) -> str:
        return f"<RouteSegment(id={self.id}, route_day_id={self.route_day_id}, order={self.segment_order}, to={self.to_spot_name})>"

    @property
    def distance_km(self) -> Optional[float]:
        """거리를 킬로미터로 변환"""
        if self.distance_meters:
            return round(self.distance_meters / 1000.0, 2)
        return None

    @property
    def duration_minutes(self) -> Optional[float]:
        """소요시간을 분으로 변환"""
        if self.duration_seconds:
            return round(self.duration_seconds / 60.0, 1)
        return None

    @property
    def average_speed_kmh(self) -> Optional[float]:
        """평균 속도 계산 (km/h)"""
        if self.distance_km and self.duration_minutes and self.duration_minutes > 0:
            return round((self.distance_km / self.duration_minutes) * 60, 1)
        return None

    @property
    def is_driving(self) -> bool:
        """자동차 이동 여부"""
        return self.travel_mode.upper() == "DRIVING"

    @property
    def is_walking(self) -> bool:
        """도보 이동 여부"""
        return self.travel_mode.upper() == "WALKING"

    @property
    def is_transit(self) -> bool:
        """대중교통 이동 여부"""
        return self.travel_mode.upper() == "TRANSIT"

    def get_steps_count(self) -> int:
        """경로 안내 단계 수"""
        if isinstance(self.directions_steps, dict) and "steps" in self.directions_steps:
            return len(self.directions_steps["steps"])
        elif isinstance(self.directions_steps, list):
            return len(self.directions_steps)
        return 0

    def get_step_by_index(self, index: int) -> Optional[Dict[str, Any]]:
        """특정 인덱스의 경로 안내 단계 조회"""
        if isinstance(self.directions_steps, dict) and "steps" in self.directions_steps:
            steps = self.directions_steps["steps"]
            if 0 <= index < len(steps):
                return steps[index]
        elif isinstance(self.directions_steps, list):
            if 0 <= index < len(self.directions_steps):
                return self.directions_steps[index]
        return None

    def to_navigation_dict(self) -> Dict[str, Any]:
        """네비게이션용 정보를 딕셔너리로 반환"""
        return {
            "segment_id": self.id,
            "route_day_id": self.route_day_id,
            "segment_order": self.segment_order,
            "from_location": self.from_location,
            "to_spot_id": self.to_spot_id,
            "to_spot_name": self.to_spot_name,
            "distance_km": self.distance_km,
            "duration_minutes": self.duration_minutes,
            "average_speed_kmh": self.average_speed_kmh,
            "travel_mode": self.travel_mode,
            "steps_count": self.get_steps_count(),
            "directions_steps": self.directions_steps,
        }

    def to_summary_dict(self) -> Dict[str, Any]:
        """요약 정보를 딕셔너리로 반환"""
        return {
            "segment_id": self.id,
            "segment_order": self.segment_order,
            "from_location": self.from_location,
            "to_spot_name": self.to_spot_name,
            "distance_km": self.distance_km,
            "duration_minutes": self.duration_minutes,
            "travel_mode": self.travel_mode,
        }
