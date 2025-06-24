from fastapi import APIRouter, status, Depends, HTTPException
from datetime import time
from typing import Optional

from app.schemas.spot import (
    RecommendSpots,
    TimeSlotSpots,
    Spot,
    SpotDetail,
    TimeSlot,
    DayOfWeek,
    BusinessHours,
    RecommendSpotFromPreInfoRequest,
    RefineTriPlanRequest,
)
from app.schemas.trip import (
    SaveTripPlanRequest,
    SaveTripPlanResponse,
    TripPlanInfo,
    TripPlanResponse,
)
from app.services.pre_info import PreInfoService
from app.services.recommendation_service import RecommendationService
from app.services.trip_refine import TripRefineService
from app.services.rec_plan import RecPlanService
from app.services.rec_spot import RecSpotService
from app.core.dependencies import (
    get_pre_info_service,
    get_recommendation_service,
    get_trip_refine_service,
    get_rec_plan_service,
    get_rec_spot_service,
)

router = APIRouter()


def _generate_sample_spots() -> RecommendSpots:
    """サンプルのスポット情報を生成する共通関数 (一時的)"""
    business_hours = {
        day: BusinessHours(
            open_time=time(9, 0),  # 9:00
            close_time=time(17, 0),  # 17:00
        )
        for day in DayOfWeek
    }

    return RecommendSpots(
        recommend_spot_id="aaaaaaa",
        recommend_spots=[
            TimeSlotSpots(
                time_slot=TimeSlot.MORNING,
                spots=[
                    Spot(
                        spot_id="aaaa",
                        longitude=139,
                        latitude=35,
                        recommendation_reason="夜景が綺麗って口コミで言われてるでー",
                        details=SpotDetail(
                            name="六甲山",
                            congestion=[1, 3, 4, 5] + [0] * 20,  # 0-23時の混雑度
                            business_hours=business_hours,
                            price=500,
                        ),
                        selected=False,
                    )
                ],
            ),
            TimeSlotSpots(
                time_slot=TimeSlot.AFTERNOON,
                spots=[
                    Spot(
                        spot_id="aaaa",
                        longitude=139,
                        latitude=35,
                        recommendation_reason="夜景が綺麗って口コミで言われてるでー",
                        details=SpotDetail(
                            name="六甲山",
                            congestion=[1, 3, 4, 5] + [0] * 20,  # 0-23時の混雑度
                            business_hours=business_hours,
                            price=500,
                        ),
                        selected=False,
                    )
                ],
            ),
            TimeSlotSpots(
                time_slot=TimeSlot.NIGHT,
                spots=[
                    Spot(
                        spot_id="aaaa",
                        longitude=139,
                        latitude=35,
                        recommendation_reason="夜景が綺麗って口コミで言われてるでー",
                        details=SpotDetail(
                            name="六甲山",
                            congestion=[1, 3, 4, 5] + [0] * 20,  # 0-23時の混雑度
                            business_hours=business_hours,
                            price=500,
                        ),
                        selected=False,
                    )
                ],
            ),
        ],
    )


@router.post(
    "/seed", response_model=RecommendSpots, status_code=status.HTTP_201_CREATED
)
async def create_trip_seed_from_pre_info(
    input_data: RecommendSpotFromPreInfoRequest,
    pre_info_service: PreInfoService = Depends(get_pre_info_service),
    recommendation_service: RecommendationService = Depends(get_recommendation_service),
    rec_plan_service: RecPlanService = Depends(get_rec_plan_service),
    rec_spot_service: RecSpotService = Depends(get_rec_spot_service),
) -> RecommendSpots:
    """
    pre_infoからトリップのシードとなるスポット推薦を生成するエンドポイント
    ※開発中のため認証不要
    """
    try:
        # Step 1: DBからpre_infoデータを取得
        pre_info_id = int(input_data.pre_info_id)
        pre_info = pre_info_service.pre_info_repository.get(pre_info_id)

        if not pre_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"pre_info with id {pre_info_id} not found",
            )

        # Step 2: 推薦サービスを呼び出し
        recommendation_result = (
            await recommendation_service.recommend_spots_from_pre_info(pre_info)
        )

        print(f"🎯 最終レスポンスメタデータ:")
        print(f"  - Keywords: {recommendation_result.get('keywords_generated')}")
        print(f"  - Weights: {recommendation_result.get('initial_weights')}")
        print(
            f"  - Processing time: {recommendation_result.get('processing_time_ms')}ms"
        )
        print(f"  - API calls: {recommendation_result.get('api_calls_made')}")
        print(
            f"  - Final spots: {len(recommendation_result.get('recommend_spots', []))}"
        )

        # 실제 추천 결과를 RecommendSpots 형식으로 변환
        actual_spots = recommendation_result.get("recommend_spots", [])
        recommend_spot_id = recommendation_result.get("rec_spot_id", "unknown")

        # RecommendSpots 객체 생성
        recommend_spots = RecommendSpots(
            recommend_spot_id=recommend_spot_id, recommend_spots=actual_spots
        )

        # Step 3: 초기 플랜 생성 (plan_id는 recommend_spot_id 사용)
        plan_id = recommend_spot_id
        try:
            initial_plan = rec_plan_service.create_initial_plan(plan_id, pre_info_id)
            print(
                f"✅ Initial plan created: {plan_id} (version {initial_plan.version})"
            )

            # Step 4: 스팟들을 DB에 저장
            saved_spots = rec_spot_service.save_spots_for_plan_version(
                plan_id=plan_id,
                version=initial_plan.version,
                recommend_spots=recommend_spots,
                previous_version=None,  # 초기 버전이므로 이전 버전 없음
            )
            print(f"✅ Saved {len(saved_spots)} spots for plan {plan_id}")

            # Step 5: similarity_score 업데이트
            spot_scores = {}
            for time_slot in recommend_spots.recommend_spots:
                for spot in time_slot.spots:
                    # RecommendSpots에서 similarity_score 추출
                    if (
                        hasattr(spot, "similarity_score")
                        and spot.similarity_score is not None
                    ):
                        spot_scores[spot.spot_id] = spot.similarity_score
                    # 또는 spot dict에서 추출
                    elif isinstance(spot, dict) and "similarity_score" in spot:
                        spot_scores[spot["spot_id"]] = spot["similarity_score"]

            if spot_scores:
                rec_spot_service.update_similarity_scores(
                    plan_id=plan_id,
                    version=initial_plan.version,
                    spot_scores=spot_scores,
                )
                print(f"✅ Updated similarity scores for {len(spot_scores)} spots")

        except Exception as e:
            print(f"⚠️ Warning: Could not save to database: {e}")
            # DB 저장 실패해도 추천 결과는 반환

        print(f"📍 실際に生成されたスポットデータ:")
        for i, spot in enumerate(actual_spots[:3]):  # 최초 3건만 로그 출력
            print(f"  Spot {i+1}: {spot}")

        # 추천 결과 반환
        return recommend_spots

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="pre_info_id must be a valid integer",
        )


