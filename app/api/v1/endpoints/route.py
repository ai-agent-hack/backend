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
from app.repositories.rec_plan import RecPlanRepository


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


@router.post("/calculate", response_model=RouteCalculationResponse)
async def calculate_route(
    request: RouteCalculationRequest,
    route_service: RouteService = Depends(get_route_service),
):
    """
    Calculate optimal travel route

    Calculate the optimal travel route based on selected spots.
    - Real distance/time calculation using Google Maps API
    - Optimal order determination using TSP algorithm
    - Multi-day trip support
    """
    try:
        result = await route_service.calculate_route(request)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred during route calculation: {str(e)}",
        )


@router.post("/regenerate", response_model=RouteCalculationResponse)
async def regenerate_route_as_new_version(
    request: RouteCalculationRequest,
    route_service: RouteService = Depends(get_route_service),
    db: Session = Depends(get_db),
):
    """
    Regenerate route as new version

    Generate a new version of the route with different parameters while preserving existing routes.
    - Existing versions are preserved
    - Saved with new version number
    - Version comparison available
    """
    try:
        # 최신 버전 조회 후 새 버전 번호 생성
        route_repository = RouteRepository(db)
        rec_spot_repository = RecSpotRepository(db)
        rec_plan_repository = RecPlanRepository(db)

        latest_route = route_repository.get_latest_by_plan(request.plan_id)

        if latest_route:
            new_version = latest_route.version + 1
        else:
            new_version = 1

        # 기존 버전에서 선택된 스팟들을 새 버전으로 복사
        if request.version:
            # 기존 RecPlan에서 pre_info_id 가져오기
            existing_plan = rec_plan_repository.get_by_plan_id_and_version(
                request.plan_id, request.version
            )
            if not existing_plan:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Plan not found: plan_id={request.plan_id}, version={request.version}",
                )

            # 새 버전의 RecPlan 생성
            from app.models.rec_plan import RecPlan

            new_plan = RecPlan(
                plan_id=request.plan_id,
                version=new_version,
                pre_info_id=existing_plan.pre_info_id,
            )
            db.add(new_plan)
            db.commit()
            db.refresh(new_plan)

            existing_spots = rec_spot_repository.get_selected_spots_by_plan_version(
                request.plan_id, request.version
            )
            if existing_spots:
                # 기존 스팟들을 새 버전으로 복사
                new_spots_data = []
                for spot in existing_spots:
                    spot_data = {
                        "plan_id": request.plan_id,
                        "version": new_version,
                        "spot_id": spot.spot_id,
                        "rank": spot.rank,
                        "status": "ADD",  # 새 버전에서는 모두 ADD 상태
                        "selected": True,  # 새 버전에서는 모두 선택됨
                        "time_slot": spot.time_slot,
                        "spot_name": spot.spot_name,
                        "latitude": spot.latitude,
                        "longitude": spot.longitude,
                        "spot_details": spot.spot_details,
                        "recommendation_reason": spot.recommendation_reason,
                        "image_url": spot.image_url,
                        "website_url": spot.website_url,
                        "similarity_score": spot.similarity_score,
                    }
                    new_spots_data.append(spot_data)

                # 새 버전으로 스팟들 생성
                rec_spot_repository.create_spots_batch(new_spots_data)

        # 새 버전으로 요청 업데이트
        new_request = RouteCalculationRequest(
            plan_id=request.plan_id,
            version=new_version,
            departure_location=request.departure_location,
            hotel_location=request.hotel_location,
            travel_mode=request.travel_mode,
            optimize_for=request.optimize_for,
        )

        result = await route_service.calculate_route(new_request)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred during route regeneration: {str(e)}",
        )


@router.patch("/{plan_id}/{version}/partial-update")
async def partial_update_route(
    plan_id: str,
    version: int,
    update_request: Dict[str, Any],
    route_service: RouteService = Depends(get_route_service),
):
    """
    Partial route update

    Partially update the route by modifying specific segments or settings.
    - Change hotel location only
    - Change order for specific day only
    - Change travel mode only
    - Reuse existing calculation results as much as possible
    """
    try:
        # 기존 경로 조회
        route_repository = RouteRepository(next(get_db()))
        existing_route = route_repository.get_by_plan_and_version(plan_id, version)

        if not existing_route:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Route not found for modification: plan_id={plan_id}, version={version}",
            )

        # Supported partial update types
        update_type = update_request.get("type")

        if update_type == "hotel_location":
            # Change hotel location only - maintain existing spot order and recalculate hotel connections only
            new_hotel = update_request.get("hotel_location")
            result = await route_service.update_hotel_location(
                plan_id, version, new_hotel
            )

        elif update_type == "travel_mode":
            # Change travel mode only - maintain existing order and recalculate travel time/distance only
            new_mode = update_request.get("travel_mode")
            result = await route_service.update_travel_mode(plan_id, version, new_mode)

        elif update_type == "day_reorder":
            # Change spot order for specific day only
            day_number = update_request.get("day_number")
            new_spot_order = update_request.get("spot_order")
            result = await route_service.reorder_day_spots(
                plan_id, version, day_number, new_spot_order
            )

        elif update_type == "spot_replacement":
            # Replace specific spot with another spot
            old_spot_id = update_request.get("old_spot_id")
            new_spot_id = update_request.get("new_spot_id")
            result = await route_service.replace_spot(
                plan_id, version, old_spot_id, new_spot_id
            )

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported update type: {update_type}",
            )

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred during partial route update: {str(e)}",
        )


