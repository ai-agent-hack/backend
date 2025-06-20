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
        """특정 사용자의 여행 사전정보 목록 조회"""
        return (
            self.db.query(PreInfo)
            .filter(PreInfo.user_id == user_id)
            .order_by(PreInfo.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create_with_user(self, obj_in: PreInfoRequest, user_id: int) -> PreInfo:
        """사용자 ID와 함께 여행 사전정보 생성"""
        obj_data = obj_in.model_dump()
        obj_data["user_id"] = user_id
        db_obj = self.model(**obj_data)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def get_user_pre_info(self, pre_info_id: int, user_id: int) -> Optional[PreInfo]:
        """특정 사용자의 특정 여행 사전정보 조회"""
        return (
            self.db.query(PreInfo)
            .filter(and_(PreInfo.id == pre_info_id, PreInfo.user_id == user_id))
            .first()
        )
