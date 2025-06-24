from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from decimal import Decimal

from app.models.rec_spot import RecSpot, SpotStatus


class RecSpotRepository:
    """
    Repository for RecSpot database operations.
    Handles spot status tracking for different plan versions.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_spots_by_plan_version(self, plan_id: str, version: int) -> List[RecSpot]:
        """Get all spots for a specific plan version"""
        return (
            self.db.query(RecSpot)
            .filter(and_(RecSpot.plan_id == plan_id, RecSpot.version == version))
            .order_by(RecSpot.rank)
            .all()
        )

    def get_active_spots_by_plan_version(
        self, plan_id: str, version: int
    ) -> List[RecSpot]:
        """Get only active spots (ADD/KEEP) for a specific plan version"""
        return (
            self.db.query(RecSpot)
            .filter(
                and_(
                    RecSpot.plan_id == plan_id,
                    RecSpot.version == version,
                    RecSpot.status.in_([SpotStatus.ADD, SpotStatus.KEEP]),
                )
            )
            .order_by(RecSpot.rank)
            .all()
        )

    def get_spot_by_plan_version_and_spot_id(
        self, plan_id: str, version: int, spot_id: str
    ) -> Optional[RecSpot]:
        """Get a specific spot in a plan version"""
        return (
            self.db.query(RecSpot)
            .filter(
                and_(
                    RecSpot.plan_id == plan_id,
                    RecSpot.version == version,
                    RecSpot.spot_id == spot_id,
                )
            )
            .first()
        )

    def create_spots_batch(self, spots_data: List[Dict[str, Any]]) -> List[RecSpot]:
        """Create multiple spots in batch"""
        spots = []
        for spot_data in spots_data:
            spot = RecSpot(**spot_data)
            spots.append(spot)
            self.db.add(spot)

        self.db.commit()
        for spot in spots:
            self.db.refresh(spot)
        return spots

    def get_spots_by_status(
        self, plan_id: str, version: int, status: SpotStatus
    ) -> List[RecSpot]:
        """Get spots by status for a specific plan version"""
        return (
            self.db.query(RecSpot)
            .filter(
                and_(
                    RecSpot.plan_id == plan_id,
                    RecSpot.version == version,
                    RecSpot.status == status,
                )
            )
            .order_by(RecSpot.rank)
            .all()
        )

    def get_spot_history(self, plan_id: str, spot_id: str) -> List[RecSpot]:
        """Get history of a specific spot across all versions"""
        return (
            self.db.query(RecSpot)
            .filter(and_(RecSpot.plan_id == plan_id, RecSpot.spot_id == spot_id))
            .order_by(RecSpot.version)
            .all()
        )

    def delete_spots_by_plan_version(self, plan_id: str, version: int) -> int:
        """Delete all spots for a specific plan version"""
        count = (
            self.db.query(RecSpot)
            .filter(and_(RecSpot.plan_id == plan_id, RecSpot.version == version))
            .delete()
        )
        self.db.commit()
        return count

    def get_version_comparison(
        self, plan_id: str, old_version: int, new_version: int
    ) -> Dict[str, List[RecSpot]]:
        """Compare spots between two versions"""
        old_spots = self.get_spots_by_plan_version(plan_id, old_version)
        new_spots = self.get_spots_by_plan_version(plan_id, new_version)

        return {
            "old_version_spots": old_spots,
            "new_version_spots": new_spots,
            "added_spots": self.get_spots_by_status(
                plan_id, new_version, SpotStatus.ADD
            ),
            "kept_spots": self.get_spots_by_status(
                plan_id, new_version, SpotStatus.KEEP
            ),
            "deleted_spots": self.get_spots_by_status(
                plan_id, new_version, SpotStatus.DEL
            ),
        }

    def get_top_rated_spots(
        self, plan_id: str, version: int, limit: int = 10
    ) -> List[RecSpot]:
        """Get top-rated active spots by similarity score"""
        return (
            self.db.query(RecSpot)
            .filter(
                and_(
                    RecSpot.plan_id == plan_id,
                    RecSpot.version == version,
                    RecSpot.status.in_([SpotStatus.ADD, SpotStatus.KEEP]),
                    RecSpot.similarity_score.isnot(None),
                )
            )
            .order_by(desc(RecSpot.similarity_score))
            .limit(limit)
            .all()
        )

    def update_similarity_scores_batch(
        self, plan_id: str, version: int, spot_scores: Dict[str, float]
    ) -> int:
        """Update similarity scores for multiple spots in batch"""
        updated_count = 0

        for spot_id, score in spot_scores.items():
            result = (
                self.db.query(RecSpot)
                .filter(
                    and_(
                        RecSpot.plan_id == plan_id,
                        RecSpot.version == version,
                        RecSpot.spot_id == spot_id,
                    )
                )
                .update({"similarity_score": Decimal(str(score))})
            )
            updated_count += result

        self.db.commit()
        return updated_count