@router.get("/{plan_id}/statistics", response_model=RouteStatistics)
async def get_route_statistics(
    plan_id: str,
    route_service: RouteService = Depends(get_route_service),
):
    """
    Get route statistics

    Provide statistical information for all versions of a specific plan.
    - Total number of versions
    - Latest version information
    - Route summary data
    """
    try:
        route_repository = RouteRepository(next(get_db()))
        statistics = route_repository.get_route_statistics(plan_id)
        return RouteStatistics(**statistics)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred while retrieving statistics: {str(e)}",
        )


@router.get("/{plan_id}/versions", response_model=List[RouteWithDays])
async def get_all_route_versions(
    plan_id: str,
    route_service: RouteService = Depends(get_route_service),
):
    """
    Get all route versions

    Retrieve route information for all versions of a specific plan.
    Used for version comparison and history management.
    """
    try:
        route_repository = RouteRepository(next(get_db()))
        routes = route_repository.get_all_by_plan(plan_id)

        if not routes:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No routes found for plan '{plan_id}'.",
            )

        return [RouteWithDays.from_orm(route) for route in routes]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred while retrieving route versions: {str(e)}",
        )


@router.get("/{plan_id}/{version}", response_model=RouteFullDetail)
async def get_route_details(
    plan_id: str,
    version: int,
    route_service: RouteService = Depends(get_route_service),
):
    """
    Get route details

    Retrieve detailed route information for a specific plan version.
    - Daily route information
    - Segment-wise travel information
    - Navigation data
    """
    route_details = await route_service.get_route_details(plan_id, version)

    if not route_details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route not found: plan_id={plan_id}, version={version}",
        )

    return route_details


@router.get("/{plan_id}/{version}/navigation")
async def get_navigation_data(
    plan_id: str,
    version: int,
    format: str = Query("json", description="Response format: json, gpx"),
    route_service: RouteService = Depends(get_route_service),
):
    """
    Get navigation data

    Retrieve navigation information for a specific route.
    - Segment-wise travel guidance
    - GPS coordinate information
    - Step-by-step instructions
    """
    route_details = await route_service.get_route_details(plan_id, version)

    if not route_details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route not found: plan_id={plan_id}, version={version}",
        )

    navigation_data = route_details.get("navigation", {})

    if format.lower() == "gpx":
        # Convert to GPX format (future implementation)
        return {"message": "GPX format is not yet supported."}

    return navigation_data


@router.delete("/{plan_id}/{version}")
async def delete_route(
    plan_id: str,
    version: int,
    route_service: RouteService = Depends(get_route_service),
):
    """
    Delete route

    Delete a specific version route of a specific plan.
    """
    try:
        route_repository = RouteRepository(next(get_db()))
        deleted = route_repository.delete_by_plan_and_version(plan_id, version)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Route not found for deletion: plan_id={plan_id}, version={version}",
            )

        return {"message": f"Route successfully deleted: {plan_id} v{version}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred during route deletion: {str(e)}",
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


@router.post("/test-calculation")
async def test_route_calculation(
    route_service: RouteService = Depends(get_route_service),
):
    """
    Route calculation test API

    Test route calculation functionality with dummy data.
    Used for development and debugging purposes.
    """
    test_request = RouteCalculationRequest(
        plan_id="test_plan",
        version=1,
        departure_location="37.5563,126.9720",  # Seoul Station
        hotel_location="37.4979,127.0276",  # Gangnam Station
        travel_mode="DRIVING",
        optimize_for="distance",
    )

    try:
        result = await route_service.calculate_route(test_request)
        return {
            "test_status": "completed",
            "result": result,
            "message": "Test route calculation completed.",
        }
    except Exception as e:
        return {
            "test_status": "failed",
            "error": str(e),
            "message": "Error occurred during test route calculation.",
        }
