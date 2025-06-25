from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.pre_info import PreInfo
from app.schemas.pre_info import PreInfoRequest, PreInfoUpdate
from app.repositories.base import BaseRepository


class PreInfoRepository(BaseRepository[PreInfo, PreInfoRequest, PreInfoUpdate]):
    """
    PreInfo data access layer.
    Follows Single Responsibility Principle - only handles PreInfo database operations.
    """

    def __init__(self, db: Session):
        super().__init__(PreInfo, db)

    def get_by_user_id(
        self, user_id: int, skip: int = 0, limit: int = 100
    ) -> List[PreInfo]:
        """特定ユーザーの旅行事前情報リストを照会"""
        return (
            self.db.query(PreInfo)
            .filter(PreInfo.user_id == user_id)
            .order_by(PreInfo.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create_with_user(self, obj_in: PreInfoRequest, user_id: int) -> PreInfo:
        """ユーザーIDと共に旅行事前情報を作成"""
        obj_data = obj_in.model_dump()
        obj_data["user_id"] = user_id
        db_obj = self.model(**obj_data)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def get_user_pre_info(self, pre_info_id: int, user_id: int) -> Optional[PreInfo]:
        """特定ユーザーの特定旅行事前情報を照会"""
        return (
            self.db.query(PreInfo)
            .filter(and_(PreInfo.id == pre_info_id, PreInfo.user_id == user_id))
            .first()
        )

    def get_by_plan_id(self, plan_id: str) -> Optional[PreInfo]:
        """plan_id를 통해 PreInfo를 조회"""
        from app.models.rec_plan import RecPlan

        return (
            self.db.query(PreInfo)
            .join(RecPlan)
            .filter(RecPlan.plan_id == plan_id)
            .first()
        )
