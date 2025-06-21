from fastapi import APIRouter, status, Depends, HTTPException
from datetime import time

from app.schemas.spot import (
    RecommendSpots,
    TimeSlotSpots,
    Spot,
    SpotDetail,
    TimeSlot,
    DayOfWeek,
    BusinessHours,
    RecommendSpotFromPreInfoRequest,
)
from app.services.pre_info import PreInfoService
from app.services.recommendation_service import RecommendationService
from app.core.dependencies import get_pre_info_service, get_recommendation_service

router = APIRouter()


def _generate_sample_spots() -> RecommendSpots:
    """サンプルのスポット情報を生成する共通関数 (임시)"""
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
) -> RecommendSpots:
    """
    pre_infoからトリップのシードとなるスポット推薦を生成するエンドポイント
    ※開発中のため認証不要
    """
    try:
        # Step 1: DB에서 pre_info 데이터 가져오기
        pre_info_id = int(input_data.pre_info_id)
        pre_info = pre_info_service.pre_info_repository.get(pre_info_id)

        if not pre_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"pre_info with id {pre_info_id} not found",
            )

        # Step 2: 추천 서비스 호출
        recommendation_result = (
            await recommendation_service.recommend_spots_from_pre_info(pre_info)
        )

        # 실제 추천 결과에 디버깅 정보 추가하여 반환
        sample_spots = _generate_sample_spots()

        # 현재는 샘플 데이터에 실제 메타데이터를 추가
        enhanced_response = {
            **sample_spots.model_dump(),
            "rec_spot_id": recommendation_result.get("rec_spot_id"),
            "processing_time_ms": recommendation_result.get("processing_time_ms"),
            "api_calls_made": recommendation_result.get("api_calls_made"),
            "total_spots_found": recommendation_result.get("total_spots_found"),
            "scoring_weights": recommendation_result.get("scoring_weights"),
            "keywords_generated": recommendation_result.get("keywords_generated"),
            "initial_weights": recommendation_result.get("initial_weights"),
        }

        print(f"🎯 최종 응답 메타데이터:")
        print(f"  - Keywords: {recommendation_result.get('keywords_generated')}")
        print(f"  - Weights: {recommendation_result.get('initial_weights')}")
        print(
            f"  - Processing time: {recommendation_result.get('processing_time_ms')}ms"
        )
        print(f"  - API calls: {recommendation_result.get('api_calls_made')}")

        # TODO: 나중에는 sample_spots 대신 실제 recommend_spots 반환
        return RecommendSpots(
            **{
                k: v
                for k, v in enhanced_response.items()
                if k in ["recommend_spot_id", "recommend_spots"]
            }
        )

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="pre_info_id must be a valid integer",
        )
