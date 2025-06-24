from typing import List, Dict, Any, Set, Optional
from decimal import Decimal

from app.models.rec_spot import RecSpot, SpotStatus
from app.repositories.rec_spot import RecSpotRepository
from app.schemas.spot import RecommendSpots, TimeSlotSpots, Spot, SpotDetail, TimeSlot


class RecSpotService:
    """
    Service for RecSpot business logic.
    Handles spot status tracking, version comparison, and conversion between formats.
    """

    def __init__(self, rec_spot_repo: RecSpotRepository):
        self.rec_spot_repo = rec_spot_repo

    def save_spots_for_plan_version(
        self,
        plan_id: str,
        version: int,
        recommend_spots: RecommendSpots,
        previous_version: Optional[int] = None,
    ) -> List[RecSpot]:
        """
        Save spots for a specific plan version with status tracking.
        Compares with previous version to determine ADD/KEEP/DEL status.
        """
        # Extract all spot IDs from current recommendation
        current_spot_ids = self._extract_spot_ids_from_recommend_spots(recommend_spots)

        # Get previous version spots if available
        previous_spot_ids = set()
        if previous_version:
            previous_spots = self.rec_spot_repo.get_active_spots_by_plan_version(
                plan_id, previous_version
            )
            previous_spot_ids = {spot.spot_id for spot in previous_spots}

        # Determine spot statuses
        spot_status_map = self._determine_spot_statuses(
            current_spot_ids, previous_spot_ids
        )

        # Create RecSpot records
        spots_data = []
        rank = 1

        for time_slot in recommend_spots.recommend_spots:
            for spot in time_slot.spots:
                status = spot_status_map.get(spot.spot_id, SpotStatus.ADD)

                spots_data.append(
                    {
                        "plan_id": plan_id,
                        "version": version,
                        "spot_id": spot.spot_id,
                        "rank": rank,
                        "status": status,
                        "similarity_score": None,  # Will be set by vector search service
                    }
                )
                rank += 1

        # Add deleted spots from previous version
        if previous_version:
            deleted_spot_ids = previous_spot_ids - current_spot_ids
            for spot_id in deleted_spot_ids:
                spots_data.append(
                    {
                        "plan_id": plan_id,
                        "version": version,
                        "spot_id": spot_id,
                        "rank": rank,
                        "status": SpotStatus.DEL,
                        "similarity_score": None,
                    }
                )
                rank += 1

        # Save to database
        return self.rec_spot_repo.create_spots_batch(spots_data)

    def get_spots_by_plan_version(self, plan_id: str, version: int) -> List[RecSpot]:
        """Get all spots for a specific plan version"""
        return self.rec_spot_repo.get_spots_by_plan_version(plan_id, version)

    def get_active_spots_by_plan_version(
        self, plan_id: str, version: int
    ) -> List[RecSpot]:
        """Get only active spots (ADD/KEEP) for a specific plan version"""
        return self.rec_spot_repo.get_active_spots_by_plan_version(plan_id, version)

    def convert_rec_spots_to_recommend_spots(
        self, rec_spots: List[RecSpot], recommend_spot_id: Optional[str] = None
    ) -> RecommendSpots:
        """
        Convert RecSpot database records back to RecommendSpots schema.
        Used for API responses and saving data.
        """
        # Filter only active spots
        active_spots = [spot for spot in rec_spots if spot.is_active]

        # Group spots by time slots (simplified - all in one time slot for now)
        spots_info = []
        for rec_spot in active_spots:
            # Create dummy spot data since we only have spot_id in RecSpot
            # In real implementation, this would fetch full spot details from Places API
            spots_info.append(
                Spot(
                    spot_id=rec_spot.spot_id,
                    longitude=0.0,  # Placeholder
                    latitude=0.0,  # Placeholder
                    recommendation_reason="Saved spot",
                    details=SpotDetail(
                        name=f"Spot {rec_spot.spot_id}",
                        congestion=[0] * 24,
                        business_hours={},
                        price=0,
                    ),
                    selected=True,
                )
            )

        time_slot_spots = [
            TimeSlotSpots(
                time_slot=TimeSlot.MORNING, spots=spots_info
            )  # Simplified time slot
        ]

        return RecommendSpots(
            recommend_spot_id=(
                recommend_spot_id or f"rec_{int(rec_spots[0].created_at.timestamp())}"
                if rec_spots
                else "rec_empty"
            ),
            recommend_spots=time_slot_spots,
        )

    def compare_versions(
        self, plan_id: str, old_version: int, new_version: int
    ) -> Dict[str, Any]:
        """
        Compare spots between two versions and return detailed analysis.
        """
        comparison = self.rec_spot_repo.get_version_comparison(
            plan_id, old_version, new_version
        )

        # Calculate statistics
        old_active_spots = [s for s in comparison["old_version_spots"] if s.is_active]
        new_active_spots = [s for s in comparison["new_version_spots"] if s.is_active]

        return {
            "plan_id": plan_id,
            "old_version": old_version,
            "new_version": new_version,
            "stats": {
                "old_active_count": len(old_active_spots),
                "new_active_count": len(new_active_spots),
                "added_count": len(comparison["added_spots"]),
                "kept_count": len(comparison["kept_spots"]),
                "deleted_count": len(comparison["deleted_spots"]),
            },
            "changes": {
                "added_spots": [s.spot_id for s in comparison["added_spots"]],
                "kept_spots": [s.spot_id for s in comparison["kept_spots"]],
                "deleted_spots": [s.spot_id for s in comparison["deleted_spots"]],
            },
        }

    def update_similarity_scores(
        self, plan_id: str, version: int, spot_scores: Dict[str, float]
    ) -> int:
        """
        Update similarity scores for spots in a specific version.
        Used after vector search processing.
        """
        return self.rec_spot_repo.update_similarity_scores_batch(
            plan_id, version, spot_scores
        )

    def get_spot_history(self, plan_id: str, spot_id: str) -> List[RecSpot]:
        """Get the history of a specific spot across all versions"""
        return self.rec_spot_repo.get_spot_history(plan_id, spot_id)

    def delete_spots_by_version(self, plan_id: str, version: int) -> int:
        """Delete all spots for a specific version"""
        return self.rec_spot_repo.delete_spots_by_plan_version(plan_id, version)

    def _extract_spot_ids_from_recommend_spots(
        self, recommend_spots: RecommendSpots
    ) -> Set[str]:
        """Extract all unique spot IDs from RecommendSpots structure"""
        spot_ids = set()
        for time_slot in recommend_spots.recommend_spots:
            for spot in time_slot.spots:
                spot_ids.add(spot.spot_id)
        return spot_ids

    def _determine_spot_statuses(
        self, current_spot_ids: Set[str], previous_spot_ids: Set[str]
    ) -> Dict[str, SpotStatus]:
        """
        Determine the status of each spot based on comparison with previous version.
        """
        status_map = {}

        for spot_id in current_spot_ids:
            if spot_id in previous_spot_ids:
                status_map[spot_id] = SpotStatus.KEEP
            else:
                status_map[spot_id] = SpotStatus.ADD

        return status_map
