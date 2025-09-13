from typing import List, Dict, Optional
from dataclasses import dataclass, field
import logging

from app.models.rec_spot import RecSpot
from app.services.google_maps_service import (
    GoogleMapsService,
    LocationCoordinate,
    DistanceMatrixResult,
)
from app.services.tsp_solver_service import TSPSolverService, TSPSolution

logger = logging.getLogger(__name__)


@dataclass
class RouteCalculationInput:
    """경로 계산에 필요한 모든 입력을 담는 데이터 클래스"""

    plan_id: str
    version: int
    selected_spots: List[RecSpot]
    total_days: int
    locations: List[LocationCoordinate]
    location_mapping: Dict[str, int]
    travel_mode: str
    optimize_for: str
    maintain_time_order: bool
    google_maps_service: GoogleMapsService
    tsp_solver_service: TSPSolverService
    time_slot_groups: Optional[Dict[str, List[int]]] = None  # 시간대별 그룹 정보


@dataclass
class RouteCalculationOutput:
    """경로 계산 결과를 담는 데이터 클래스"""

    tsp_solutions: Dict[int, TSPSolution] = field(default_factory=dict)
    total_distance_meters: int = 0
    total_duration_seconds: int = 0


class RouteCalculator:
    """
    경로 계산의 전 과정을 책임지는 클래스.
    관심사 분리: 복잡한 계산 로직을 RouteService로부터 분리.
    """

    def __init__(self, calc_input: RouteCalculationInput):
        self.input = calc_input
        self.output = RouteCalculationOutput()
        self.logger = logging.getLogger(self.__class__.__name__)

    async def run(self) -> RouteCalculationOutput:
        """계산 프로세스를 순차적으로 실행"""
        self.logger.info(
            f"경로 계산 시작: plan_id={self.input.plan_id}, version={self.input.version}"
        )

        # 1. 일차별 스팟 분배
        daily_spot_indices = self._assign_spots_to_days()

        # 2. 비용 행렬 생성
        cost_matrix_result = await self._build_cost_matrix()

        # 3. 일차별 TSP 문제 해결
        if daily_spot_indices and cost_matrix_result:
            self.output.tsp_solutions = (
                self.input.tsp_solver_service.solve_multi_day_tsp(
                    locations=self.input.locations,
                    distance_matrix_result=cost_matrix_result,
                    days_assignment=daily_spot_indices,
                    optimize_for=self.input.optimize_for,
                    maintain_time_order=self.input.maintain_time_order,
                    time_slot_groups=getattr(self.input, "time_slot_groups", None),
                )
            )

        # 4. 전체 통계 계산
        self._calculate_total_summary()

        self.logger.info(
            f"경로 계산 완료: {len(self.output.tsp_solutions)}일치 경로 생성"
        )
        return self.output

    def _assign_spots_to_days(self) -> Dict[int, List[int]]:
        """스팟을 일차별로 분배하고, maintain_time_order가 True면 시간대별로 그룹화"""
        total_spots = len(self.input.selected_spots)
        if total_spots == 0:
            return {}

        if self.input.maintain_time_order:
            # 시간대별로 그룹화한 후 TSP 최적화를 위한 특별한 구조 생성
            time_slot_map = {"MORNING": 0, "AFTERNOON": 1, "NIGHT": 2}

            # 시간대별로 스팟 그룹화
            time_slot_groups = {"MORNING": [], "AFTERNOON": [], "NIGHT": []}

            for i, spot in enumerate(self.input.selected_spots):
                time_slot = spot.time_slot or "AFTERNOON"  # 기본값
                if time_slot in time_slot_groups:
                    time_slot_groups[time_slot].append(i)

            # 시간대 순서대로 재배열 (오전 -> 오후 -> 저녁)
            ordered_indices = []
            for time_slot in ["MORNING", "AFTERNOON", "NIGHT"]:
                ordered_indices.extend(time_slot_groups[time_slot])

            self.logger.info(
                f"시간대 순서 유지 모드: {len(ordered_indices)}개 스팟을 시간대별로 그룹화"
            )
            self.logger.info(
                f"시간대별 분포: 오전={len(time_slot_groups['MORNING'])}, 오후={len(time_slot_groups['AFTERNOON'])}, 저녁={len(time_slot_groups['NIGHT'])}"
            )

            # time_slot_groups 정보를 RouteCalculationInput에 저장 (TSP에서 활용)
            self.input.time_slot_groups = time_slot_groups

            return {1: ordered_indices}
        else:
            # 기존 로직: 모든 스팟을 day 1에 할당 (일정 나누기 비활성화)
            spot_location_indices = list(range(total_spots))
            return {1: spot_location_indices}

    async def _build_cost_matrix(self) -> Optional[List[List[DistanceMatrixResult]]]:
        """Google Maps API를 호출하여 비용 행렬 생성"""
        try:
            matrix_result = await self.input.google_maps_service.get_distance_matrix(
                self.input.locations, self.input.locations, self.input.travel_mode
            )
            return matrix_result
        except Exception as e:
            self.logger.error(f"비용 행렬 생성 실패: {e}")
            return None

    def _calculate_total_summary(self):
        """계산된 TSP 결과로부터 전체 요약 정보 계산"""
        if not self.output.tsp_solutions:
            return

        self.output.total_distance_meters = sum(
            sol.total_distance_meters for sol in self.output.tsp_solutions.values()
        )
        self.output.total_duration_seconds = sum(
            sol.total_duration_seconds for sol in self.output.tsp_solutions.values()
        )
