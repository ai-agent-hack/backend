from typing import Optional, List, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.rec_plan import RecPlan


class RecPlanRepository:
    """
    Repository for RecPlan database operations.
    Follows Repository pattern for data access abstraction.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_by_plan_id(self, plan_id: str) -> List[RecPlan]:
        """Get all versions of a plan by plan_id"""
        return (
            self.db.query(RecPlan)
            .filter(RecPlan.plan_id == plan_id)
            .order_by(desc(RecPlan.version))
            .all()
        )

    def get_latest_version(self, plan_id: str) -> Optional[RecPlan]:
        """Get the latest version of a plan"""
        return (
            self.db.query(RecPlan)
            .filter(RecPlan.plan_id == plan_id)
            .order_by(desc(RecPlan.version))
            .first()
        )

    def get_by_plan_id_and_version(
        self, plan_id: str, version: int
    ) -> Optional[RecPlan]:
        """Get a specific version of a plan"""
        return (
            self.db.query(RecPlan)
            .filter(RecPlan.plan_id == plan_id, RecPlan.version == version)
            .first()
        )

    def create_new_version(
        self, plan_id: str, pre_info_id: int, base_version: Optional[int] = None
    ) -> RecPlan:
        """Create a new version of a plan"""
        if base_version is None:
            # Get the latest version number
            latest = self.get_latest_version(plan_id)
            next_version = (latest.version + 1) if latest else 1
        else:
            next_version = base_version + 1

        new_plan = RecPlan(
            plan_id=plan_id, version=next_version, pre_info_id=pre_info_id
        )

        self.db.add(new_plan)
        self.db.commit()
        self.db.refresh(new_plan)
        return new_plan

    def get_version_history(self, plan_id: str) -> List[RecPlan]:
        """Get version history for a plan (oldest to newest)"""
        return (
            self.db.query(RecPlan)
            .filter(RecPlan.plan_id == plan_id)
            .order_by(RecPlan.version)
            .all()
        )

    def delete_plan_all_versions(self, plan_id: str) -> int:
        """Delete all versions of a plan. Returns count of deleted records."""
        count = self.db.query(RecPlan).filter(RecPlan.plan_id == plan_id).delete()
        self.db.commit()
        return count

    def get_plans_by_pre_info_id(self, pre_info_id: int) -> List[RecPlan]:
        """Get all plans associated with a pre_info_id"""
        return (
            self.db.query(RecPlan)
            .filter(RecPlan.pre_info_id == pre_info_id)
            .order_by(desc(RecPlan.created_at))
            .all()
        )
