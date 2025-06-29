import asyncio
import aiohttp
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from app.core.config import settings


logger = logging.getLogger(__name__)


@dataclass
class LocationCoordinate:
    """위치 좌표"""

    latitude: float
    longitude: float
    name: Optional[str] = None

    def to_string(self) -> str:
        """Google Maps API용 문자열 변환"""
        return f"{self.latitude},{self.longitude}"


@dataclass
class DistanceMatrixResult:
    """Distance Matrix API 결과"""

    from_location: LocationCoordinate
    to_location: LocationCoordinate
    distance_meters: int
    duration_seconds: int
    status: str


@dataclass
class DirectionsResult:
    """Directions API 결과"""

    distance_meters: int
    duration_seconds: int
    polyline: str
    steps: List[Dict[str, Any]]
    status: str


class GoogleMapsService:
    """
    Google Maps API 서비스.
    Single Responsibility Principle: Google Maps API 호출만 담당
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GOOGLE_MAP_API_KEY
        self.base_url = "https://maps.googleapis.com/maps/api"

        if not self.api_key:
            logger.warning("Google Maps API 키가 설정되지 않았습니다.")

    async def get_distance_matrix(
        self,
        origins: List[LocationCoordinate],
        destinations: List[LocationCoordinate],
        travel_mode: str = "driving",
    ) -> List[List[DistanceMatrixResult]]:
        """
        Distance Matrix API를 사용하여 여러 지점 간 거리/시간 계산

        Args:
            origins: 출발지 목록
            destinations: 목적지 목록
            travel_mode: 이동 수단 (driving, walking, transit, bicycling)

        Returns:
            origins x destinations 매트릭스 결과
        """
        if not self.api_key:
            raise ValueError("Google Maps API 키가 필요합니다.")

        # API 요청 파라미터 구성
        origins_str = "|".join([loc.to_string() for loc in origins])
        destinations_str = "|".join([loc.to_string() for loc in destinations])

        params = {
            "origins": origins_str,
            "destinations": destinations_str,
            "mode": travel_mode.lower(),
            "units": "metric",
            "language": "ko",
            "key": self.api_key,
        }

        url = f"{self.base_url}/distancematrix/json"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        raise Exception(f"Google Maps API 오류: {response.status}")

                    data = await response.json()

                    if data.get("status") != "OK":
                        raise Exception(
                            f"Google Maps API 응답 오류: {data.get('status')}"
                        )

                    return self._parse_distance_matrix_response(
                        data, origins, destinations
                    )

        except Exception as e:
            logger.error(f"Distance Matrix API 호출 실패: {e}")
            raise

    async def get_directions(
        self,
        origin: LocationCoordinate,
        destination: LocationCoordinate,
        waypoints: Optional[List[LocationCoordinate]] = None,
        travel_mode: str = "driving",
        optimize_waypoints: bool = True,
    ) -> DirectionsResult:
        """
        Directions API를 사용하여 경로 탐색

        Args:
            origin: 출발지
            destination: 목적지
            waypoints: 경유지 목록
            travel_mode: 이동 수단
            optimize_waypoints: 경유지 순서 최적화 여부

        Returns:
            경로 정보
        """
        if not self.api_key:
            raise ValueError("Google Maps API 키가 필요합니다.")

        # waypoints가 단일 객체일 경우 리스트로 변환
        if waypoints and not isinstance(waypoints, list):
            waypoints = [waypoints]

        params = {
            "origin": origin.to_string(),
            "destination": destination.to_string(),
            "mode": travel_mode.lower(),
            "units": "metric",
            "language": "ko",
            "key": self.api_key,
        }

        # 경유지 추가
        if waypoints:
            waypoints_str = "|".join([wp.to_string() for wp in waypoints])
            if optimize_waypoints:
                waypoints_str = f"optimize:true|{waypoints_str}"
            params["waypoints"] = waypoints_str

        url = f"{self.base_url}/directions/json"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        raise Exception(f"Google Maps API 오류: {response.status}")

                    data = await response.json()

                    if data.get("status") != "OK":
                        raise Exception(
                            f"Google Maps API 응답 오류: {data.get('status')}"
                        )

                    return self._parse_directions_response(data)

        except Exception as e:
            logger.error(f"Directions API 호출 실패: {e}")
            raise

    async def calculate_optimal_route(
        self,
        start_location: LocationCoordinate,
        end_location: LocationCoordinate,
        waypoints: List[LocationCoordinate],
        travel_mode: str = "driving",
    ) -> Tuple[List[LocationCoordinate], DirectionsResult]:
        """
        최적 경로 계산 (TSP 해결을 위한 Google Maps 최적화 사용)

        Args:
            start_location: 시작점
            end_location: 종료점
            waypoints: 방문할 지점들
            travel_mode: 이동 수단

        Returns:
            (최적 순서의 waypoints, 전체 경로 정보)
        """
        if not waypoints:
            # 경유지가 없으면 직접 경로
            directions = await self.get_directions(
                start_location, end_location, travel_mode=travel_mode
            )
            return [], directions

        # Google Maps의 waypoint 최적화 사용
        directions = await self.get_directions(
            start_location,
            end_location,
            waypoints=waypoints,
            travel_mode=travel_mode,
            optimize_waypoints=True,
        )

        # 최적화된 순서 추출 (Google Maps가 반환하는 waypoint_order 사용)
        # 실제 구현에서는 response에서 waypoint_order를 파싱해야 함
        optimized_waypoints = waypoints  # 임시로 원본 순서 사용

        return optimized_waypoints, directions

    async def batch_distance_calculation(
        self, locations: List[LocationCoordinate], travel_mode: str = "driving"
    ) -> Dict[Tuple[int, int], DistanceMatrixResult]:
        """
        모든 지점 간 거리 매트릭스 계산 (배치 처리)

        Args:
            locations: 모든 위치 목록
            travel_mode: 이동 수단

        Returns:
            {(from_index, to_index): DistanceMatrixResult} 딕셔너리
        """
        if len(locations) <= 1:
            return {}

        # Google Maps API 제한: 한 번에 최대 25개 origins x 25개 destinations
        max_batch_size = 25
        results = {}

        # 배치 처리
        for i in range(0, len(locations), max_batch_size):
            for j in range(0, len(locations), max_batch_size):
                origins_batch = locations[i : i + max_batch_size]
                destinations_batch = locations[j : j + max_batch_size]

                try:
                    matrix_results = await self.get_distance_matrix(
                        origins_batch, destinations_batch, travel_mode
                    )

                    # 결과를 딕셔너리에 저장
                    for orig_idx, row in enumerate(matrix_results):
                        for dest_idx, result in enumerate(row):
                            global_orig_idx = i + orig_idx
                            global_dest_idx = j + dest_idx
                            results[(global_orig_idx, global_dest_idx)] = result

                except Exception as e:
                    logger.error(f"배치 거리 계산 실패 (batch {i}-{j}): {e}")
                    # 실패한 배치에 대해서는 기본값 설정
                    for orig_idx in range(len(origins_batch)):
                        for dest_idx in range(len(destinations_batch)):
                            global_orig_idx = i + orig_idx
                            global_dest_idx = j + dest_idx
                            if global_orig_idx != global_dest_idx:
                                results[(global_orig_idx, global_dest_idx)] = (
                                    DistanceMatrixResult(
                                        from_location=origins_batch[orig_idx],
                                        to_location=destinations_batch[dest_idx],
                                        distance_meters=999999,  # 매우 큰 값
                                        duration_seconds=999999,
                                        status="ERROR",
                                    )
                                )

                # API 호출 제한을 피하기 위한 지연
                await asyncio.sleep(0.1)

        return results

    def _parse_distance_matrix_response(
        self,
        response_data: Dict[str, Any],
        origins: List[LocationCoordinate],
        destinations: List[LocationCoordinate],
    ) -> List[List[DistanceMatrixResult]]:
        """Distance Matrix API 응답 파싱"""
        results = []

        for orig_idx, row in enumerate(response_data.get("rows", [])):
            row_results = []

            for dest_idx, element in enumerate(row.get("elements", [])):
                status = element.get("status", "UNKNOWN")

                if status == "OK":
                    distance = element.get("distance", {}).get("value", 0)
                    duration = element.get("duration", {}).get("value", 0)
                else:
                    distance = 999999
                    duration = 999999

                result = DistanceMatrixResult(
                    from_location=origins[orig_idx],
                    to_location=destinations[dest_idx],
                    distance_meters=distance,
                    duration_seconds=duration,
                    status=status,
                )
                row_results.append(result)

            results.append(row_results)

        return results

    def _parse_directions_response(
        self, response_data: Dict[str, Any]
    ) -> DirectionsResult:
        """Directions API 응답 파싱"""
        routes = response_data.get("routes", [])
        if not routes:
            raise Exception("경로를 찾을 수 없습니다.")

        route = routes[0]  # 첫 번째 경로 사용
        legs = route.get("legs", [])

        # 전체 거리와 시간 계산
        total_distance = sum(leg.get("distance", {}).get("value", 0) for leg in legs)
        total_duration = sum(leg.get("duration", {}).get("value", 0) for leg in legs)

        # 전체 경로 폴리라인
        polyline = route.get("overview_polyline", {}).get("points", "")

        # 모든 step 수집
        all_steps = []
        for leg in legs:
            all_steps.extend(leg.get("steps", []))

        return DirectionsResult(
            distance_meters=total_distance,
            duration_seconds=total_duration,
            polyline=polyline,
            steps=all_steps,
            status="OK",
        )
