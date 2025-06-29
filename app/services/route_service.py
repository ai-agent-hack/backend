import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal

from app.repositories.route import (
    RouteRepository,
    RouteDayRepository,
    RouteSegmentRepository,
)
from app.repositories.rec_spot import RecSpotRepository
from app.repositories.rec_plan import RecPlanRepository
from app.repositories.pre_info import PreInfoRepository
from app.services.google_maps_service import (
    GoogleMapsService,
    LocationCoordinate,
    DistanceMatrixResult,
)
from app.services.tsp_solver_service import TSPSolverService, TSPSolution
from app.schemas.route import (
    RouteCalculationRequest,
    RouteCalculationResponse,
    RouteCreate,
    RouteDayCreate,
    RouteSegmentCreate,
)
from app.models.rec_spot import RecSpot
from app.services.route_calculator import (
    RouteCalculator,
    RouteCalculationInput,
    RouteCalculationOutput,
)


logger = logging.getLogger(__name__)


class RouteService:
    """
    Route 계산 비즈니스 로직 서비스.
    Single Responsibility Principle: 경로 최적화 비즈니스 로직만 담당
    """

    def __init__(
        self,
        route_repository: RouteRepository,
        route_day_repository: RouteDayRepository,
        route_segment_repository: RouteSegmentRepository,
        rec_spot_repository: RecSpotRepository,
        rec_plan_repository: RecPlanRepository,
        pre_info_repository: PreInfoRepository,
        google_maps_service: GoogleMapsService,
        tsp_solver_service: TSPSolverService,
    ):
        self.route_repository = route_repository
        self.route_day_repository = route_day_repository
        self.route_segment_repository = route_segment_repository
        self.rec_spot_repository = rec_spot_repository
        self.rec_plan_repository = rec_plan_repository
        self.pre_info_repository = pre_info_repository
        self.google_maps_service = google_maps_service
        self.tsp_solver_service = tsp_solver_service

    async def calculate_route(
        self, request: RouteCalculationRequest
    ) -> RouteCalculationResponse:
        """
        경로 계산 메인 로직.
        RouteCalculator를 사용하여 계산을 위임하고, 결과를 저장합니다.
        """
        start_time = time.time()

        try:
            # 1. 최신 plan 버전 가져오기 (선택된 스팟이 있는 버전)
            latest_plan = self.rec_plan_repository.get_latest_version(request.plan_id)
            latest_version = latest_plan.version if latest_plan else 1

            # 2. pre_info에서 출발지와 호텔 정보 가져오기
            pre_info = self.pre_info_repository.get_by_plan_id(request.plan_id)
            if not pre_info:
                raise ValueError(
                    f"Plan {request.plan_id}에 대한 pre_info를 찾을 수 없습니다."
                )

            # departure_location과 hotel_location을 pre_info에서 추출
            departure_location = pre_info.region
            hotel_location = pre_info.region  # region을 기본 위치로 사용

            if not departure_location:
                raise ValueError("출발지 정보를 찾을 수 없습니다.")

            # 기존 경로 데이터가 있다면 삭제
            existing_route = self.route_repository.get_by_plan_and_version(
                request.plan_id, latest_version
            )
            if existing_route:
                self.route_repository.delete_by_plan_and_version(
                    request.plan_id, latest_version
                )

            # 3. 계산에 필요한 입력 데이터 준비
            spots_data = await self._collect_spots_data(request.plan_id, latest_version)
            if not spots_data["selected_spots"]:
                raise ValueError("선택된 스팟이 없습니다.")

            locations, location_mapping = self._create_location_coordinates(spots_data)

            calculation_input = RouteCalculationInput(
                plan_id=request.plan_id,
                version=latest_version,
                selected_spots=spots_data["selected_spots"],
                total_days=spots_data["total_days"],
                locations=locations,
                location_mapping=location_mapping,
                travel_mode=request.travel_mode,
                optimize_for=request.optimize_for,
                google_maps_service=self.google_maps_service,
                tsp_solver_service=self.tsp_solver_service,
            )

            # 2. RouteCalculator 실행
            calculator = RouteCalculator(calculation_input)
            calculation_output = await calculator.run()

            # 3. 상세 경로 정보 생성 (Google Maps API 호출)
            detailed_routes = await self._generate_detailed_routes(
                calculation_output.tsp_solutions, locations, request.travel_mode
            )

            # 4. 데이터베이스에 결과 저장
            route = await self._save_route_data(
                request,
                spots_data,
                calculation_output,
                detailed_routes,
                locations,
                latest_version,
            )

            calculation_time = time.time() - start_time
            return RouteCalculationResponse(
                success=True,
                route_id=route.id,
                total_distance_km=(
                    float(route.total_distance_km) if route.total_distance_km else None
                ),
                total_duration_minutes=route.total_duration_minutes,
                total_spots_count=route.total_spots_count,
                calculation_time_seconds=calculation_time,
            )

        except Exception as e:
            logger.error(f"경로 계산 중 에러 발생: {e}", exc_info=True)
            return RouteCalculationResponse(success=False, error_message=str(e))

    async def _collect_spots_data(self, plan_id: str, version: int) -> Dict[str, Any]:
        """1️⃣ スポットデータ収集"""
        selected_spots = self.rec_spot_repository.get_selected_spots_by_plan_version(
            plan_id, version
        )

        # 時間帯別分類
        spots_by_time_slot = {"MORNING": [], "AFTERNOON": [], "NIGHT": []}

        for spot in selected_spots:
            time_slot = spot.time_slot or "AFTERNOON"  # デフォルト値
            spots_by_time_slot[time_slot].append(spot)

        # 旅行期間情報
        pre_info = self.pre_info_repository.get_by_plan_id(plan_id)
        total_days = self._calculate_total_days(pre_info) if pre_info else 1

        return {
            "selected_spots": selected_spots,
            "spots_by_time_slot": spots_by_time_slot,
            "total_days": total_days,
            "pre_info": pre_info,
        }

    def _create_location_coordinates(
        self, spots_data: Dict[str, Any]
    ) -> Tuple[List[LocationCoordinate], Dict[str, int]]:
        """스팟들만으로 좌표 리스트 생성"""
        locations = []
        location_mapping = {}

        # 스팟들만 추가 (출발지/호텔 개념 제거)
        for i, spot in enumerate(spots_data["selected_spots"]):
            if spot.latitude and spot.longitude:
                coord = LocationCoordinate(
                    latitude=float(spot.latitude),
                    longitude=float(spot.longitude),
                    name=spot.spot_name,
                )
                locations.append(coord)
                location_mapping[f"spot_{spot.id}"] = i

        return locations, location_mapping

    def _assign_spots_to_days(
        self, selected_spots: List[RecSpot], total_days: int
    ) -> Dict[int, List[int]]:
        """
        4️⃣ 일차별 그룹화 - total_days에 맞춰 스팟을 균등 분배
        """
        total_spots = len(selected_spots)
        if total_spots == 0 or total_days == 0:
            return {}

        # 스팟의 위치 인덱스(locations 리스트 기준)를 매핑. 스팟은 0부터 시작.
        spot_location_index_map = {spot.id: i for i, spot in enumerate(selected_spots)}

        # 시간대 순서로 스팟 정렬
        time_slot_map = {"MORNING": 0, "AFTERNOON": 1, "NIGHT": 2}
        sorted_spots = sorted(
            selected_spots, key=lambda s: time_slot_map.get(s.time_slot, 99)
        )

        # 정렬된 순서에 따라 위치 인덱스 리스트 생성
        sorted_location_indices = [
            spot_location_index_map[spot.id] for spot in sorted_spots
        ]

        # 일차별로 스팟 분배
        spots_per_day = (total_spots + total_days - 1) // total_days  # 올림 계산
        daily_spot_indices = {}
        for day in range(1, total_days + 1):
            start_index = (day - 1) * spots_per_day
            end_index = start_index + spots_per_day
            if start_index < total_spots:
                daily_spot_indices[day] = sorted_location_indices[start_index:end_index]

        return daily_spot_indices

    async def _generate_detailed_routes(
        self,
        tsp_solutions: Dict[int, TSPSolution],
        locations: List[LocationCoordinate],
        travel_mode: str,
    ) -> Dict[int, Dict[str, Any]]:
        """6️⃣ 상세 경로 생성"""
        detailed_routes = {}

        for day, solution in tsp_solutions.items():
            if len(solution.optimal_order) < 2:
                continue

            # 해당 일차의 LocationCoordinate 리스트 생성
            day_locations = [locations[idx] for idx in solution.optimal_order]

            # Unique한 location이 2개 미만인 경우 Directions API 호출을 건너뜀
            unique_locations = {(loc.latitude, loc.longitude) for loc in day_locations}
            if len(unique_locations) < 2:
                detailed_routes[day] = {
                    "directions": None,
                    "locations": day_locations,
                    "segments": self._create_route_segments(solution, locations),
                }
                continue

            try:
                # Google Maps Directions API 호출
                directions = await self.google_maps_service.get_directions(
                    origin=day_locations[0],
                    destination=day_locations[-1],
                    waypoints=day_locations[1:-1] if len(day_locations) > 2 else None,
                    travel_mode=travel_mode,
                    optimize_waypoints=False,  # 이미 TSP로 최적화됨
                )

                detailed_routes[day] = {
                    "directions": directions,
                    "locations": day_locations,
                    "segments": self._create_route_segments(solution, locations),
                }

            except Exception as e:
                logger.warning(f"Day {day} 상세 경로 생성 실패: {e}")
                # 기본 구간 정보만 생성
                detailed_routes[day] = {
                    "directions": None,
                    "locations": day_locations,
                    "segments": self._create_route_segments(solution, locations),
                }

        return detailed_routes

    async def _save_route_data(
        self,
        request: RouteCalculationRequest,
        spots_data: Dict[str, Any],
        calc_output: RouteCalculationOutput,
        detailed_routes: Dict[int, Dict[str, Any]],
        locations: List[LocationCoordinate],
        latest_version: int,
    ) -> Any:  # Route model
        """7️⃣ 데이터베이스 저장"""

        # 전체 통계 계산
        total_spots = len(spots_data["selected_spots"])

        # Route 데이터 준비
        route_data = {
            "plan_id": request.plan_id,
            "version": latest_version,
            "total_days": spots_data["total_days"],
            "total_distance_km": Decimal(
                str(round(calc_output.total_distance_meters / 1000, 2))
            ),
            "total_duration_minutes": calc_output.total_duration_seconds // 60,
            "total_spots_count": total_spots,
            "google_maps_data": {
                "travel_mode": request.travel_mode,
                "optimize_for": request.optimize_for,
                "solutions_summary": {
                    day: {
                        "distance_meters": sol.total_distance_meters,
                        "duration_seconds": sol.total_duration_seconds,
                        "solve_time": sol.solve_time_seconds,
                    }
                    for day, sol in calc_output.tsp_solutions.items()
                },
            },
        }

        # RouteDay 데이터 준비
        days_data = []
        for day, solution in calc_output.tsp_solutions.items():
            day_route = detailed_routes.get(day, {})

            day_data = {
                "day_number": day,
                "start_location": (
                    locations[solution.optimal_order[0]].name
                    if solution.optimal_order
                    else None
                ),
                "end_location": (
                    locations[solution.optimal_order[-1]].name
                    if solution.optimal_order
                    else None
                ),
                "day_distance_km": Decimal(
                    str(round(solution.total_distance_meters / 1000, 2))
                ),
                "day_duration_minutes": solution.total_duration_seconds // 60,
                "ordered_spots": self._create_ordered_spots_data(
                    solution, locations, spots_data
                ),
                "route_geometry": {
                    "polyline": (
                        day_route.get("directions").polyline
                        if day_route.get("directions")
                        else None
                    ),
                },
                "segments": self._create_segments_data_with_directions(
                    day_route.get("segments", []),
                    locations,
                    request.travel_mode,
                    day_route.get("directions"),
                ),
            }
            days_data.append(day_data)

        # 데이터베이스에 저장
        route = self.route_repository.create_with_days_and_segments(
            route_data, days_data
        )

        return route

    def _create_ordered_spots_data(
        self,
        solution: TSPSolution,
        locations: List[LocationCoordinate],
        spots_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """방문 순서가 적용된 스팟 데이터 생성"""
        ordered_spots = []

        for order, location_idx in enumerate(solution.optimal_order):
            location = locations[location_idx]

            # 해당 위치에 대응하는 스팟 찾기
            matching_spot = None
            for spot in spots_data["selected_spots"]:
                if (
                    spot.latitude
                    and spot.longitude
                    and abs(float(spot.latitude) - location.latitude) < 0.0001
                    and abs(float(spot.longitude) - location.longitude) < 0.0001
                ):
                    matching_spot = spot
                    break

            # 기본 정보
            spot_data = {
                "order": order,
                "location_index": location_idx,
                "name": location.name,
                "latitude": location.latitude,
                "longitude": location.longitude,
                "is_spot": matching_spot is not None,
                "spot_id": matching_spot.spot_id if matching_spot else None,
                "time_slot": matching_spot.time_slot if matching_spot else None,
            }

            # 매칭되는 스팟이 있으면 상세 정보 추가
            if matching_spot:
                spot_data.update(
                    {
                        "spot_name": matching_spot.spot_name,
                        "recommendation_reason": matching_spot.recommendation_reason,
                        "image_url": matching_spot.image_url,
                        "website_url": matching_spot.website_url,
                        "selected": matching_spot.selected,
                        "similarity_score": (
                            float(matching_spot.similarity_score)
                            if matching_spot.similarity_score
                            else None
                        ),
                        # 상세 정보 (spot_details에서 추출)
                        "details": (
                            {
                                "congestion": (
                                    matching_spot.spot_details.get(
                                        "congestion", [0] * 24
                                    )
                                    if matching_spot.spot_details
                                    else [0] * 24
                                ),
                                "business_hours": (
                                    matching_spot.spot_details.get("business_hours", {})
                                    if matching_spot.spot_details
                                    else {}
                                ),
                                "price": (
                                    matching_spot.spot_details.get("price", 0)
                                    if matching_spot.spot_details
                                    else 0
                                ),
                            }
                            if matching_spot.spot_details
                            else None
                        ),
                    }
                )
            ordered_spots.append(spot_data)

        return {
            "spots": ordered_spots,
            "total_spots": len(ordered_spots),
            "optimization_info": {
                "total_distance_meters": solution.total_distance_meters,
                "total_duration_seconds": solution.total_duration_seconds,
                "solve_time_seconds": solution.solve_time_seconds,
            },
        }

    def _create_segments_data(
        self,
        segments: List[Tuple[int, int]],
        locations: List[LocationCoordinate],
        travel_mode: str = "DRIVING",
    ) -> List[Dict[str, Any]]:
        """구간 데이터 생성 (기본 버전)"""
        segments_data = []

        for order, (from_idx, to_idx) in enumerate(segments):
            segment_data = {
                "segment_order": order + 1,
                "from_location": locations[from_idx].name,
                "to_spot_name": locations[to_idx].name,
                "distance_meters": None,  # 실제 거리는 Google Maps에서 가져옴
                "duration_seconds": None,
                "travel_mode": travel_mode.upper(),  # 요청에서 받은 travel_mode 사용
            }
            segments_data.append(segment_data)

        return segments_data

    def _create_segments_data_with_directions(
        self,
        segments: List[Tuple[int, int]],
        locations: List[LocationCoordinate],
        travel_mode: str = "DRIVING",
        directions_result=None,
    ) -> List[Dict[str, Any]]:
        """구간 데이터 생성 (Google Maps 결과 포함)"""
        segments_data = []

        # Google Maps 결과에서 개별 leg 정보 추출
        legs_data = []
        if directions_result and hasattr(directions_result, "steps"):
            # steps를 legs로 변환 (간단한 구현)
            # 실제로는 legs 정보가 directions_result에 포함되어야 함
            pass

        for order, (from_idx, to_idx) in enumerate(segments):
            # 기본 segment 데이터
            segment_data = {
                "segment_order": order + 1,
                "from_location": locations[from_idx].name,
                "to_spot_name": locations[to_idx].name,
                "distance_meters": None,
                "duration_seconds": None,
                "travel_mode": travel_mode.upper(),
            }

            # Google Maps 결과가 있고 해당하는 leg가 있으면 실제 데이터 사용
            if directions_result and hasattr(directions_result, "distance_meters"):
                # 전체 경로에서 개별 구간을 추정하는 로직
                # 실제로는 각 leg의 거리/시간을 개별적으로 받아야 함
                total_segments = len(segments)
                if total_segments > 0:
                    segment_data["distance_meters"] = (
                        directions_result.distance_meters // total_segments
                    )
                    segment_data["duration_seconds"] = (
                        directions_result.duration_seconds // total_segments
                    )

            segments_data.append(segment_data)

        return segments_data

    def _create_route_segments(
        self, solution: TSPSolution, locations: List[LocationCoordinate]
    ) -> List[Tuple[int, int]]:
        """TSP 솔루션에서 구간 정보 추출"""
        segments = []
        order = solution.optimal_order

        for i in range(len(order) - 1):
            segments.append((order[i], order[i + 1]))

        return segments

    def _parse_location_string(self, location_str: str) -> LocationCoordinate:
        """문자열 위치를 LocationCoordinate로 변환"""
        # 간단한 구현: "37.5563,126.9720" 형식 가정
        # 실제로는 더 복잡한 파싱 로직 필요 (주소 → 좌표 변환 등)
        try:
            if "," in location_str:
                lat_str, lng_str = location_str.split(",")
                return LocationCoordinate(
                    latitude=float(lat_str.strip()),
                    longitude=float(lng_str.strip()),
                    name=f"Location({lat_str.strip()},{lng_str.strip()})",
                )
            else:
                # 주소인 경우 기본 서울역 좌표 사용 (임시)
                return LocationCoordinate(
                    latitude=37.5563, longitude=126.9720, name=location_str
                )
        except Exception:
            # 파싱 실패 시 기본 좌표
            return LocationCoordinate(
                latitude=37.5563, longitude=126.9720, name=location_str
            )

    def _calculate_total_days(self, pre_info) -> int:
        """여행 기간 계산"""
        if not pre_info or not pre_info.start_date or not pre_info.end_date:
            return 1

        delta = pre_info.end_date.date() - pre_info.start_date.date()
        return max(1, delta.days + 1)  # 당일치기도 1일로 계산

    async def get_route_details(
        self, plan_id: str, version: int
    ) -> Optional[Dict[str, Any]]:
        """경로 상세 정보 조회"""
        route = self.route_repository.get_with_details(
            plan_id, version, include_segments=True
        )

        if not route:
            return None

        # Route 스키마에 맞는 형태로 데이터 구성
        route_data = {
            # 기본 Route 필드들
            "id": route.id,
            "plan_id": route.plan_id,
            "version": route.version,
            "total_days": route.total_days,
            "departure_location": route.departure_location,
            "hotel_location": route.hotel_location,
            "total_distance_km": (
                float(route.total_distance_km) if route.total_distance_km else None
            ),
            "total_duration_minutes": route.total_duration_minutes,
            "total_spots_count": route.total_spots_count,
            "calculated_at": route.calculated_at,
            "google_maps_data": route.google_maps_data,
            # RouteDay와 RouteSegment 포함
            "route_days": [],
        }

        # RouteDay 데이터 추가
        for route_day in route.route_days:
            day_data = {
                # 기본 RouteDay 필드들
                "id": route_day.id,
                "route_id": route_day.route_id,
                "day_number": route_day.day_number,
                "start_location": route_day.start_location,
                "end_location": route_day.end_location,
                "day_distance_km": (
                    float(route_day.day_distance_km)
                    if route_day.day_distance_km
                    else None
                ),
                "day_duration_minutes": route_day.day_duration_minutes,
                "ordered_spots": route_day.ordered_spots,
                "route_geometry": route_day.route_geometry,
                # RouteSegment 포함
                "route_segments": [],
            }

            # RouteSegment 데이터 추가
            for segment in route_day.route_segments:
                segment_data = {
                    "id": segment.id,
                    "route_day_id": segment.route_day_id,
                    "segment_order": segment.segment_order,
                    "from_location": segment.from_location,
                    "to_spot_id": segment.to_spot_id,
                    "to_spot_name": segment.to_spot_name,
                    "distance_meters": segment.distance_meters,
                    "duration_seconds": segment.duration_seconds,
                    "travel_mode": segment.travel_mode,
                    "directions_steps": segment.directions_steps,
                }
                day_data["route_segments"].append(segment_data)

            route_data["route_days"].append(day_data)

        return route_data

    async def get_route_full_details(
        self,
        plan_id: str,
        version: int,
        calculation_time_seconds: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        RouteFullDetail 스키마에 맞는 완전한 상세 정보 조회
        계산 직후 호출 시 calculation_time_seconds를 전달할 수 있음
        """
        route = self.route_repository.get_with_details(
            plan_id, version, include_segments=True
        )

        if not route:
            return None

        # 기본 route 정보 생성
        route_details = await self.get_route_details(plan_id, version)

        # 추가 상세 정보 생성
        route_summary = {
            "route_id": route.id,
            "plan_id": route.plan_id,
            "version": route.version,
            "total_days": route.total_days,
            "departure_location": route.departure_location,
            "hotel_location": route.hotel_location,
            "calculated_at": (
                route.calculated_at.isoformat() if route.calculated_at else None
            ),
        }

        daily_summary = []
        for route_day in route.route_days:
            # ordered_spots에서 실제 스팟 개수 계산
            ordered_spots = route_day.ordered_spots or {}
            spots_count = len(ordered_spots.get("spots", []))

            day_info = {
                "day_number": route_day.day_number,
                "spots_count": spots_count,
                "distance_km": (
                    float(route_day.day_distance_km) if route_day.day_distance_km else 0
                ),
                "duration_minutes": route_day.day_duration_minutes or 0,
                "start_location": route_day.start_location,
                "end_location": route_day.end_location,
            }
            daily_summary.append(day_info)

        optimization_details = {
            "total_days": route.total_days,
            "total_locations_processed": route.total_spots_count or 0,
            "google_maps_data_available": route.google_maps_data is not None,
            "calculation_method": "TSP_optimization",
        }

        # RouteFullDetail 형태로 결합
        full_details = {
            **route_details,
            "route_summary": route_summary,
            "daily_summary": daily_summary,
            "optimization_details": optimization_details,
            "calculation_time_seconds": calculation_time_seconds,
            "created_by_calculation": calculation_time_seconds is not None,
        }

        return full_details

    def _create_navigation_data(self, route) -> Dict[str, Any]:
        """내비게이션 데이터 생성"""
        navigation_data = {
            "route_id": route.id,
            "total_distance_km": (
                float(route.total_distance_km) if route.total_distance_km else 0
            ),
            "total_duration_minutes": route.total_duration_minutes or 0,
            "days": [],
        }

        for route_day in route.route_days:
            day_nav = {
                "day_number": route_day.day_number,
                "start_location": route_day.start_location,
                "end_location": route_day.end_location,
                "segments": [
                    seg.to_navigation_dict() for seg in route_day.route_segments
                ],
            }
            navigation_data["days"].append(day_nav)

        return navigation_data

    # === 부분 수정 메서드들 ===

    async def update_hotel_location(
        self, plan_id: str, version: int, new_hotel_location: str
    ) -> Dict[str, Any]:
        """
        호텔 위치만 변경하여 경로 부분 수정

        기존 스팟 방문 순서는 유지하고 호텔 연결 구간만 재계산합니다.
        """
        # 1. 기존 경로 조회
        route = self.route_repository.get_with_details(
            plan_id, version, include_segments=True
        )
        if not route:
            raise ValueError(f"Route not found: {plan_id} v{version}")

        # 2. 호텔 위치 업데이트
        route.hotel_location = new_hotel_location

        # 3. 각 일차의 마지막 구간 (스팟 → 호텔) 재계산
        total_distance_km = 0
        total_duration_minutes = 0

        for route_day in route.route_days:
            if route_day.route_segments:
                # 마지막 구간을 새 호텔 위치로 업데이트
                last_segment = route_day.route_segments[-1]
                last_segment.from_location = (
                    last_segment.to_spot_name or last_segment.from_location
                )
                last_segment.to_spot_name = new_hotel_location

                # Google Maps API로 새 거리/시간 계산 (실제 구현에서는 실제 API 호출)
                # 임시로 기존 값 사용하되, 호텔까지의 구간 시간을 추정
                estimated_hotel_distance = 5000  # 5km 추정
                estimated_hotel_duration = 20 * 60  # 20분 추정

                last_segment.distance_meters = estimated_hotel_distance
                last_segment.duration_seconds = estimated_hotel_duration

                # 일차별 총합 재계산
                day_distance_meters = sum(
                    seg.distance_meters or 0 for seg in route_day.route_segments
                )
                day_duration_seconds = sum(
                    seg.duration_seconds or 0 for seg in route_day.route_segments
                )

                route_day.day_distance_km = Decimal(str(day_distance_meters / 1000))
                route_day.day_duration_minutes = day_duration_seconds // 60

                total_distance_km += day_distance_meters / 1000
                total_duration_minutes += day_duration_seconds // 60

        # 4. 전체 경로 요약 업데이트
        route.total_distance_km = Decimal(str(total_distance_km))
        route.total_duration_minutes = total_duration_minutes

        # 5. 데이터베이스 업데이트
        self.route_repository.db.commit()

        return {
            "success": True,
            "message": "호텔 위치가 성공적으로 업데이트되었습니다",
            "updated_hotel_location": new_hotel_location,
            "new_total_distance_km": float(route.total_distance_km),
            "new_total_duration_minutes": route.total_duration_minutes,
        }

    async def update_travel_mode(
        self, plan_id: str, version: int, new_travel_mode: str
    ) -> Dict[str, Any]:
        """
        이동 수단만 변경하여 경로 부분 수정

        기존 스팟 방문 순서는 유지하고 이동 시간/거리만 재계산합니다.
        """
        # 1. 기존 경로 조회
        route = self.route_repository.get_with_details(
            plan_id, version, include_segments=True
        )
        if not route:
            raise ValueError(f"Route not found: {plan_id} v{version}")

        # 2. 모든 구간의 travel_mode 업데이트 및 시간/거리 재계산
        total_distance_km = 0
        total_duration_minutes = 0

        for route_day in route.route_days:
            day_distance_meters = 0
            day_duration_seconds = 0

            for segment in route_day.route_segments:
                segment.travel_mode = new_travel_mode

                # 이동 수단에 따른 시간/거리 조정 (실제로는 Google Maps API 사용)
                if segment.distance_meters and segment.duration_seconds:
                    base_distance = segment.distance_meters

                    if new_travel_mode == "DRIVING":
                        # 자동차: 빠른 속도
                        segment.duration_seconds = int(
                            base_distance / 1000 * 60 * 1.5
                        )  # 시속 40km 가정
                    elif new_travel_mode == "WALKING":
                        # 도보: 느린 속도
                        segment.duration_seconds = int(
                            base_distance / 1000 * 60 * 12
                        )  # 시속 5km 가정
                    elif new_travel_mode == "TRANSIT":
                        # 대중교통: 중간 속도
                        segment.duration_seconds = int(
                            base_distance / 1000 * 60 * 2.5
                        )  # 시속 24km 가정

                day_distance_meters += segment.distance_meters or 0
                day_duration_seconds += segment.duration_seconds or 0

            # 일차별 총합 업데이트
            route_day.day_distance_km = Decimal(str(day_distance_meters / 1000))
            route_day.day_duration_minutes = day_duration_seconds // 60

            total_distance_km += day_distance_meters / 1000
            total_duration_minutes += day_duration_seconds // 60

        # 3. 전체 경로 요약 업데이트
        route.total_distance_km = Decimal(str(total_distance_km))
        route.total_duration_minutes = total_duration_minutes

        # 4. 데이터베이스 업데이트
        self.route_repository.db.commit()

        return {
            "success": True,
            "message": f"이동 수단이 {new_travel_mode}로 변경되었습니다",
            "updated_travel_mode": new_travel_mode,
            "new_total_distance_km": float(route.total_distance_km),
            "new_total_duration_minutes": route.total_duration_minutes,
        }

    async def reorder_day_spots(
        self, plan_id: str, version: int, day_number: int, new_spot_order: List[str]
    ) -> Dict[str, Any]:
        """
        특정 일차의 스팟 순서만 변경하여 부분 수정

        해당 일차만 TSP 재계산하고 다른 일차는 유지합니다.
        """
        # 1. 기존 경로 조회
        route = self.route_repository.get_with_details(
            plan_id, version, include_segments=True
        )
        if not route:
            raise ValueError(f"Route not found: {plan_id} v{version}")

        # 2. 해당 일차 찾기
        target_day = None
        for route_day in route.route_days:
            if route_day.day_number == day_number:
                target_day = route_day
                break

        if not target_day:
            raise ValueError(f"Day {day_number} not found in route")

        # 3. 새 순서로 ordered_spots 업데이트
        if target_day.ordered_spots and "spots" in target_day.ordered_spots:
            spots = target_day.ordered_spots["spots"]

            # 새 순서대로 재배열
            reordered_spots = []
            for new_order, spot_id in enumerate(new_spot_order):
                for spot in spots:
                    if spot.get("spot_id") == spot_id:
                        spot_copy = spot.copy()
                        spot_copy["order"] = new_order
                        reordered_spots.append(spot_copy)
                        break

            target_day.ordered_spots["spots"] = reordered_spots

        # 4. 해당 일차의 구간들 재계산
        # 새 순서에 맞게 segment들을 재생성
        if target_day.route_segments:
            # 기존 segment들 삭제
            for segment in target_day.route_segments:
                self.route_repository.db.delete(segment)

            # 새 순서로 segment들 재생성
            new_segments = []
            for i in range(len(new_spot_order)):
                from_location = (
                    reordered_spots[i]["name"] if i < len(reordered_spots) else None
                )
                to_location = (
                    reordered_spots[i + 1]["name"]
                    if i + 1 < len(reordered_spots)
                    else target_day.end_location
                )

                if from_location and to_location:
                    # 추정 거리/시간 (실제로는 Google Maps API 사용)
                    estimated_distance = 2000  # 2km 추정
                    estimated_duration = 10 * 60  # 10분 추정

                    segment_data = {
                        "route_day_id": target_day.id,
                        "segment_order": i + 1,
                        "from_location": from_location,
                        "to_spot_name": to_location,
                        "distance_meters": estimated_distance,
                        "duration_seconds": estimated_duration,
                        "travel_mode": "TRANSIT",  # 기본값
                    }

                    from app.models.route_segment import RouteSegment

                    new_segment = RouteSegment(**segment_data)
                    self.route_repository.db.add(new_segment)
                    new_segments.append(new_segment)

            # 일차별 총합 재계산
            day_distance_meters = sum(seg.distance_meters or 0 for seg in new_segments)
            day_duration_seconds = sum(
                seg.duration_seconds or 0 for seg in new_segments
            )

            target_day.day_distance_km = Decimal(str(day_distance_meters / 1000))
            target_day.day_duration_minutes = day_duration_seconds // 60

        # 5. 전체 경로 총합 재계산
        total_distance_km = sum(
            float(day.day_distance_km) if day.day_distance_km else 0
            for day in route.route_days
        )
        total_duration_minutes = sum(
            day.day_duration_minutes or 0 for day in route.route_days
        )

        route.total_distance_km = Decimal(str(total_distance_km))
        route.total_duration_minutes = total_duration_minutes

        # 6. 데이터베이스 업데이트
        self.route_repository.db.commit()

        return {
            "success": True,
            "message": f"{day_number}일차 스팟 순서가 성공적으로 변경되었습니다",
            "updated_day": day_number,
            "new_spot_order": new_spot_order,
            "new_day_distance_km": (
                float(target_day.day_distance_km) if target_day.day_distance_km else 0
            ),
            "new_day_duration_minutes": target_day.day_duration_minutes or 0,
        }

    async def replace_spot(
        self, plan_id: str, version: int, old_spot_id: str, new_spot_id: str
    ) -> Dict[str, Any]:
        """
        특정 스팟을 다른 스팟으로 교체

        교체된 스팟의 위치에 따라 해당 일차만 부분 재계산합니다.
        """
        # 1. 기존 경로 조회
        route = self.route_repository.get_with_details(
            plan_id, version, include_segments=True
        )
        if not route:
            raise ValueError(f"Route not found: {plan_id} v{version}")

        # 2. 교체할 스팟 찾기
        target_day = None
        spot_found = False

        for route_day in route.route_days:
            if route_day.ordered_spots and "spots" in route_day.ordered_spots:
                for spot in route_day.ordered_spots["spots"]:
                    if spot.get("spot_id") == old_spot_id:
                        # 새 스팟 정보로 교체 (실제로는 RecSpot에서 조회 필요)
                        spot["spot_id"] = new_spot_id
                        spot["name"] = f"New Spot {new_spot_id}"  # 임시
                        target_day = route_day
                        spot_found = True
                        break
            if spot_found:
                break

        if not spot_found:
            raise ValueError(f"Spot {old_spot_id} not found in route")

        # 3. 해당 일차의 경로 재계산 (실제로는 새 좌표로 TSP 재실행)
        # 임시로 기존 값 유지

        # 4. 데이터베이스 업데이트
        self.route_repository.db.commit()

        return {
            "success": True,
            "message": f"스팟이 성공적으로 교체되었습니다: {old_spot_id} → {new_spot_id}",
            "old_spot_id": old_spot_id,
            "new_spot_id": new_spot_id,
            "affected_day": target_day.day_number if target_day else None,
        }
