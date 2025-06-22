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

        print(f"🎯 최종 응답 메타데이터:")
        print(f"  - Keywords: {recommendation_result.get('keywords_generated')}")
        print(f"  - Weights: {recommendation_result.get('initial_weights')}")
        print(
            f"  - Processing time: {recommendation_result.get('processing_time_ms')}ms"
        )
        print(f"  - API calls: {recommendation_result.get('api_calls_made')}")
        print(
            f"  - Final spots: {len(recommendation_result.get('recommend_spots', []))}"
        )

        # 실제 추천 결과를 적절한 형식으로 변환
        actual_spots = recommendation_result.get("recommend_spots", [])

        # 임시로 샘플 형식으로 변환 (실제 데이터 구조 확인용)
        print(f"📍 실제 생성된 스포트 데이터:")
        for i, spot in enumerate(actual_spots[:3]):  # 처음 3개만 로그 출력
            print(f"  Spot {i+1}: {spot}")

        # 실제 추천 결과 반환 (일단 원본 데이터 구조로)
        return {
            "recommend_spot_id": recommendation_result.get("rec_spot_id", "unknown"),
            "recommend_spots": actual_spots,
            "processing_time_ms": recommendation_result.get("processing_time_ms"),
            "api_calls_made": recommendation_result.get("api_calls_made"),
            "total_spots_found": recommendation_result.get("total_spots_found"),
            "scoring_weights": recommendation_result.get("scoring_weights"),
            "keywords_generated": recommendation_result.get("keywords_generated"),
            "initial_weights": recommendation_result.get("initial_weights"),
        }

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="pre_info_id must be a valid integer",
        )
