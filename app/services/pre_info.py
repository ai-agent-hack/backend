from typing import List, Optional
from datetime import datetime

from app.models.pre_info import PreInfo
from app.schemas.pre_info import PreInfoRequest, PreInfoUpdate
from app.repositories.pre_info import PreInfoRepository
from app.core.exceptions import ValidationError, NotFoundError


class PreInfoService:
    """
    PreInfo business logic service.
    Follows Single Responsibility Principle - only handles PreInfo business operations.
    """

    def __init__(self, pre_info_repository: PreInfoRepository):
        self.pre_info_repository = pre_info_repository

    def create_pre_info(self, pre_info_in: PreInfoRequest, user_id: int) -> PreInfo:
        """여행 사전정보 생성"""
        # 비즈니스 로직: 날짜 유효성 검증
        if pre_info_in.start_date >= pre_info_in.end_date:
            raise ValidationError("여행 시작일은 종료일보다 이전이어야 합니다")

        # 비즈니스 로직: 과거 날짜 검증
        if pre_info_in.start_date.date() < datetime.now().date():
            raise ValidationError("여행 시작일은 오늘 이후여야 합니다")

        # 비즈니스 로직: 예산 검증
        if pre_info_in.budget < 10000:
            raise ValidationError("최소 예산은 10,000원 이상이어야 합니다")

        return self.pre_info_repository.create_with_user(pre_info_in, user_id)

    def get_user_pre_infos(
        self, user_id: int, skip: int = 0, limit: int = 100
    ) -> List[PreInfo]:
        """사용자의 여행 사전정보 목록 조회"""
        return self.pre_info_repository.get_by_user_id(user_id, skip, limit)

    def get_pre_info_by_id(self, pre_info_id: int, user_id: int) -> PreInfo:
        """특정 여행 사전정보 조회 (본인 것만)"""
        pre_info = self.pre_info_repository.get_user_pre_info(pre_info_id, user_id)
        if not pre_info:
            raise NotFoundError("여행 사전정보를 찾을 수 없습니다")
        return pre_info

    def update_pre_info(
        self, pre_info_id: int, pre_info_update: PreInfoUpdate, user_id: int
    ) -> PreInfo:
        """여행 사전정보 수정 (본인 것만)"""
        pre_info = self.get_pre_info_by_id(pre_info_id, user_id)

        # 비즈니스 로직: 날짜 유효성 검증
        if pre_info_update.start_date and pre_info_update.end_date:
            if pre_info_update.start_date >= pre_info_update.end_date:
                raise ValidationError("여행 시작일은 종료일보다 이전이어야 합니다")
        elif pre_info_update.start_date:
            if pre_info_update.start_date >= pre_info.end_date:
                raise ValidationError("여행 시작일은 종료일보다 이전이어야 합니다")
        elif pre_info_update.end_date:
            if pre_info.start_date >= pre_info_update.end_date:
                raise ValidationError("여행 시작일은 종료일보다 이전이어야 합니다")

        # 비즈니스 로직: 예산 검증
        if pre_info_update.budget is not None and pre_info_update.budget < 10000:
            raise ValidationError("최소 예산은 10,000원 이상이어야 합니다")

        return self.pre_info_repository.update(pre_info, pre_info_update)

    def delete_pre_info(self, pre_info_id: int, user_id: int) -> PreInfo:
        """여행 사전정보 삭제 (본인 것만)"""
        pre_info = self.get_pre_info_by_id(pre_info_id, user_id)
        return self.pre_info_repository.delete(pre_info_id)