@router.post(
    "/{plan_id}/refine", response_model=RecommendSpots, status_code=status.HTTP_200_OK
)
async def refine_trip_plan(
    plan_id: str,
    input_data: RefineTriPlanRequest,
    trip_refine_service: TripRefineService = Depends(get_trip_refine_service),
) -> RecommendSpots:
    """
    既存のトリッププランを精査・改善するエンドポイント
    メモリのみで処理し、DBには保存しない
    """
    try:
        # TripRefineServiceを使って推薦 개선 처리
        refined_recommendations = await trip_refine_service.refine_trip_plan(
            plan_id=plan_id, refine_request=input_data
        )

        print(f"🔄 Plan {plan_id} refined successfully")
        print(f"  - Chat messages: {len(input_data.chat_history)}")
        print(f"  - Current spots: {len(input_data.recommend_spots.recommend_spots)}")
        print(f"  - New spots: {len(refined_recommendations.recommend_spots)}")

        return refined_recommendations

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        print(f"❌ Error refining plan {plan_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refine trip plan: {str(e)}",
        )


@router.post(
    "/{plan_id}/save",
    response_model=SaveTripPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def save_trip_plan(
    plan_id: str,
    input_data: SaveTripPlanRequest,
    trip_refine_service: TripRefineService = Depends(get_trip_refine_service),
) -> SaveTripPlanResponse:
    """
    精査・改善されたトリッププランを新しいバージョンとして保存
    """
    try:
        # TripRefineServiceを使って플랜 저장
        save_result = trip_refine_service.save_refined_plan(
            plan_id=plan_id, recommend_spots=input_data.recommend_spots
        )

        print(f"💾 Plan {plan_id} saved successfully")
        print(
            f"  - Version: {save_result['old_version']} → {save_result['new_version']}"
        )
        print(f"  - Spots saved: {save_result['spots_saved']}")

        return SaveTripPlanResponse(**save_result)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        print(f"❌ Error saving plan {plan_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save trip plan: {str(e)}",
        )


@router.get(
    "/{plan_id}", response_model=TripPlanResponse, status_code=status.HTTP_200_OK
)
async def get_trip_plan(
    plan_id: str,
    version: Optional[int] = None,
    rec_plan_service: RecPlanService = Depends(get_rec_plan_service),
) -> TripPlanResponse:
    """
    トリッププランを取得（指定バージョンまたは최신）
    """
    try:
        # RecPlanServiceを使って플랜 조회
        plan_data = rec_plan_service.get_plan_with_spots(
            plan_id=plan_id, version=version
        )

        if not plan_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Trip plan {plan_id} not found",
            )

        # 모든 버전 목록 조회
        all_versions = rec_plan_service.get_plan_versions(plan_id)

        print(f"📖 Plan {plan_id} retrieved successfully")
        print(f"  - Version: {plan_data['plan_info']['version']}")
        print(f"  - Total spots: {plan_data['plan_info']['total_spots']}")
        print(f"  - Available versions: {all_versions}")

        return TripPlanResponse(
            plan_info=TripPlanInfo(**plan_data["plan_info"]),
            recommend_spots=plan_data["recommend_spots"],
            all_versions=all_versions,
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        print(f"❌ Error retrieving plan {plan_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve trip plan: {str(e)}",
        )
