import logging
from typing import List, Dict, Tuple, Optional
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
        TSP(Traveling Salesperson Problem) 해결
        주어진 거리 행렬을 기반으로 최적의 방문 순서를 찾습니다.
        end_index가 None이면 출발지에서 시작하여 가장 효율적인 순서로 방문하는 개방 경로(open path)를 찾습니다.
        """
        import time

        start_time = time.time()

        is_open_path = end_index is None
        if is_open_path:
            # For open path, we still calculate a round trip and then cut the last segment.
            end_index = start_index

        try:
            # OR-Tools가 설치되어 있으면 사용, 없으면 휴리스틱 사용
            from ortools.constraint_solver import pywrapcp

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

        # 개방 경로인 경우, 마지막 노드를 제거하고 경로를 재계산
        if is_open_path and solution.optimal_order and len(solution.optimal_order) > 1:
            if solution.optimal_order[0] == solution.optimal_order[-1]:
                solution.optimal_order = solution.optimal_order[:-1]

                # 경로 변경 후 메트릭 재계산
                (
                    solution.total_distance_meters,
                    solution.total_duration_seconds,
                    solution.route_segments,
                ) = self._calculate_route_metrics(
                    solution.optimal_order, distance_matrix
                )

        solution.solve_time_seconds = time.time() - start_time
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
            from ortools.constraint_solver import pywrapcp, routing_enums_pb2
        except ImportError:
            raise ImportError("OR-Tools 패키지가 필요합니다: pip install ortools")

        # TSP 모델 생성 (start_index와 end_index를 리스트로 전달)
        manager = pywrapcp.RoutingIndexManager(
            num_locations, 1, [start_index], [end_index]
        )
        routing = pywrapcp.RoutingModel(manager)

        # 비용 콜백 등록
        def distance_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            cost = self._get_cost(distance_matrix, from_node, to_node, optimize_for)
            return int(cost)

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        # 검색 파라미터 설정
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        search_parameters.time_limit.seconds = 5

        # TSP 해결
        solution = routing.SolveWithParameters(search_parameters)

        if not solution:
            raise Exception("OR-Tools로 해결할 수 없습니다.")

        # 경로 추출
        route = []
        index = routing.Start(0)
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route.append(node_index)
            index = solution.Value(routing.NextVar(index))
        route.append(manager.IndexToNode(index))

        # 거리, 시간, 세그먼트 재계산
        total_distance, total_duration, segments = self._calculate_route_metrics(
            route, distance_matrix
        )

        return TSPSolution(
            optimal_order=route,
            total_distance_meters=total_distance,
            total_duration_seconds=total_duration,
            route_segments=segments,
            solve_time_seconds=0.0,  # 상위 레벨에서 계산됨
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
        objective_value = solution.ObjectiveValue()
        total_distance = objective_value
        total_duration = objective_value

        return TSPSolution(
            optimal_order=route,
            total_distance_meters=total_distance,
            total_duration_seconds=total_duration,
            route_segments=self._calculate_route_metrics(route, distance_matrix)[2],
            solve_time_seconds=0.0,
        )

    def solve_multi_day_tsp(
        self,
        locations: List[LocationCoordinate],
        distance_matrix_result: List[List[DistanceMatrixResult]],
        days_assignment: Dict[int, List[int]],
        optimize_for: str = "distance",
        maintain_time_order: bool = False,
        time_slot_groups: Optional[Dict[str, List[int]]] = None,
    ) -> Dict[int, TSPSolution]:
        """
        다중 일차 TSP 문제 해결
        maintain_time_order가 True이면 시간대별 그룹 내에서 TSP 최적화 수행
        """
        solutions = {}

        for day, spot_indices in days_assignment.items():
            if len(spot_indices) <= 1:
                # 스팟이 1개 이하인 경우
                solution = TSPSolution(
                    optimal_order=spot_indices,
                    total_distance_meters=0,
                    total_duration_seconds=0,
                    route_segments=[],
                    solve_time_seconds=0.0,
                )
                solutions[day] = solution
                continue

            if maintain_time_order and time_slot_groups:
                # 시간대별 그룹 내 TSP 최적화 모드
                logger.info(f"Day {day}: 시간대별 그룹 내 TSP 최적화 모드")

                optimized_order = []
                total_distance = 0
                total_duration = 0
                all_segments = []

                # 시간대 순서대로 처리 (오전 -> 오후 -> 저녁)
                for time_slot in ["MORNING", "AFTERNOON", "NIGHT"]:
                    if time_slot not in time_slot_groups:
                        continue

                    group_indices = time_slot_groups[time_slot]
                    if len(group_indices) == 0:
                        continue
                    elif len(group_indices) == 1:
                        # 그룹에 스팟이 1개면 그대로 추가
                        optimized_order.extend(group_indices)
                        continue

                    logger.info(
                        f"  {time_slot} 그룹: {len(group_indices)}개 스팟 TSP 최적화"
                    )

                    # 그룹 내 상대 인덱스로 매핑 (0, 1, 2, ...)
                    group_size = len(group_indices)
                    relative_distance_matrix = {}

                    for i in range(group_size):
                        for j in range(group_size):
                            actual_i = group_indices[i]
                            actual_j = group_indices[j]

                            if actual_i < len(
                                distance_matrix_result
                            ) and actual_j < len(distance_matrix_result[actual_i]):
                                # 상대 인덱스 (i, j)로 저장
                                relative_distance_matrix[(i, j)] = (
                                    distance_matrix_result[actual_i][actual_j]
                                )

                    if not relative_distance_matrix:
                        # 거리 행렬이 없으면 순서 그대로 사용
                        optimized_order.extend(group_indices)
                        continue

                    try:
                        # 그룹 내 TSP 최적화 (상대 인덱스 사용)
                        group_solution = self.solve_tsp(
                            distance_matrix=relative_distance_matrix,
                            num_locations=group_size,
                            start_index=0,  # 그룹 내에서는 항상 0부터 시작
                            end_index=None,  # 개방 경로
                            optimize_for=optimize_for,
                        )

                        # 상대 인덱스를 실제 인덱스로 변환
                        actual_optimized_order = [
                            group_indices[i] for i in group_solution.optimal_order
                        ]
                        optimized_order.extend(actual_optimized_order)

                        total_distance += group_solution.total_distance_meters
                        total_duration += group_solution.total_duration_seconds

                        # 세그먼트도 실제 인덱스로 변환
                        for from_rel, to_rel in group_solution.route_segments:
                            actual_from = group_indices[from_rel]
                            actual_to = group_indices[to_rel]
                            all_segments.append((actual_from, actual_to))

                        logger.info(
                            f"    {time_slot} 그룹 TSP 완료: {len(actual_optimized_order)}개 스팟"
                        )

                    except Exception as e:
                        logger.warning(
                            f"    {time_slot} 그룹 TSP 실패, 기본 순서 사용: {e}"
                        )
                        optimized_order.extend(group_indices)

                # 그룹 간 연결 거리/시간 추가 계산
                if len(optimized_order) > 1:
                    for i in range(len(optimized_order) - 1):
                        from_idx = optimized_order[i]
                        to_idx = optimized_order[i + 1]

                        # 이미 그룹 내 세그먼트로 처리된 것은 스킵
                        if (from_idx, to_idx) not in all_segments:
                            if from_idx < len(distance_matrix_result) and to_idx < len(
                                distance_matrix_result[from_idx]
                            ):
                                dist_result = distance_matrix_result[from_idx][to_idx]
                                total_distance += dist_result.distance_meters
                                total_duration += dist_result.duration_seconds
                                all_segments.append((from_idx, to_idx))

                solution = TSPSolution(
                    optimal_order=optimized_order,
                    total_distance_meters=total_distance,
                    total_duration_seconds=total_duration,
                    route_segments=all_segments,
                    solve_time_seconds=0.0,
                )
                solutions[day] = solution
                continue

            # 기존 TSP 최적화 로직 (maintain_time_order=False 또는 time_slot_groups 없음)
            distance_matrix = {}
            for i in spot_indices:
                for j in spot_indices:
                    if i < len(distance_matrix_result) and j < len(
                        distance_matrix_result[i]
                    ):
                        distance_matrix[(i, j)] = distance_matrix_result[i][j]

            if not distance_matrix:
                # 거리 행렬이 없는 경우 기본값 사용
                solution = TSPSolution(
                    optimal_order=spot_indices,
                    total_distance_meters=0,
                    total_duration_seconds=0,
                    route_segments=[],
                    solve_time_seconds=0.0,
                )
                solutions[day] = solution
                continue

            try:
                solution = self.solve_tsp(
                    distance_matrix=distance_matrix,
                    num_locations=len(spot_indices),
                    start_index=spot_indices[0],
                    end_index=None,  # 개방 경로
                    optimize_for=optimize_for,
                )
                solutions[day] = solution

            except Exception as e:
                logger.error(f"Day {day} TSP 해결 실패: {e}")
                # 실패 시 순서 그대로 사용
                solution = TSPSolution(
                    optimal_order=spot_indices,
                    total_distance_meters=0,
                    total_duration_seconds=0,
                    route_segments=[],
                    solve_time_seconds=0.0,
                )
                solutions[day] = solution

        return solutions

    def _solve_tsp(
        self,
        distance_matrix: List[List[int]],
        start_node: int,
        num_vehicles: int,
    ) -> Tuple[List[int], int, int]:
        """OR-Tools를 사용한 TSP 해결"""
        try:
            from ortools.constraint_solver import routing_enums_pb2
            from ortools.constraint_solver import pywrapcp
        except ImportError:
            raise ImportError("OR-Tools 패키지가 필요합니다: pip install ortools")

        # TSP 모델 생성
        manager = pywrapcp.RoutingIndexManager(
            len(distance_matrix), num_vehicles, start_node
        )
        routing = pywrapcp.RoutingModel(manager)

        def distance_callback(from_index, to_index):
            """거리 콜백 함수"""
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return distance_matrix[from_node][to_node]

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

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

        # 경로 추출
        route = []
        index = routing.Start(0)
        while not routing.IsEnd(index):
            route.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))
        route.append(manager.IndexToNode(index))  # 마지막 노드 추가

        # 메트릭스 계산 및 세그먼트 생성
        total_distance = 0
        total_duration = 0
        segments = []
        for i in range(len(route) - 1):
            from_node = route[i]
            to_node = route[i + 1]
            dist = distance_matrix[from_node][to_node]

            # 비용 행렬이 거리/시간 중 하나이므로, 다른 하나는 추정치 또는 동일 값 사용
            total_distance += dist
            total_duration += dist  # 여기서 더 나은 추정이 필요할 수 있음
            segments.append((from_node, to_node))

        return TSPSolution(
            optimal_order=route,
            total_distance_meters=total_distance,
            total_duration_seconds=total_duration,
            route_segments=segments,
            solve_time_seconds=0.0,  # 계산 시간은 상위 레벨에서 측정
        )
