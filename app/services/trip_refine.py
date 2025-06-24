from typing import List, Dict, Any, Optional
from datetime import datetime

from app.schemas.spot import RecommendSpots, RefineTriPlanRequest, ChatMessage
from app.services.rec_plan import RecPlanService
from app.services.rec_spot import RecSpotService
from app.services.recommendation_service import RecommendationService
from app.services.llm_service import LLMService


class TripRefineService:
    """
    Service for trip plan refinement.
    Integrates with existing recommendation pipeline while managing memory-only processing.
    Follows Open/Closed Principle - extends functionality without modifying existing services.
    """

    def __init__(
        self,
        rec_plan_service: RecPlanService,
        rec_spot_service: RecSpotService,
        recommendation_service: RecommendationService,
        llm_service: LLMService,
    ):
        self.rec_plan_service = rec_plan_service
        self.rec_spot_service = rec_spot_service
        self.recommendation_service = recommendation_service
        self.llm_service = llm_service

    async def refine_trip_plan(
        self, plan_id: str, refine_request: RefineTriPlanRequest
    ) -> RecommendSpots:
        """
        Main refine logic - processes in memory only, no DB saves.

        Process Flow:
        1. Get existing plan context (from DB)
        2. Extract keywords from chat history
        3. Run recommendation pipeline
        4. Return new RecommendSpots (no DB save)
        """

        # 1. Get plan context and validate
        plan_info = self.rec_plan_service.get_plan_info_with_pre_info(plan_id)

        # 2. Process chat history to extract user intent
        chat_summary = self._summarize_chat_history(refine_request.chat_history)
        refined_context = self._create_refined_context(
            plan_info["plan_context"], chat_summary, refine_request.recommend_spots
        )

        # 3. Process selected spots and generate new recommendations
        selected_spots = self._extract_selected_spots(refine_request.recommend_spots)

        # Generate new recommendations for non-selected spots only
        pre_info = plan_info.get("pre_info")
        if not pre_info:
            raise ValueError(f"PreInfo not found for plan {plan_id}")

        recommendation_result = (
            await self.recommendation_service.recommend_spots_from_pre_info(pre_info)
        )

        # Convert recommendation result and merge with selected spots
        new_spots = recommendation_result.get("recommend_spots", [])
        recommend_spot_id = recommendation_result.get(
            "rec_spot_id", f"refined_{plan_id}"
        )

        # Merge selected spots with new recommendations
        merged_spots = self._merge_selected_and_new_spots(selected_spots, new_spots)

        new_recommendations = RecommendSpots(
            recommend_spot_id=recommend_spot_id, recommend_spots=merged_spots
        )

        return new_recommendations

    def save_refined_plan(
        self, plan_id: str, recommend_spots: RecommendSpots
    ) -> Dict[str, Any]:
        """
        Save the refined plan as a new version.
        Used by /trip/{plan_id}/save endpoint.
        """

        # Get current plan info
        current_plan = self.rec_plan_service.get_plan_by_id(plan_id)
        if not current_plan:
            raise ValueError(f"Plan {plan_id} not found")

        # Create new plan version
        new_plan = self.rec_plan_service.create_new_version(plan_id)

        # Save spots with status tracking
        saved_spots = self.rec_spot_service.save_spots_for_plan_version(
            plan_id=plan_id,
            version=new_plan.version,
            recommend_spots=recommend_spots,
            previous_version=current_plan.version,
        )

        # Get version comparison for response
        comparison = self.rec_spot_service.compare_versions(
            plan_id, current_plan.version, new_plan.version
        )

        return {
            "plan_id": plan_id,
            "old_version": current_plan.version,
            "new_version": new_plan.version,
            "saved_at": new_plan.created_at,
            "spots_saved": len(saved_spots),
            "version_comparison": comparison,
        }

    def get_plan_with_spots(
        self, plan_id: str, version: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get plan information with associated spots.
        If version is None, gets the latest version.
        """

        if version:
            plan = self.rec_plan_service.get_plan_by_id_and_version(plan_id, version)
        else:
            plan = self.rec_plan_service.get_plan_by_id(plan_id)

        if not plan:
            raise ValueError(f"Plan {plan_id} version {version or 'latest'} not found")

        # Get spots for this version
        spots = self.rec_spot_service.get_active_spots_by_plan_version(
            plan_id, plan.version
        )

        # Convert spots back to RecommendSpots format
        recommend_spots = self.rec_spot_service.convert_rec_spots_to_recommend_spots(
            spots
        )

        return {
            "plan_id": plan.plan_id,
            "version": plan.version,
            "created_at": plan.created_at,
            "recommend_spots": recommend_spots,
            "spots_count": len(spots),
        }

    def _summarize_chat_history(
        self, chat_history: List[ChatMessage]
    ) -> Dict[str, Any]:
        """
        Process chat history to extract user preferences and intent.
        """
        if not chat_history:
            return {"user_intent": "No specific requests", "keywords": []}

        # Combine all user messages
        user_messages = [msg.message for msg in chat_history if msg.role == "user"]

        if not user_messages:
            return {"user_intent": "No user requests", "keywords": []}

        combined_user_input = " ".join(user_messages)

        # Use LLM service to extract intent and keywords
        # This would be implemented to call Vertex AI for keyword extraction
        return {
            "user_intent": combined_user_input,
            "keywords": self._extract_keywords_from_text(combined_user_input),
            "message_count": len(chat_history),
            "user_message_count": len(user_messages),
        }

    def _extract_keywords_from_text(self, text: str) -> List[str]:
        """
        Extract keywords from user text.
        This is a simplified implementation - would use LLM service in reality.
        """
        # Simple keyword extraction (would be replaced with LLM call)
        keywords = []

        # Common travel keywords
        keyword_mapping = {
            "카페": ["카페", "커피"],
            "음식": ["음식", "식당", "맛집", "레스토랑"],
            "문화": ["박물관", "갤러리", "전시"],
            "자연": ["공원", "산", "바다", "강"],
            "쇼핑": ["쇼핑", "백화점", "시장"],
            "액티비티": ["체험", "활동", "놀이"],
            "실내": ["실내", "indoor"],
            "야외": ["야외", "outdoor"],
            "조용한": ["조용", "평화", "힐링"],
            "활발한": ["활발", "신나는", "재미"],
        }

        text_lower = text.lower()
        for category, terms in keyword_mapping.items():
            if any(term in text_lower for term in terms):
                keywords.append(category)

        return keywords

    def _create_refined_context(
        self,
        original_context: Dict[str, Any],
        chat_summary: Dict[str, Any],
        current_spots: RecommendSpots,
    ) -> Dict[str, Any]:
        """
        Create refined context by merging original plan context with chat insights.
        """
        refined_context = original_context.copy()

        # Enhance atmosphere based on chat keywords
        if chat_summary["keywords"]:
            enhanced_atmosphere = f"{original_context['atmosphere']} + {', '.join(chat_summary['keywords'])}"
            refined_context["atmosphere"] = enhanced_atmosphere

        # Add user intent
        refined_context["user_intent"] = chat_summary["user_intent"]
        refined_context["refinement_keywords"] = chat_summary["keywords"]

        # Add current spots context for reference
        current_spot_ids = []
        for time_slot in current_spots.recommend_spots:
            current_spot_ids.extend([spot.spot_id for spot in time_slot.spots])

        refined_context["current_spots"] = current_spot_ids
        refined_context["spots_count"] = len(current_spot_ids)

        return refined_context

    def _extract_selected_spots(
        self, recommend_spots: RecommendSpots
    ) -> List[Dict[str, Any]]:
        """
        Extract spots that are marked as selected (selected: true).
        Returns list of spots grouped by time slot.
        """
        selected_spots = []

        for time_slot in recommend_spots.recommend_spots:
            selected_in_slot = [
                {"time_slot": time_slot.time_slot, "spot": spot}
                for spot in time_slot.spots
                if spot.selected
            ]
            selected_spots.extend(selected_in_slot)

        return selected_spots

    def _merge_selected_and_new_spots(
        self, selected_spots: List[Dict[str, Any]], new_spots: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Merge selected spots with new recommendations.
        Selected spots take priority and are preserved in their original time slots.
        New spots fill the remaining slots.
        """
        from app.schemas.spot import TimeSlot, Spot, TimeSlotSpots

        # Group selected spots by time slot
        selected_by_timeslot = {}
        for selected in selected_spots:
            time_slot = selected["time_slot"]
            if time_slot not in selected_by_timeslot:
                selected_by_timeslot[time_slot] = []
            selected_by_timeslot[time_slot].append(selected["spot"])

        # Create merged result with all time slots
        merged_time_slots = []

        # Process each time slot from new recommendations
        for new_time_slot in new_spots:
            time_slot_name = new_time_slot["time_slot"]

            # Start with selected spots for this time slot
            merged_spots = selected_by_timeslot.get(time_slot_name, [])

            # Add new spots to fill remaining slots (assuming max 8 spots per time slot)
            new_spots_in_slot = new_time_slot["spots"]
            spots_needed = max(8 - len(merged_spots), 0)

            # Add new spots up to the limit
            for i, new_spot in enumerate(new_spots_in_slot):
                if i < spots_needed:
                    # Convert dict to Spot object if needed
                    if isinstance(new_spot, dict):
                        merged_spots.append(Spot(**new_spot))
                    else:
                        merged_spots.append(new_spot)

            # Create TimeSlotSpots object correctly
            merged_time_slot = TimeSlotSpots(
                time_slot=TimeSlot(time_slot_name), spots=merged_spots
            )
            merged_time_slots.append(merged_time_slot)

        return merged_time_slots
