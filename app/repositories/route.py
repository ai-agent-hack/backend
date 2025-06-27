from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, desc

from app.repositories.base import BaseRepository
from app.models.route import Route
from app.models.route_day import RouteDay
from app.models.route_segment import RouteSegment
from app.schemas.route import RouteCreate, RouteUpdate


class RouteRepository(BaseRepository[Route, RouteCreate, RouteUpdate]):
    """
    Route 데이터 액세스 계층.
    Single Responsibility Principle: 경로 데이터베이스 작업만 담당
    """

    def __init__(self, db: Session):
        super().__init__(Route, db)

    def get_by_plan_and_version(self, plan_id: str, version: int) -> Optional[Route]:
        """특정 플랜의 특정 버전 경로 조회"""
        return (
            self.db.query(Route)
            .filter(and_(Route.plan_id == plan_id, Route.version == version))
            .first()
        )

    def get_latest_by_plan(self, plan_id: str) -> Optional[Route]:
        """특정 플랜의 최신 버전 경로 조회"""
        return (
            self.db.query(Route)
            .filter(Route.plan_id == plan_id)
            .order_by(desc(Route.version))
            .first()
        )

    def get_with_details(
        self, plan_id: str, version: int, include_segments: bool = True
    ) -> Optional[Route]:
        """경로와 하위 데이터를 모두 포함하여 조회"""
        query = self.db.query(Route)

        if include_segments:
            # segment를 로드할 때 day도 함께 로드되도록 joinedload를 중첩합니다.
            query = query.options(
                joinedload(Route.route_days).joinedload(RouteDay.route_segments)
            )
        else:
            # day만 로드합니다.
            query = query.options(joinedload(Route.route_days))

        return query.filter(
            and_(Route.plan_id == plan_id, Route.version == version)
        ).first()

    def get_all_by_plan(self, plan_id: str) -> List[Route]:
        """특정 플랜의 모든 버전 경로 조회"""
        return (
            self.db.query(Route)
            .filter(Route.plan_id == plan_id)
            .order_by(desc(Route.version))
            .all()
        )

    def get_plans_with_routes(self, limit: int = 100) -> List[str]:
        """경로가 있는 플랜 ID 목록 조회"""
        return self.db.query(Route.plan_id).distinct().limit(limit).all()

    def create_with_days_and_segments(
        self, route_data: Dict[str, Any], days_data: List[Dict[str, Any]]
    ) -> Route:
        """경로, 일차별 경로, 구간을 한 번에 생성"""
        # 1. Route 생성
        route = Route(**route_data)
        self.db.add(route)
        self.db.flush()  # ID 생성을 위해 flush

        # 2. RouteDay 생성
        for day_data in days_data:
            segments_data = day_data.pop("segments", [])

            route_day = RouteDay(route_id=route.id, **day_data)
            self.db.add(route_day)
            self.db.flush()  # ID 생성을 위해 flush

            # 3. RouteSegment 생성
            for segment_data in segments_data:
                route_segment = RouteSegment(route_day_id=route_day.id, **segment_data)
                self.db.add(route_segment)

        self.db.commit()
        self.db.refresh(route)
        return route

    def update_route_summary(
        self,
        route_id: int,
        total_distance_km: float,
        total_duration_minutes: int,
        total_spots_count: int,
    ) -> Optional[Route]:
        """경로 요약 정보 업데이트"""
        route = self.get(route_id)
        if route:
            route.total_distance_km = total_distance_km
            route.total_duration_minutes = total_duration_minutes
            route.total_spots_count = total_spots_count
            self.db.commit()
            self.db.refresh(route)
        return route

    def delete_by_plan_and_version(self, plan_id: str, version: int) -> bool:
        """특정 플랜의 특정 버전 경로 삭제"""
        route = self.get_by_plan_and_version(plan_id, version)
        if route:
            self.db.delete(route)
            self.db.flush()  # 변경 사항을 세션에 즉시 반영
            return True
        return False

    def get_route_statistics(self, plan_id: str) -> Dict[str, Any]:
        """플랜의 경로 통계 정보"""
        routes = self.get_all_by_plan(plan_id)

        if not routes:
            return {"total_versions": 0, "latest_version": 0, "has_routes": False}

        latest_route = routes[0]  # 이미 desc 정렬됨

        return {
            "total_versions": len(routes),
            "latest_version": latest_route.version,
            "has_routes": True,
            "latest_route_summary": (
                latest_route.to_summary_dict() if latest_route else None
            ),
            "total_distance_km": (
                float(latest_route.total_distance_km)
                if latest_route.total_distance_km
                else None
            ),
            "total_duration_minutes": latest_route.total_duration_minutes,
            "total_days": latest_route.total_days,
        }

    def exists_for_plan_version(self, plan_id: str, version: int) -> bool:
        """특정 플랜 버전에 경로가 있는지 확인"""
        return (
            self.db.query(Route.id)
            .filter(and_(Route.plan_id == plan_id, Route.version == version))
            .first()
        ) is not None


class RouteDayRepository:
    """
    RouteDay 데이터 액세스 계층.
    일차별 경로 데이터베이스 작업만 담당
    """

    def __init__(self, db: Session):
        self.db = db

    def get_by_route_and_day(
        self, route_id: int, day_number: int
    ) -> Optional[RouteDay]:
        """특정 경로의 특정 일차 조회"""
        return (
            self.db.query(RouteDay)
            .filter(
                and_(RouteDay.route_id == route_id, RouteDay.day_number == day_number)
            )
            .first()
        )

    def get_all_by_route(self, route_id: int) -> List[RouteDay]:
        """특정 경로의 모든 일차 조회"""
        return (
            self.db.query(RouteDay)
            .filter(RouteDay.route_id == route_id)
            .order_by(RouteDay.day_number)
            .all()
        )

    def update_spots_order(
        self, route_day_id: int, ordered_spots: Dict[str, Any]
    ) -> Optional[RouteDay]:
        """일차별 스팟 순서 업데이트"""
        route_day = self.db.query(RouteDay).get(route_day_id)
        if route_day:
            route_day.ordered_spots = ordered_spots
            self.db.commit()
            self.db.refresh(route_day)
        return route_day


class RouteSegmentRepository:
    """
    RouteSegment 데이터 액세스 계층.
    경로 구간 데이터베이스 작업만 담당
    """

    def __init__(self, db: Session):
        self.db = db

    def get_by_route_day(self, route_day_id: int) -> List[RouteSegment]:
        """특정 일차의 모든 구간 조회"""
        return (
            self.db.query(RouteSegment)
            .filter(RouteSegment.route_day_id == route_day_id)
            .order_by(RouteSegment.segment_order)
            .all()
        )

    def create_segments_batch(
        self, route_day_id: int, segments_data: List[Dict[str, Any]]
    ) -> List[RouteSegment]:
        """구간들을 일괄 생성"""
        segments = []
        for segment_data in segments_data:
            segment = RouteSegment(route_day_id=route_day_id, **segment_data)
            self.db.add(segment)
            segments.append(segment)

        self.db.commit()
        return segments

    def delete_by_route_day(self, route_day_id: int) -> int:
        """특정 일차의 모든 구간 삭제"""
        deleted_count = (
            self.db.query(RouteSegment)
            .filter(RouteSegment.route_day_id == route_day_id)
            .delete()
        )
        self.db.commit()
        return deleted_count
