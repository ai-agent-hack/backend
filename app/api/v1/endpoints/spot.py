from fastapi import APIRouter, status
from datetime import time

from app.schemas.spot import (
    RecommendSpots, TimeSlotSpots, Spot, SpotDetail, TimeSlot,
    DayOfWeek, BusinessHours, RecommendSpotFromChatRequest, RecommendSpotFromPreInfoRequest
)

router = APIRouter()

def _generate_sample_spots() -> RecommendSpots:
    """サンプルのスポット情報を生成する共通関数"""
    business_hours = {
        day: BusinessHours(
            open_time=time(9, 0),  # 9:00
            close_time=time(17, 0),  # 17:00
        ) for day in DayOfWeek
    }

    return RecommendSpots(
        recommend_spot_id="aaaaaaa",
        recommend_spots=[
            TimeSlotSpots(
                time_slot=TimeSlot.MORNING,
                spots=[
                    Spot(
                        spot_id="aaaa",
                        longitude=124.13,
                        latitude=124.13,
                        recommendation_reason="夜景が綺麗って口コミで言われてるでー",
                        details=SpotDetail(
                            name="六甲山",
                            congestion=[1, 3, 4, 5] + [0] * 20,  # 0-23時の混雑度
                            business_hours=business_hours,
                            price=500
                        ),
                        selected=False
                    )
                ]
            ),
            TimeSlotSpots(
                time_slot=TimeSlot.AFTERNOON,
                spots=[
                    Spot(
                        spot_id="aaaa",
                        longitude=124.13,
                        latitude=124.13,
                        recommendation_reason="夜景が綺麗って口コミで言われてるでー",
                        details=SpotDetail(
                            name="六甲山",
                            congestion=[1, 3, 4, 5] + [0] * 20,  # 0-23時の混雑度
                            business_hours=business_hours,
                            price=500
                        ),
                        selected=False
                    )
                ]
            ),
            TimeSlotSpots(
                time_slot=TimeSlot.NIGHT,
                spots=[
                    Spot(
                        spot_id="aaaa",
                        longitude=124.13,
                        latitude=124.13,
                        recommendation_reason="夜景が綺麗って口コミで言われてるでー",
                        details=SpotDetail(
                            name="六甲山",
                            congestion=[1, 3, 4, 5] + [0] * 20,  # 0-23時の混雑度
                            business_hours=business_hours,
                            price=500
                        ),
                        selected=False
                    )
                ]
            )
        ]
    )

@router.post("/spot/pre_info", response_model=RecommendSpots, status_code=status.HTTP_201_CREATED)
async def spot_from_pre_info(
    input_data: RecommendSpotFromPreInfoRequest,
) -> RecommendSpots:
    """
    pre_infoからスポット情報を生成するエンドポイント
    """
    # TODO: pre_infoからスポット情報を生成するロジックを実装
    return _generate_sample_spots()

@router.post("/spot/chat", response_model=RecommendSpots, status_code=status.HTTP_201_CREATED)
async def spot_from_chat(
    input_data: RecommendSpotFromChatRequest,
) -> RecommendSpots:
    """
    chatからスポット情報を生成するエンドポイント
    """
    # TODO: chatからスポット情報を生成するロジックを実装
    return _generate_sample_spots()



