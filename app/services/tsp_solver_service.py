import logging
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
import math

from app.services.google_maps_service import LocationCoordinate, DistanceMatrixResult


logger = logging.getLogger(__name__)


@dataclass
class TSPSolution:
    """TSP 해결 결과"""

    optimal_order: List[int]  # 최적 방문 순서 (인덱스)
    total_distance_meters: int
    total_duration_seconds: int
    route_segments: List[Tuple[int, int]]  # (from_index, to_index) 쌍들
    solve_time_seconds: float


class TSPSolverService:
    """
    TSP(Traveling Salesman Problem) 해결 서비스.
    Single Responsibility Principle: TSP 최적화만 담당
    """

    def __init__(self):
        self.max_locations = 50  # OR-Tools TSP 제한

    def solve_tsp(
        self,
        distance_matrix: Dict[Tuple[int, int], DistanceMatrixResult],
        num_locations: int,
        start_index: int = 0,
        end_index: Optional[int] = None,
        optimize_for: str = "distance",  # "distance" or "time"
    ) -> TSPSolution:
        """
        TSP 문제 해결

        Args:
            distance_matrix: 거리 매트릭스 딕셔너리
            num_locations: 전체 위치 수
            start_index: 시작 지점 인덱스
            end_index: 종료 지점 인덱스 (None이면 start_index와 동일)
            optimize_for: 최적화 기준 ("distance" 또는 "time")

        Returns:
            TSP 해결 결과
        """
        import time

        start_time = time.time()

        try:
            # OR-Tools 사용 시도
            solution = self._solve_with_ortools(
                distance_matrix, num_locations, start_index, end_index, optimize_for
            )
        except ImportError:
            logger.warning(
                "OR-Tools가 설치되지 않았습니다. 휴리스틱 방법을 사용합니다."
            )
            solution = self._solve_with_heuristic(
                distance_matrix, num_locations, start_index, end_index, optimize_for
            )
        except Exception as e:
            logger.error(f"OR-Tools TSP 해결 실패: {e}. 휴리스틱 방법을 사용합니다.")
            solution = self._solve_with_heuristic(
                distance_matrix, num_locations, start_index, end_index, optimize_for
            )

        solve_time = time.time() - start_time
        solution.solve_time_seconds = solve_time

        return solution

    def _solve_with_ortools(
        self,
        distance_matrix: Dict[Tuple[int, int], DistanceMatrixResult],
        num_locations: int,
        start_index: int,
        end_index: Optional[int],
        optimize_for: str,
    ) -> TSPSolution:
        """OR-Tools를 사용한 TSP 해결"""
        try:
            from ortools.constraint_solver import routing_enums_pb2
            from ortools.constraint_solver import pywrapcp
        except ImportError:
            raise ImportError("OR-Tools 패키지가 필요합니다: pip install ortools")

        # 거리 매트릭스를 2D 배열로 변환
        matrix = self._create_matrix_array(distance_matrix, num_locations, optimize_for)

        # TSP 모델 생성
        manager = pywrapcp.RoutingIndexManager(num_locations, 1, start_index)
        routing = pywrapcp.RoutingModel(manager)

        def distance_callback(from_index, to_index):
            """거리 콜백 함수"""
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return matrix[from_node][to_node]

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        # 종료 지점 설정
        if end_index is not None and end_index != start_index:
            routing.SetFixedCostOfAllVehicles(0)
            routing.AddVariableMinimizedByFinalizer(routing.End(0))

        # 검색 파라미터 설정
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        search_parameters.time_limit.seconds = 30  # 30초 제한

        # TSP 해결
        solution = routing.SolveWithParameters(search_parameters)

        if not solution:
            raise Exception("OR-Tools로 해결할 수 없습니다.")

        return self._parse_ortools_solution(
            solution, manager, routing, distance_matrix, optimize_for
        )

    def _solve_with_heuristic(
        self,
        distance_matrix: Dict[Tuple[int, int], DistanceMatrixResult],
        num_locations: int,
        start_index: int,
        end_index: Optional[int],
        optimize_for: str,
    ) -> TSPSolution:
        """휴리스틱 방법을 사용한 TSP 해결 (Nearest Neighbor + 2-opt)"""

        # 1. Nearest Neighbor로 초기 해 구성
        visited = [False] * num_locations
        route = [start_index]
        visited[start_index] = True
        current = start_index

        while len(route) < num_locations:
            best_next = None
            best_cost = float("inf")

            for next_idx in range(num_locations):
                if not visited[next_idx]:
                    cost = self._get_cost(
                        distance_matrix, current, next_idx, optimize_for
                    )
                    if cost < best_cost:
                        best_cost = cost
                        best_next = next_idx

            if best_next is not None:
                route.append(best_next)
                visited[best_next] = True
                current = best_next

        # 종료 지점이 다른 경우 마지막에 추가
        if end_index is not None and end_index != start_index:
            if end_index in route:
                route.remove(end_index)
            route.append(end_index)

        # 2. 2-opt 개선
        route = self._improve_with_2opt(route, distance_matrix, optimize_for)

        # 3. 결과 계산
        total_distance, total_duration, segments = self._calculate_route_metrics(
            route, distance_matrix
        )

        return TSPSolution(
            optimal_order=route,
            total_distance_meters=total_distance,
            total_duration_seconds=total_duration,
            route_segments=segments,
            solve_time_seconds=0.0,  # 나중에 설정됨
        )

    def _improve_with_2opt(
        self,
        route: List[int],
        distance_matrix: Dict[Tuple[int, int], DistanceMatrixResult],
        optimize_for: str,
        max_iterations: int = 100,
    ) -> List[int]:
        """2-opt 알고리즘으로 경로 개선"""

        best_route = route[:]
        best_cost = self._calculate_total_cost(
            best_route, distance_matrix, optimize_for
        )

        for iteration in range(max_iterations):
            improved = False

            for i in range(1, len(route) - 2):
                for j in range(i + 1, len(route)):
                    if j - i == 1:
                        continue  # 인접한 간선은 건너뜀

                    # 2-opt swap
                    new_route = route[:]
                    new_route[i:j] = route[i:j][::-1]

                    new_cost = self._calculate_total_cost(
                        new_route, distance_matrix, optimize_for
                    )

                    if new_cost < best_cost:
                        best_route = new_route
                        best_cost = new_cost
                        route = new_route
                        improved = True
                        break

                if improved:
                    break

            if not improved:
                break

        return best_route

    def _create_matrix_array(
        self,
        distance_matrix: Dict[Tuple[int, int], DistanceMatrixResult],
        num_locations: int,
        optimize_for: str,
    ) -> List[List[int]]:
        """거리 매트릭스를 2D 배열로 변환"""
        matrix = [[0] * num_locations for _ in range(num_locations)]

        for i in range(num_locations):
            for j in range(num_locations):
                if i == j:
                    matrix[i][j] = 0
                else:
                    result = distance_matrix.get((i, j))
                    if result:
                        if optimize_for == "time":
                            matrix[i][j] = result.duration_seconds
                        else:
                            matrix[i][j] = result.distance_meters
                    else:
                        matrix[i][j] = 999999  # 매우 큰 값

        return matrix

    def _get_cost(
        self,
        distance_matrix: Dict[Tuple[int, int], DistanceMatrixResult],
        from_idx: int,
        to_idx: int,
        optimize_for: str,
    ) -> float:
        """두 지점 간 비용 조회"""
        if from_idx == to_idx:
            return 0.0

        result = distance_matrix.get((from_idx, to_idx))
        if result:
            if optimize_for == "time":
                return float(result.duration_seconds)
            else:
                return float(result.distance_meters)

        return float("inf")

    def _calculate_total_cost(
        self,
        route: List[int],
        distance_matrix: Dict[Tuple[int, int], DistanceMatrixResult],
        optimize_for: str,
    ) -> float:
        """경로의 총 비용 계산"""
        total_cost = 0.0

        for i in range(len(route) - 1):
            cost = self._get_cost(distance_matrix, route[i], route[i + 1], optimize_for)
            total_cost += cost

        return total_cost

    def _calculate_route_metrics(
        self,
        route: List[int],
        distance_matrix: Dict[Tuple[int, int], DistanceMatrixResult],
    ) -> Tuple[int, int, List[Tuple[int, int]]]:
        """경로의 총 거리, 시간, 구간 정보 계산"""
        total_distance = 0
        total_duration = 0
        segments = []

        for i in range(len(route) - 1):
            from_idx = route[i]
            to_idx = route[i + 1]

            result = distance_matrix.get((from_idx, to_idx))
            if result:
                total_distance += result.distance_meters
                total_duration += result.duration_seconds

            segments.append((from_idx, to_idx))

        return total_distance, total_duration, segments

    def _parse_ortools_solution(
        self,
        solution,
        manager,
        routing,
        distance_matrix: Dict[Tuple[int, int], DistanceMatrixResult],
        optimize_for: str,
    ) -> TSPSolution:
        """OR-Tools 해결 결과 파싱"""
        route = []
        index = routing.Start(0)

        while not routing.IsEnd(index):
            route.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))

        # 마지막 노드 추가
        route.append(manager.IndexToNode(index))

        # 메트릭스 계산
        total_distance, total_duration, segments = self._calculate_route_metrics(
            route, distance_matrix
        )

        return TSPSolution(
            optimal_order=route,
            total_distance_meters=total_distance,
            total_duration_seconds=total_duration,
            route_segments=segments,
            solve_time_seconds=0.0,
        )

    def solve_multi_day_tsp(
        self,
        locations: List[LocationCoordinate],
        distance_matrix: Dict[Tuple[int, int], DistanceMatrixResult],
        days_assignment: Dict[int, int],  # {location_index: day_number}
        start_location_index: int,
        hotel_location_index: Optional[int] = None,
        optimize_for: str = "distance",
    ) -> Dict[int, TSPSolution]:
        """
        다일차 TSP 해결

        Args:
            locations: 모든 위치 목록
            distance_matrix: 거리 매트릭스
            days_assignment: 각 위치의 일차 배정
            start_location_index: 시작 위치 인덱스
            hotel_location_index: 호텔 위치 인덱스
            optimize_for: 최적화 기준

        Returns:
            {day_number: TSPSolution} 딕셔너리
        """
        solutions = {}

        # 일차별로 위치들을 그룹화
        days_locations = {}
        for loc_idx, day in days_assignment.items():
            if day not in days_locations:
                days_locations[day] = []
            days_locations[day].append(loc_idx)

        for day, day_locations in days_locations.items():
            if not day_locations:
                continue

            # 해당 일차의 시작점과 종료점 결정
            if day == 1:
                day_start = start_location_index
            else:
                day_start = hotel_location_index or start_location_index

            day_end = hotel_location_index or start_location_index

            # 해당 일차의 모든 위치 (시작점 + 방문지 + 종료점)
            all_day_locations = [day_start] + day_locations
            if day_end not in all_day_locations:
                all_day_locations.append(day_end)

            # 해당 일차의 거리 매트릭스 추출
            day_distance_matrix = self._extract_day_distance_matrix(
                distance_matrix, all_day_locations
            )

            # 인덱스 매핑 (원본 인덱스 → 일차별 인덱스)
            index_mapping = {loc: i for i, loc in enumerate(all_day_locations)}
            reverse_mapping = {i: loc for i, loc in enumerate(all_day_locations)}

            # 일차별 TSP 해결
            day_solution = self.solve_tsp(
                day_distance_matrix,
                len(all_day_locations),
                start_index=0,  # 매핑된 시작점은 항상 0
                end_index=index_mapping.get(day_end),
                optimize_for=optimize_for,
            )

            # 원본 인덱스로 결과 변환
            original_order = [
                reverse_mapping[idx] for idx in day_solution.optimal_order
            ]
            original_segments = [
                (reverse_mapping[seg[0]], reverse_mapping[seg[1]])
                for seg in day_solution.route_segments
            ]

            day_solution.optimal_order = original_order
            day_solution.route_segments = original_segments

            solutions[day] = day_solution

        return solutions

    def _extract_day_distance_matrix(
        self,
        full_distance_matrix: Dict[Tuple[int, int], DistanceMatrixResult],
        day_locations: List[int],
    ) -> Dict[Tuple[int, int], DistanceMatrixResult]:
        """일차별 거리 매트릭스 추출"""
        day_matrix = {}

        for i, from_loc in enumerate(day_locations):
            for j, to_loc in enumerate(day_locations):
                if (from_loc, to_loc) in full_distance_matrix:
                    day_matrix[(i, j)] = full_distance_matrix[(from_loc, to_loc)]

        return day_matrix
