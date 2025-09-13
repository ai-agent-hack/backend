from typing import List, Dict, Any, Optional
import copy

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
        if not plan_info or not plan_info.get("pre_info"):
            raise ValueError(f"Plan or PreInfo not found for plan_id {plan_id}")

        pre_info = plan_info["pre_info"]

        # 2. Process chat history to extract user intent
        chat_summary = await self._summarize_chat_history(refine_request.chat_history)

        # --- 📝 디버깅 로그 강화 ---
        print("---------- Refine Service Debugging ----------")
        print(
            f"🗣️ Raw Chat Input: {[msg.message for msg in refine_request.chat_history]}"
        )
        print(f"🤖 LLM Extraction Result: {chat_summary}")
        # ------------------------------------------

        # 3. Create a refined pre_info object with chat context
        refined_pre_info = copy.deepcopy(pre_info)

        # 3-1. 지역(Region) 정보 업데이트
        new_region = chat_summary.get("region")
        if new_region:
            print(
                f"🌍 Region updated: from '{refined_pre_info.region}' to '{new_region}'"
            )
            refined_pre_info.region = new_region

        # 3-2. 분위기(Atmosphere) 정보 강화
        if chat_summary["keywords"]:
            chat_keywords = ", ".join(chat_summary["keywords"])
            print(f"🎨 Atmosphere enhanced with keywords: {chat_keywords}")
            if refined_pre_info.atmosphere:
                refined_pre_info.atmosphere += f", {chat_keywords}"
            else:
                refined_pre_info.atmosphere = chat_keywords

        # 4. Process selected spots and generate new recommendations
        selected_spots = self._extract_selected_spots(refine_request.recommend_spots)

        # Chat 키워드를 추천 서비스에 전달하여 키워드 우선순위를 강화
        recommendation_result = await self.recommendation_service.get_recommendations(
            refined_pre_info,
            chat_keywords=chat_summary.get("keywords", []),
        )

        # Convert recommendation result and merge with selected spots
        new_spots = recommendation_result.get("recommend_spots", [])
        recommend_spot_id = recommendation_result.get(
            "rec_spot_id", f"refined_{plan_id}"
        )

        # Merge selected spots with new recommendations
        merged_spots = self._merge_selected_and_new_spots(selected_spots, new_spots)

        # Debug logging for selected spots preservation
        print(f"🔍 Refine Debug Info:")
        print(f"  - Original selected spots: {len(selected_spots)}")
        for spot_data in selected_spots:
            print(
                f"    • {spot_data['spot'].spot_id} in {spot_data['time_slot']} (selected: {spot_data['spot'].selected})"
            )

        # Count final selected spots
        final_selected_count = 0
        for time_slot in merged_spots:
            for spot in time_slot.spots:
                if spot.selected:
                    final_selected_count += 1
                    print(
                        f"    ✓ {spot.spot_id} in {time_slot.time_slot} (selected: {spot.selected})"
                    )

        print(f"  - Final selected spots preserved: {final_selected_count}")

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

    async def _summarize_chat_history(
        self, chat_history: List[ChatMessage]
    ) -> Dict[str, Any]:
        """
        Process chat history using LLM to extract refined user preferences and keywords.
        """
        if not chat_history:
            return {"user_intent": "No specific requests", "keywords": []}

        # Combine all user messages for context
        user_messages = [msg.message for msg in chat_history if msg.role == "user"]
        if not user_messages:
            return {"user_intent": "No user requests", "keywords": []}

        combined_user_input = " ".join(user_messages)

        # Use the LLM service to extract keywords and intent
        # This replaces the simple keyword mapping
        extracted_data = await self.llm_service.extract_keywords_from_chat(
            combined_user_input
        )

        return {
            "user_intent": extracted_data.get("intent", combined_user_input),
            "keywords": extracted_data.get("keywords", []),
            "region": extracted_data.get("region"),
            "message_count": len(chat_history),
            "user_message_count": len(user_messages),
        }

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

        # Group selected spots by time slot and create a set of selected spot IDs
        selected_by_timeslot = {}
        selected_spot_ids = set()

        for selected in selected_spots:
            time_slot = selected["time_slot"]
            spot = selected["spot"]

            if time_slot not in selected_by_timeslot:
                selected_by_timeslot[time_slot] = []

            # Ensure the selected spot has selected=True preserved
            spot.selected = True
            selected_by_timeslot[time_slot].append(spot)
            selected_spot_ids.add(spot.spot_id)

        # Create merged result with all time slots
        merged_time_slots = []

        # Get all time slots from both selected spots and new recommendations
        all_time_slots = set()
        all_time_slots.update(selected_by_timeslot.keys())
        for new_time_slot in new_spots:
            all_time_slots.add(new_time_slot["time_slot"])

        # Process each time slot
        for time_slot_name in all_time_slots:
            # Start with selected spots for this time slot (already have selected=True)
            merged_spots = selected_by_timeslot.get(time_slot_name, []).copy()

            # Find corresponding new time slot data
            new_time_slot_data = None
            for new_time_slot in new_spots:
                if new_time_slot["time_slot"] == time_slot_name:
                    new_time_slot_data = new_time_slot
                    break

            # Add new spots that are not already selected
            if new_time_slot_data:
                new_spots_in_slot = new_time_slot_data["spots"]

                for new_spot in new_spots_in_slot:
                    # Check if this spot was in the original selected list
                    spot_id = (
                        new_spot.get("spot_id")
                        if isinstance(new_spot, dict)
                        else new_spot.spot_id
                    )

                    # Only add if this spot was not already selected
                    if spot_id not in selected_spot_ids:
                        # Convert dict to Spot object if needed
                        if isinstance(new_spot, dict):
                            # Ensure selected is False for new spots
                            new_spot["selected"] = False
                            merged_spots.append(Spot(**new_spot))
                        else:
                            # For Spot objects, ensure selected is False
                            new_spot.selected = False
                            merged_spots.append(new_spot)

            # Create TimeSlotSpots object correctly (only if there are spots)
            if merged_spots:
                merged_time_slot = TimeSlotSpots(
                    time_slot=TimeSlot(time_slot_name), spots=merged_spots
                )
                merged_time_slots.append(merged_time_slot)

        return merged_time_slots
