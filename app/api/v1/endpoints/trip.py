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
    RefineTriPlanRequest,
)
from app.services.pre_info import PreInfoService
from app.services.recommendation_service import RecommendationService
from app.core.dependencies import get_pre_info_service, get_recommendation_service

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

        # 実際の推薦結果を適切な形式に変換
        actual_spots = recommendation_result.get("recommend_spots", [])

        # 一時的にサンプル形式に変換（実際のデータ構造確認用）
        print(f"📍 実際に生成されたスポットデータ:")
        for i, spot in enumerate(actual_spots[:3]):  # 最初の3件のみログ出力
            print(f"  Spot {i+1}: {spot}")

        # 実際の推薦結果を返す（一旦元のデータ構造で）
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

@router.post(
    "/{plan_id}/refine", response_model=RecommendSpots, status_code=status.HTTP_200_OK
)
async def refine_trip_plan(
    plan_id: str,
    input_data: RefineTriPlanRequest,
) -> RecommendSpots:
    """
    既存のトリッププランを精査・改善するエンドポイント
    """
    # TODO: plan_idを使って既存のプランを取得し、精査するロジックを実装
    # input_data.recommend_spots: 現在の推薦スポット情報
    # input_data.feedback: ユーザーからのフィードバック（オプション）
    return _generate_sample_spots()
