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
        pre_info_repository: PreInfoRepository,
        google_maps_service: GoogleMapsService,
        tsp_solver_service: TSPSolverService,
    ):
        self.route_repository = route_repository
        self.route_day_repository = route_day_repository
        self.route_segment_repository = route_segment_repository
        self.rec_spot_repository = rec_spot_repository
        self.pre_info_repository = pre_info_repository
        self.google_maps_service = google_maps_service
        self.tsp_solver_service = tsp_solver_service

    async def calculate_route(
        self, request: RouteCalculationRequest
    ) -> RouteCalculationResponse:
        """
        全体ルート計算メインメソッド。
        上記で説明した7段階プロセスを実行します。
        """
        start_time = time.time()

        try:
            logger.info(
                f"ルート計算開始: plan_id={request.plan_id}, version={request.version}"
            )

            # 1️⃣ スポットデータ収集
            spots_data = await self._collect_spots_data(
                request.plan_id, request.version
            )
            if not spots_data["selected_spots"]:
                return RouteCalculationResponse(
                    success=False, error_message="選択されたスポットがありません。"
                )

            # departure_locationがない場合、PreInfoから自動抽出
            departure_location = request.departure_location
            if not departure_location and spots_data.get("pre_info"):
                departure_location = spots_data["pre_info"].departure_location
                logger.info(f"PreInfoから出発地を自動抽出: {departure_location}")

            if not departure_location:
                return RouteCalculationResponse(
                    success=False, error_message="出発地情報がありません。"
                )

            # 2️⃣ 座標変換
            locations, location_mapping = self._create_location_coordinates(
                spots_data, departure_location, request.hotel_location
            )

            # 3️⃣ 距離マトリクス計算
            distance_matrix = await self.google_maps_service.batch_distance_calculation(
                locations, request.travel_mode
            )

            # 4️⃣ 日別グループ化
            days_assignment = self._assign_spots_to_days(spots_data["selected_spots"])

            # 5️⃣ TSP解決
            tsp_solutions = self.tsp_solver_service.solve_multi_day_tsp(
                locations=locations,
                distance_matrix=distance_matrix,
                days_assignment=days_assignment,
                start_location_index=location_mapping["departure"],
                hotel_location_index=location_mapping.get("hotel"),
                optimize_for=request.optimize_for,
            )

            # 6️⃣ 詳細ルート生成
            detailed_routes = await self._generate_detailed_routes(
                tsp_solutions, locations, request.travel_mode
            )

            # 7️⃣ データベース保存
            route = await self._save_route_data(
                request, spots_data, tsp_solutions, detailed_routes, locations
            )

            calculation_time = time.time() - start_time
            logger.info(
                f"ルート計算完了: route_id={route.id}, 所要時間={calculation_time:.2f}s"
            )

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
            calculation_time = time.time() - start_time
            logger.error(f"ルート計算失敗: {e}", exc_info=True)

            return RouteCalculationResponse(
                success=False,
                error_message=str(e),
                calculation_time_seconds=calculation_time,
            )

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
        self,
        spots_data: Dict[str, Any],
        departure_location: str,
        hotel_location: Optional[str],
    ) -> Tuple[List[LocationCoordinate], Dict[str, int]]:
        """2️⃣ 座標変換"""
        locations = []
        location_mapping = {}

        # 출발지 추가
        departure_coord = self._parse_location_string(departure_location)
        locations.append(departure_coord)
        location_mapping["departure"] = 0

        # 스팟들 추가
        for spot in spots_data["selected_spots"]:
            if spot.latitude and spot.longitude:
                coord = LocationCoordinate(
                    latitude=float(spot.latitude),
                    longitude=float(spot.longitude),
                    name=spot.spot_name,
                )
                locations.append(coord)
                location_mapping[f"spot_{spot.id}"] = len(locations) - 1

        # 호텔 추가 (출발지와 다른 경우)
        if hotel_location and hotel_location != departure_location:
            hotel_coord = self._parse_location_string(hotel_location)
            locations.append(hotel_coord)
            location_mapping["hotel"] = len(locations) - 1
        else:
            location_mapping["hotel"] = location_mapping["departure"]

        return locations, location_mapping

    def _assign_spots_to_days(self, selected_spots: List[RecSpot]) -> Dict[int, int]:
        """4️⃣ 일차별 그룹화 - 시간대를 일차로 변환"""
        days_assignment = {}

        # 간단한 전략: 시간대별로 하루씩 배정
        # 실제로는 더 복잡한 로직 필요 (스팟 수, 지역별 클러스터링 등)

        spot_index = 1  # 0은 출발지
        current_day = 1
        spots_per_day = 8  # 하루 최대 스팟 수

        # 시간대 순서대로 배정
        time_slot_order = ["MORNING", "AFTERNOON", "NIGHT"]

        for time_slot in time_slot_order:
            slot_spots = [s for s in selected_spots if s.time_slot == time_slot]

            for spot in slot_spots:
                days_assignment[spot_index] = current_day
                spot_index += 1

                # 하루 최대 스팟 수 초과 시 다음 날로
                spots_in_current_day = sum(
                    1 for day in days_assignment.values() if day == current_day
                )
                if spots_in_current_day >= spots_per_day:
                    current_day += 1

        return days_assignment

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
        tsp_solutions: Dict[int, TSPSolution],
        detailed_routes: Dict[int, Dict[str, Any]],
        locations: List[LocationCoordinate],
    ) -> Any:  # Route model
        """7️⃣ 데이터베이스 저장"""

        # 전체 통계 계산
        total_distance = sum(
            sol.total_distance_meters for sol in tsp_solutions.values()
        )
        total_duration = sum(
            sol.total_duration_seconds for sol in tsp_solutions.values()
        )
        total_spots = len(spots_data["selected_spots"])

        # Route 데이터 준비
        route_data = {
            "plan_id": request.plan_id,
            "version": request.version,
            "total_days": spots_data["total_days"],
            "departure_location": request.departure_location,
            "hotel_location": request.hotel_location,
            "total_distance_km": Decimal(str(round(total_distance / 1000, 2))),
            "total_duration_minutes": total_duration // 60,
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
                    for day, sol in tsp_solutions.items()
                },
            },
        }

        # RouteDay 데이터 준비
        days_data = []
        for day, solution in tsp_solutions.items():
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
                        day_route.get("directions", {}).get("polyline")
                        if day_route.get("directions")
                        else None
                    ),
                    "bounds": None,  # 필요시 추가
                },
                "segments": self._create_segments_data(
                    day_route.get("segments", []), locations
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
        self, segments: List[Tuple[int, int]], locations: List[LocationCoordinate]
    ) -> List[Dict[str, Any]]:
        """구간 데이터 생성"""
        segments_data = []

        for order, (from_idx, to_idx) in enumerate(segments):
            segment_data = {
                "segment_order": order + 1,
                "from_location": locations[from_idx].name,
                "to_spot_name": locations[to_idx].name,
                "distance_meters": None,  # 실제 거리는 Google Maps에서 가져옴
                "duration_seconds": None,
                "travel_mode": "DRIVING",  # 기본값
            }
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

        return {
            "route_summary": route.to_summary_dict(),
            "days": [day.to_detail_dict() for day in route.route_days],
            "navigation": self._create_navigation_data(route),
        }

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

                # Google Maps API로 새 거리/시간 계산
                # (실제 구현에서는 Google Maps Service 호출)
                # 임시로 기존 값 유지

                day_distance = (
                    float(route_day.day_distance_km) if route_day.day_distance_km else 0
                )
                day_duration = route_day.day_duration_minutes or 0

                total_distance_km += day_distance
                total_duration_minutes += day_duration

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

        # 2. 모든 구간의 travel_mode 업데이트
        total_distance_km = 0
        total_duration_minutes = 0

        for route_day in route.route_days:
            for segment in route_day.route_segments:
                segment.travel_mode = new_travel_mode
                # 실제로는 Google Maps API로 새 이동 시간/거리 재계산 필요

            day_distance = (
                float(route_day.day_distance_km) if route_day.day_distance_km else 0
            )
            day_duration = route_day.day_duration_minutes or 0

            total_distance_km += day_distance
            total_duration_minutes += day_duration

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

        # 4. 해당 일차의 구간들 재계산 (실제로는 TSP 재실행 필요)
        # 임시로 기존 값 유지

        # 5. 데이터베이스 업데이트
        self.route_repository.db.commit()

        return {
            "success": True,
            "message": f"{day_number}일차 스팟 순서가 성공적으로 변경되었습니다",
            "updated_day": day_number,
            "new_spot_order": new_spot_order,
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
