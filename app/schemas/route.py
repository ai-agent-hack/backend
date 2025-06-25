from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal


# === Route Schemas ===


class RouteBase(BaseModel):
    """Route 기본 스키마"""

    plan_id: str = Field(..., max_length=50)
    version: int = Field(..., ge=1)
    total_days: int = Field(..., ge=1)
    departure_location: Optional[str] = Field(None, max_length=200)
    hotel_location: Optional[str] = Field(None, max_length=200)


class RouteCreate(RouteBase):
    """Route 생성 스키마"""

    total_distance_km: Optional[Decimal] = None
    total_duration_minutes: Optional[int] = None
    total_spots_count: Optional[int] = None
    google_maps_data: Optional[Dict[str, Any]] = None


class RouteUpdate(BaseModel):
    """Route 업데이트 스키마"""

    total_days: Optional[int] = Field(None, ge=1)
    departure_location: Optional[str] = Field(None, max_length=200)
    hotel_location: Optional[str] = Field(None, max_length=200)
    total_distance_km: Optional[Decimal] = None
    total_duration_minutes: Optional[int] = None
    total_spots_count: Optional[int] = None
    google_maps_data: Optional[Dict[str, Any]] = None


class Route(RouteBase):
    """Route 응답 스키마"""

    id: int
    total_distance_km: Optional[float]
    total_duration_minutes: Optional[int]
    total_spots_count: Optional[int]
    calculated_at: datetime
    google_maps_data: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


# === RouteDay Schemas ===


class RouteDayBase(BaseModel):
    """RouteDay 기본 스키마"""

    day_number: int = Field(..., ge=1)
    start_location: Optional[str] = Field(None, max_length=200)
    end_location: Optional[str] = Field(None, max_length=200)
    ordered_spots: Dict[str, Any] = Field(...)


class RouteDayCreate(RouteDayBase):
    """RouteDay 생성 스키마"""

    route_id: int
    day_distance_km: Optional[Decimal] = None
    day_duration_minutes: Optional[int] = None
    route_geometry: Optional[Dict[str, Any]] = None


class RouteDayUpdate(BaseModel):
    """RouteDay 업데이트 스키마"""

    start_location: Optional[str] = Field(None, max_length=200)
    end_location: Optional[str] = Field(None, max_length=200)
    day_distance_km: Optional[Decimal] = None
    day_duration_minutes: Optional[int] = None
    ordered_spots: Optional[Dict[str, Any]] = None
    route_geometry: Optional[Dict[str, Any]] = None


class RouteDay(RouteDayBase):
    """RouteDay 응답 스키마"""

    id: int
    route_id: int
    day_distance_km: Optional[float]
    day_duration_minutes: Optional[int]
    route_geometry: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


# === RouteSegment Schemas ===


class RouteSegmentBase(BaseModel):
    """RouteSegment 기본 스키마"""

    segment_order: int = Field(..., ge=1)
    from_location: Optional[str] = Field(None, max_length=200)
    to_spot_id: Optional[str] = Field(None, max_length=100)
    to_spot_name: Optional[str] = Field(None, max_length=200)
    travel_mode: str = Field("DRIVING", max_length=20)


class RouteSegmentCreate(RouteSegmentBase):
    """RouteSegment 생성 스키마"""

    route_day_id: int
    distance_meters: Optional[int] = None
    duration_seconds: Optional[int] = None
    directions_steps: Optional[Dict[str, Any]] = None


class RouteSegmentUpdate(BaseModel):
    """RouteSegment 업데이트 스키마"""

    from_location: Optional[str] = Field(None, max_length=200)
    to_spot_id: Optional[str] = Field(None, max_length=100)
    to_spot_name: Optional[str] = Field(None, max_length=200)
    distance_meters: Optional[int] = None
    duration_seconds: Optional[int] = None
    travel_mode: Optional[str] = Field(None, max_length=20)
    directions_steps: Optional[Dict[str, Any]] = None


class RouteSegment(RouteSegmentBase):
    """RouteSegment 응답 스키마"""

    id: int
    route_day_id: int
    distance_meters: Optional[int]
    duration_seconds: Optional[int]
    directions_steps: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


# === Composite Schemas ===


class RouteWithDays(Route):
    """일차별 경로를 포함한 Route 스키마"""

    route_days: List[RouteDay] = []


class RouteDayWithSegments(RouteDay):
    """구간을 포함한 RouteDay 스키마"""

    route_segments: List[RouteSegment] = []


class RouteFullDetail(Route):
    """모든 하위 데이터를 포함한 Route 스키마"""

    route_days: List[RouteDayWithSegments] = []


# === Request/Response Schemas ===


class RouteCalculationRequest(BaseModel):
    """경로 계산 요청 스키마"""

    plan_id: str
    version: int
    departure_location: Optional[str] = None
    hotel_location: Optional[str] = None
    travel_mode: str = Field("DRIVING", max_length=20)
    optimize_for: str = Field("distance", description="distance or time")


class RouteCalculationResponse(BaseModel):
    """경로 계산 응답 스키마"""

    success: bool
    route_id: Optional[int] = None
    total_distance_km: Optional[float] = None
    total_duration_minutes: Optional[int] = None
    total_spots_count: Optional[int] = None
    calculation_time_seconds: Optional[float] = None
    error_message: Optional[str] = None


class RouteStatistics(BaseModel):
    """경로 통계 정보 스키마"""

    total_versions: int
    latest_version: int
    has_routes: bool
    latest_route_summary: Optional[Dict[str, Any]] = None
    total_distance_km: Optional[float] = None
    total_duration_minutes: Optional[int] = None
    total_days: Optional[int] = None


# === Navigation Schemas ===


class NavigationStep(BaseModel):
    """내비게이션 단계 스키마"""

    instruction: str
    distance_meters: int
    duration_seconds: int
    polyline: Optional[str] = None


class RouteNavigation(BaseModel):
    """내비게이션 정보 스키마"""

    route_id: int
    plan_id: str
    version: int
    total_distance_km: float
    total_duration_minutes: int
    days: List[Dict[str, Any]]
