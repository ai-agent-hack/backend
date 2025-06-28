from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.route import (
    RouteCalculationRequest,
    RouteCalculationResponse,
    RouteDeleteResponse,
    RoutePartialUpdateResponse,
    NavigationResponse,
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


@router.post("/calculate-detailed", response_model=RouteFullDetail)
async def calculate_route_with_details(
    request: RouteCalculationRequest,
    route_service: RouteService = Depends(get_route_service),
):
    """
    Calculate optimal travel route with full details

    Calculate route and return complete route information including:
    - All route details (days, segments, navigation)
    - Route summary and daily summaries
    - Optimization metadata and calculation details

    ⚠️ Returns same schema as GET /route/{plan_id}/{version} for consistency
    """
    try:
        # 1. 경로 계산 실행
        calculation_result = await route_service.calculate_route(request)

        if not calculation_result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=calculation_result.error_message or "Route calculation failed",
            )

        # 2. 계산 성공 시 완전한 상세 정보 조회 - 최신 버전으로 조회
        latest_route = route_service.route_repository.get_latest_by_plan(
            request.plan_id
        )
        latest_version = latest_route.version if latest_route else 1

        route_full_details = await route_service.get_route_full_details(
            request.plan_id,
            latest_version,
            calculation_time_seconds=calculation_result.calculation_time_seconds,
        )

        if not route_full_details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Route details not found after calculation",
            )

        return route_full_details

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred during detailed route calculation: {str(e)}",
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
        if latest_route:
            # 기존 RecPlan에서 pre_info_id 가져오기
            existing_plan = rec_plan_repository.get_by_plan_id_and_version(
                request.plan_id, latest_route.version
            )
            if not existing_plan:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Plan not found: plan_id={request.plan_id}, version={latest_route.version}",
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
                request.plan_id, latest_route.version
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


