from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.route import (
    RouteCalculationRequest,
    RouteCalculationResponse,
    RouteStatistics,
    RouteFullDetail,
    RouteWithDays,
)
from app.services.route_service import RouteService
from app.services.google_maps_service import GoogleMapsService
from app.services.tsp_solver_service import TSPSolverService
from app.repositories.route import (
    RouteRepository,
    RouteDayRepository,
    RouteSegmentRepository,
)
from app.repositories.rec_spot import RecSpotRepository
from app.repositories.pre_info import PreInfoRepository


router = APIRouter()


def get_route_service(db: Session = Depends(get_db)) -> RouteService:
    """RouteService 의존성 주입"""
    return RouteService(
        route_repository=RouteRepository(db),
        route_day_repository=RouteDayRepository(db),
        route_segment_repository=RouteSegmentRepository(db),
        rec_spot_repository=RecSpotRepository(db),
        pre_info_repository=PreInfoRepository(db),
        google_maps_service=GoogleMapsService(),
        tsp_solver_service=TSPSolverService(),
    )


@router.post("/calculate", response_model=RouteCalculationResponse)
async def calculate_route(
    request: RouteCalculationRequest,
    route_service: RouteService = Depends(get_route_service),
):
    """
    경로 계산 API

    선택된 스팟들을 기반으로 최적의 여행 경로를 계산합니다.
    - Google Maps API를 사용한 실제 거리/시간 계산
    - TSP 알고리즘을 사용한 최적 순서 결정
    - 다일차 여행 지원
    """
    try:
        result = await route_service.calculate_route(request)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"경로 계산 중 오류가 발생했습니다: {str(e)}",
        )


@router.get("/{plan_id}/{version}", response_model=RouteFullDetail)
async def get_route_details(
    plan_id: str,
    version: int,
    route_service: RouteService = Depends(get_route_service),
):
    """
    경로 상세 정보 조회 API

    특정 플랜의 특정 버전에 대한 상세 경로 정보를 조회합니다.
    - 일차별 경로 정보
    - 구간별 이동 정보
    - 내비게이션 데이터
    """
    route_details = await route_service.get_route_details(plan_id, version)

    if not route_details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"경로를 찾을 수 없습니다: plan_id={plan_id}, version={version}",
        )

    return route_details


@router.get("/{plan_id}/statistics", response_model=RouteStatistics)
async def get_route_statistics(
    plan_id: str,
    route_service: RouteService = Depends(get_route_service),
):
    """
    플랜의 경로 통계 정보 조회 API

    특정 플랜의 모든 버전에 대한 통계 정보를 제공합니다.
    - 총 버전 수
    - 최신 버전 정보
    - 경로 요약 데이터
    """
    try:
        route_repository = RouteRepository(next(get_db()))
        statistics = route_repository.get_route_statistics(plan_id)
        return RouteStatistics(**statistics)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"통계 조회 중 오류가 발생했습니다: {str(e)}",
        )


@router.get("/{plan_id}/versions", response_model=List[RouteWithDays])
async def get_all_route_versions(
    plan_id: str,
    route_service: RouteService = Depends(get_route_service),
):
    """
    플랜의 모든 경로 버전 조회 API

    특정 플랜의 모든 버전의 경로 정보를 조회합니다.
    버전별 비교 및 이력 관리에 사용됩니다.
    """
    try:
        route_repository = RouteRepository(next(get_db()))
        routes = route_repository.get_all_by_plan(plan_id)

        if not routes:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"플랜 '{plan_id}'에 대한 경로가 없습니다.",
            )

        return [RouteWithDays.from_orm(route) for route in routes]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"경로 버전 조회 중 오류가 발생했습니다: {str(e)}",
        )


@router.delete("/{plan_id}/{version}")
async def delete_route(
    plan_id: str,
    version: int,
    route_service: RouteService = Depends(get_route_service),
):
    """
    경로 삭제 API

    특정 플랜의 특정 버전 경로를 삭제합니다.
    """
    try:
        route_repository = RouteRepository(next(get_db()))
        deleted = route_repository.delete_by_plan_and_version(plan_id, version)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"삭제할 경로를 찾을 수 없습니다: plan_id={plan_id}, version={version}",
            )

        return {"message": f"경로가 성공적으로 삭제되었습니다: {plan_id} v{version}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"경로 삭제 중 오류가 발생했습니다: {str(e)}",
        )


@router.get("/{plan_id}/{version}/navigation")
async def get_navigation_data(
    plan_id: str,
    version: int,
    format: str = Query("json", description="응답 형식: json, gpx"),
    route_service: RouteService = Depends(get_route_service),
):
    """
    내비게이션 데이터 조회 API

    특정 경로의 내비게이션 정보를 조회합니다.
    - 구간별 이동 안내
    - GPS 좌표 정보
    - 단계별 안내사항
    """
    route_details = await route_service.get_route_details(plan_id, version)

    if not route_details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"경로를 찾을 수 없습니다: plan_id={plan_id}, version={version}",
        )

    navigation_data = route_details.get("navigation", {})

    if format.lower() == "gpx":
        # GPX 형식으로 변환 (향후 구현)
        return {"message": "GPX 형식은 아직 지원되지 않습니다."}

    return navigation_data


@router.get("/health")
async def route_service_health():
    """
    Route 서비스 상태 확인 API

    Google Maps API 연결 상태 및 TSP 서비스 상태를 확인합니다.
    """
    try:
        # Google Maps 서비스 상태 확인
        google_maps_service = GoogleMapsService()
        google_maps_status = "OK" if google_maps_service.api_key else "NO_API_KEY"

        # TSP 서비스 상태 확인
        tsp_service = TSPSolverService()
        tsp_status = "OK"

        # OR-Tools 설치 상태 확인
        try:
            from ortools.constraint_solver import pywrapcp

            ortools_status = "AVAILABLE"
        except ImportError:
            ortools_status = "NOT_INSTALLED"

        return {
            "status": "healthy",
            "services": {
                "google_maps": google_maps_status,
                "tsp_solver": tsp_status,
                "ortools": ortools_status,
            },
            "capabilities": {
                "route_calculation": True,
                "multi_day_optimization": True,
                "real_time_traffic": google_maps_status == "OK",
                "advanced_tsp": ortools_status == "AVAILABLE",
            },
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@router.post("/test-calculation")
async def test_route_calculation(
    route_service: RouteService = Depends(get_route_service),
):
    """
    경로 계산 테스트 API

    더미 데이터로 경로 계산 기능을 테스트합니다.
    개발 및 디버깅 목적으로 사용됩니다.
    """
    test_request = RouteCalculationRequest(
        plan_id="test_plan",
        version=1,
        departure_location="37.5563,126.9720",  # 서울역
        hotel_location="37.4979,127.0276",  # 강남역
        travel_mode="DRIVING",
        optimize_for="distance",
    )

    try:
        result = await route_service.calculate_route(test_request)
        return {
            "test_status": "completed",
            "result": result,
            "message": "테스트 경로 계산이 완료되었습니다.",
        }
    except Exception as e:
        return {
            "test_status": "failed",
            "error": str(e),
            "message": "테스트 경로 계산 중 오류가 발생했습니다.",
        }
