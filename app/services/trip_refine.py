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

        # 3. Generate new recommendations using existing pipeline
        # Note: This uses the same recommendation service as /trip/seed
        new_recommendations = (
            await self.recommendation_service.generate_recommendations(
                pre_info_context=refined_context, chat_context=chat_summary
            )
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
