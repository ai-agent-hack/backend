from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.route import (
    RouteCalculationRequest,
    RouteResponse,
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
    """RouteService dependency injection"""
    return RouteService(
        route_repository=RouteRepository(db),
        route_day_repository=RouteDayRepository(db),
        route_segment_repository=RouteSegmentRepository(db),
        rec_spot_repository=RecSpotRepository(db),
        pre_info_repository=PreInfoRepository(db),
        google_maps_service=GoogleMapsService(),
        tsp_solver_service=TSPSolverService(),
    )


@router.post("/coordinates", response_model=RouteResponse)
async def calculate_route_coordinates(
    request: RouteCalculationRequest,
    route_service: RouteService = Depends(get_route_service),
):
    """
    Calculate route and return coordinates only

    Calculate the optimal travel route and return simple coordinate arrays.
    - TSP optimization for optimal order
    - Returns only coordinates without complex route data
    """
    try:
        # 1. 경로 계산 실행
        calculation_result = await route_service.calculate_route(request)

        if not calculation_result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=calculation_result.error_message or "Route calculation failed",
            )

        # 2. 최신 버전으로 경로 상세 정보 조회
        latest_route = route_service.route_repository.get_latest_by_plan(
            request.plan_id
        )
        latest_version = latest_route.version if latest_route else 1

        route_details = await route_service.get_route_details(
            request.plan_id, latest_version
        )

        if not route_details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Route details not found after calculation",
            )

        # 3. 좌표만 추출
        all_coordinates = []
        for route_day in route_details.get("route_days", []):
            route_geometry = route_day.get("route_geometry", {})
            day_coordinates = route_geometry.get("coordinates", [])
            all_coordinates.extend(day_coordinates)

        return RouteResponse(coordinates=all_coordinates)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred during route calculation: {str(e)}",
        )


@router.get("/health")
async def route_service_health():
    """
    Route service health check

    Check the connection status of Google Maps API and TSP service status.
    """
    try:
        # Check Google Maps service status
        google_maps_service = GoogleMapsService()
        google_maps_status = "OK" if google_maps_service.api_key else "NO_API_KEY"

        # Check TSP service status
        tsp_service = TSPSolverService()
        tsp_status = "OK"

        # Check OR-Tools installation status
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
