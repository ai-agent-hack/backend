from typing import Optional, List, Dict, Any
from datetime import datetime

from app.models.rec_plan import RecPlan
from app.models.pre_info import PreInfo
from app.repositories.rec_plan import RecPlanRepository
from app.repositories.pre_info import PreInfoRepository
from app.repositories.rec_spot import RecSpotRepository
from app.schemas.spot import RecommendSpots
from app.services.rec_spot import RecSpotService


class RecPlanService:
    """
    Service for RecPlan business logic.
    Follows Single Responsibility Principle - handles plan version management.
    """

    def __init__(
        self,
        rec_plan_repo: RecPlanRepository,
        pre_info_repo: PreInfoRepository,
        rec_spot_repo: RecSpotRepository = None,
    ):
        self.rec_plan_repo = rec_plan_repo
        self.pre_info_repo = pre_info_repo
        self.rec_spot_repo = rec_spot_repo

    def get_plan_by_id(self, plan_id: str) -> Optional[RecPlan]:
        """Get the latest version of a plan"""
        return self.rec_plan_repo.get_latest_version(plan_id)

    def get_plan_by_id_and_version(
        self, plan_id: str, version: int
    ) -> Optional[RecPlan]:
        """Get a specific version of a plan"""
        return self.rec_plan_repo.get_by_plan_id_and_version(plan_id, version)

    def create_initial_plan(self, plan_id: str, pre_info_id: int) -> RecPlan:
        """
        Create the initial version (v1) of a plan.
        Used by the /trip/seed endpoint.
        """
        # Validate pre_info exists
        pre_info = self.pre_info_repo.get(pre_info_id)
        if not pre_info:
            raise ValueError(f"PreInfo with id {pre_info_id} not found")

        # Check if plan already exists
        existing_plan = self.rec_plan_repo.get_latest_version(plan_id)
        if existing_plan:
            raise ValueError(
                f"Plan {plan_id} already exists (version {existing_plan.version})"
            )

        # Create initial version
        return self.rec_plan_repo.create_new_version(
            plan_id=plan_id, pre_info_id=pre_info_id
        )

    def create_new_version(self, plan_id: str) -> RecPlan:
        """
        Create a new version of an existing plan.
        Used by the /trip/{plan_id}/save endpoint.
        """
        # Get latest version
        latest_plan = self.rec_plan_repo.get_latest_version(plan_id)
        if not latest_plan:
            raise ValueError(f"Plan {plan_id} not found")

        # Create new version
        return self.rec_plan_repo.create_new_version(
            plan_id=plan_id,
            pre_info_id=latest_plan.pre_info_id,
            base_version=latest_plan.version,
        )

    def get_plan_info_with_pre_info(self, plan_id: str) -> Dict[str, Any]:
        """
        Get plan information along with associated pre_info.
        Used by refine endpoint to get context.
        """
        latest_plan = self.rec_plan_repo.get_latest_version(plan_id)
        if not latest_plan:
            raise ValueError(f"Plan {plan_id} not found")

        pre_info = self.pre_info_repo.get(latest_plan.pre_info_id)
        if not pre_info:
            raise ValueError(f"Associated PreInfo {latest_plan.pre_info_id} not found")

        return {
            "plan": latest_plan,
            "pre_info": pre_info,
            "plan_context": {
                "plan_id": latest_plan.plan_id,
                "current_version": latest_plan.version,
                "created_at": latest_plan.created_at,
                "departure_location": pre_info.departure_location,
                "start_date": pre_info.start_date,
                "end_date": pre_info.end_date,
                "atmosphere": pre_info.atmosphere,
                "budget": pre_info.budget,
                "region": pre_info.region,
                "participants_count": pre_info.participants_count,
            },
        }

    def get_plan_version_history(self, plan_id: str) -> List[RecPlan]:
        """Get all versions of a plan (oldest to newest)"""
        return self.rec_plan_repo.get_version_history(plan_id)

    def delete_plan(self, plan_id: str) -> int:
        """Delete all versions of a plan. Returns count of deleted records."""
        return self.rec_plan_repo.delete_plan_all_versions(plan_id)

    def validate_plan_exists(self, plan_id: str) -> bool:
        """Check if a plan exists"""
        return self.rec_plan_repo.get_latest_version(plan_id) is not None

    def get_plans_by_user(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all plans for a user with summary information"""
        # Get pre_infos for the user
        user_pre_infos = self.pre_info_repo.get_multi(filters={"user_id": user_id})

        user_plans = []
        for pre_info in user_pre_infos:
            plans = self.rec_plan_repo.get_plans_by_pre_info_id(pre_info.id)
            for plan in plans:
                user_plans.append(
                    {
                        "plan_id": plan.plan_id,
                        "version": plan.version,
                        "created_at": plan.created_at,
                        "atmosphere": pre_info.atmosphere,
                        "region": pre_info.region,
                        "start_date": pre_info.start_date,
                        "end_date": pre_info.end_date,
                    }
                )

        return sorted(user_plans, key=lambda x: x["created_at"], reverse=True)

    def get_plan_with_spots(
        self, plan_id: str, version: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get plan information with associated spots data.
        Used by GET /trip/{plan_id} endpoint.
        """
        if not self.rec_spot_repo:
            raise ValueError("RecSpotRepository not available")

        # Get specific version or latest
        if version:
            plan = self.rec_plan_repo.get_by_plan_id_and_version(plan_id, version)
        else:
            plan = self.rec_plan_repo.get_latest_version(plan_id)

        if not plan:
            return None

        # Get associated spots
        rec_spots = self.rec_spot_repo.get_spots_by_plan_version(plan_id, plan.version)

        # Convert to RecommendSpots format using RecSpotService
        rec_spot_service = RecSpotService(self.rec_spot_repo)
        recommend_spots = rec_spot_service.convert_rec_spots_to_recommend_spots(
            rec_spots, f"plan_{plan_id}_v{plan.version}"
        )

        # Get pre_info for additional context
        pre_info = self.pre_info_repo.get(plan.pre_info_id)

        return {
            "plan_info": {
                "plan_id": plan.plan_id,
                "version": plan.version,
                "pre_info_id": plan.pre_info_id,
                "created_at": plan.created_at,
                "total_spots": len(rec_spots),
            },
            "recommend_spots": recommend_spots,
            "pre_info": pre_info,
        }

    def get_plan_versions(self, plan_id: str) -> List[int]:
        """
        Get all version numbers for a plan.
        Used by GET /trip/{plan_id} endpoint.
        """
        versions = self.rec_plan_repo.get_version_history(plan_id)
        return [v.version for v in versions]
