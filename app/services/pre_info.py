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
        """旅行事前情報の作成"""
        # ビジネスロジック: 日付有効性検証
        if pre_info_in.start_date >= pre_info_in.end_date:
            raise ValidationError("旅行開始日は終了日より前である必要があります")

        # ビジネスロジック: 過去日付検証
        if pre_info_in.start_date.date() < datetime.now().date():
            raise ValidationError("旅行開始日は今日以降である必要があります")

        # ビジネスロジック: 予算検証
        if pre_info_in.budget < 10000:
            raise ValidationError("最低予算は10,000円以上である必要があります")

        return self.pre_info_repository.create_with_user(pre_info_in, user_id)

    def get_user_pre_infos(
        self, user_id: int, skip: int = 0, limit: int = 100
    ) -> List[PreInfo]:
        """ユーザーの旅行事前情報一覧取得"""
        return self.pre_info_repository.get_by_user_id(user_id, skip, limit)

    def get_pre_info_by_id(self, pre_info_id: int, user_id: int) -> PreInfo:
        """特定の旅行事前情報取得（本人のみ）"""
        pre_info = self.pre_info_repository.get_user_pre_info(pre_info_id, user_id)
        if not pre_info:
            raise NotFoundError("旅行事前情報が見つかりません")
        return pre_info

    def update_pre_info(
        self, pre_info_id: int, pre_info_update: PreInfoUpdate, user_id: int
    ) -> PreInfo:
        """旅行事前情報の修正（本人のみ）"""
        pre_info = self.get_pre_info_by_id(pre_info_id, user_id)

        # ビジネスロジック: 日付有効性検証
        if pre_info_update.start_date and pre_info_update.end_date:
            if pre_info_update.start_date >= pre_info_update.end_date:
                raise ValidationError("旅行開始日は終了日より前である必要があります")
        elif pre_info_update.start_date:
            if pre_info_update.start_date >= pre_info.end_date:
                raise ValidationError("旅行開始日は終了日より前である必要があります")
        elif pre_info_update.end_date:
            if pre_info.start_date >= pre_info_update.end_date:
                raise ValidationError("旅行開始日は終了日より前である必要があります")

        # ビジネスロジック: 予算検証
        if pre_info_update.budget is not None and pre_info_update.budget < 10000:
            raise ValidationError("最低予算は10,000円以上である必要があります")

        return self.pre_info_repository.update(pre_info, pre_info_update)

    def delete_pre_info(self, pre_info_id: int, user_id: int) -> PreInfo:
        """旅行事前情報の削除（本人のみ）"""
        pre_info = self.get_pre_info_by_id(pre_info_id, user_id)
        return self.pre_info_repository.delete(pre_info_id)