@router.patch(
    "/{plan_id}/{version}/partial-update", response_model=RoutePartialUpdateResponse
)
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

        # 업데이트 전 상태 기록
        before_summary = {
            "total_distance_km": (
                float(existing_route.total_distance_km)
                if existing_route.total_distance_km
                else None
            ),
            "total_duration_minutes": existing_route.total_duration_minutes,
            "hotel_location": existing_route.hotel_location,
        }

        # Supported partial update types
        update_type = update_request.get("type")
        updated_fields = []
        affected_days = []
        recalculation_needed = False

        if update_type == "hotel_location":
            # Change hotel location only - maintain existing spot order and recalculate hotel connections only
            new_hotel = update_request.get("hotel_location")
            result = await route_service.update_hotel_location(
                plan_id, version, new_hotel
            )
            updated_fields = [
                "hotel_location",
                "total_distance_km",
                "total_duration_minutes",
            ]
            recalculation_needed = True
            affected_days = list(range(1, existing_route.total_days + 1))

        elif update_type == "travel_mode":
            # Change travel mode only - maintain existing order and recalculate travel time/distance only
            new_mode = update_request.get("travel_mode")
            result = await route_service.update_travel_mode(plan_id, version, new_mode)
            updated_fields = [
                "travel_mode",
                "total_distance_km",
                "total_duration_minutes",
            ]
            recalculation_needed = True
            affected_days = list(range(1, existing_route.total_days + 1))

        elif update_type == "day_reorder":
            # Change spot order for specific day only
            day_number = update_request.get("day_number")
            new_spot_order = update_request.get("spot_order")
            result = await route_service.reorder_day_spots(
                plan_id, version, day_number, new_spot_order
            )
            updated_fields = [
                "ordered_spots",
                "day_distance_km",
                "day_duration_minutes",
            ]
            recalculation_needed = True
            affected_days = [day_number]

        elif update_type == "spot_replacement":
            # Replace specific spot with another spot
            old_spot_id = update_request.get("old_spot_id")
            new_spot_id = update_request.get("new_spot_id")
            result = await route_service.replace_spot(
                plan_id, version, old_spot_id, new_spot_id
            )
            updated_fields = ["spots", "total_distance_km", "total_duration_minutes"]
            recalculation_needed = True
            # affected_days는 spot이 속한 날에 따라 결정됨 (임시로 모든 날 설정)
            affected_days = list(range(1, existing_route.total_days + 1))

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported update type: {update_type}",
            )

        # 업데이트된 route 정보 조회
        updated_route = route_repository.get_by_plan_and_version(plan_id, version)
        after_summary = {
            "total_distance_km": (
                float(updated_route.total_distance_km)
                if updated_route.total_distance_km
                else None
            ),
            "total_duration_minutes": updated_route.total_duration_minutes,
            "hotel_location": updated_route.hotel_location,
        }

        return RoutePartialUpdateResponse(
            success=True,
            update_type=update_type,
            updated_fields=updated_fields,
            route_id=existing_route.id,
            plan_id=plan_id,
            version=version,
            before_summary=before_summary,
            after_summary=after_summary,
            recalculation_needed=recalculation_needed,
            affected_days=affected_days,
            message=f"Successfully updated {update_type} for route {plan_id} v{version}",
        )
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
    - Route metadata and summary
    - Daily route information with ordered spots
    - Segment-wise travel information
    - Daily summaries and optimization details

    ⚠️ Returns same schema as POST /calculate-detailed for consistency
    """
    route_full_details = await route_service.get_route_full_details(plan_id, version)

    if not route_full_details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route not found: plan_id={plan_id}, version={version}",
        )

    return route_full_details


@router.get("/{plan_id}/{version}/navigation", response_model=NavigationResponse)
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

    if format.lower() == "gpx":
        # Convert to GPX format (future implementation)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="GPX format is not yet supported.",
        )

    # NavigationResponse 형태로 변환
    daily_navigation = []
    for route_day in route_details.get("route_days", []):
        day_nav = {
            "day_number": route_day["day_number"],
            "start_location": route_day["start_location"],
            "end_location": route_day["end_location"],
            "day_distance_km": route_day["day_distance_km"],
            "day_duration_minutes": route_day["day_duration_minutes"],
            "ordered_spots": route_day["ordered_spots"],
            "route_geometry": route_day["route_geometry"],
            "segments": [
                {
                    "segment_order": seg["segment_order"],
                    "from_location": seg["from_location"],
                    "to_spot_name": seg["to_spot_name"],
                    "distance_meters": seg["distance_meters"],
                    "duration_seconds": seg["duration_seconds"],
                    "travel_mode": seg["travel_mode"],
                    "directions_steps": seg.get("directions_steps"),
                }
                for seg in route_day.get("route_segments", [])
            ],
        }
        daily_navigation.append(day_nav)

    route_overview = {
        "departure_location": route_details["departure_location"],
        "hotel_location": route_details["hotel_location"],
        "total_spots_count": route_details["total_spots_count"],
        "google_maps_data": route_details.get("google_maps_data"),
    }

    return NavigationResponse(
        route_id=route_details["id"],
        plan_id=route_details["plan_id"],
        version=route_details["version"],
        total_distance_km=route_details["total_distance_km"] or 0,
        total_duration_minutes=route_details["total_duration_minutes"] or 0,
        total_days=route_details["total_days"],
        daily_navigation=daily_navigation,
        route_overview=route_overview,
    )


@router.delete("/{plan_id}/{version}", response_model=RouteDeleteResponse)
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

        # 삭제 전 정보 조회
        route_to_delete = route_repository.get_by_plan_and_version(plan_id, version)
        if not route_to_delete:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Route not found for deletion: plan_id={plan_id}, version={version}",
            )

        deleted_summary = {
            "route_id": route_to_delete.id,
            "total_distance_km": (
                float(route_to_delete.total_distance_km)
                if route_to_delete.total_distance_km
                else None
            ),
            "total_duration_minutes": route_to_delete.total_duration_minutes,
            "total_days": route_to_delete.total_days,
            "calculated_at": (
                route_to_delete.calculated_at.isoformat()
                if route_to_delete.calculated_at
                else None
            ),
        }

        # 삭제 실행
        deleted = route_repository.delete_by_plan_and_version(plan_id, version)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Route deletion failed: plan_id={plan_id}, version={version}",
            )

        # 남은 버전들 조회
        remaining_routes = route_repository.get_all_by_plan(plan_id)
        remaining_versions = [route.version for route in remaining_routes]

        return RouteDeleteResponse(
            success=True,
            deleted_route_id=route_to_delete.id,
            plan_id=plan_id,
            version=version,
            deleted_summary=deleted_summary,
            remaining_versions=remaining_versions,
            message=f"Route successfully deleted: {plan_id} v{version}",
        )
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
    Note: Requires pre_info data for test_plan to exist.
    """
    test_request = RouteCalculationRequest(
        plan_id="test_plan",
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
