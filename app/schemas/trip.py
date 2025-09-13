from pydantic import BaseModel
from typing import Dict, Any, List
from datetime import datetime
from app.schemas.spot import RecommendSpots


class SaveTripPlanRequest(BaseModel):
    """トリッププラン保存リクエスト"""

    recommend_spots: RecommendSpots


class TripSeedResponse(BaseModel):
    """trip/seed エンドポイントのレスポンス"""

    plan_id: str
    recommend_spots: RecommendSpots


class SaveTripPlanResponse(BaseModel):
    """トリッププラン保存レスポンス"""

    plan_id: str
    old_version: int
    new_version: int
    saved_at: datetime
    spots_saved: int
    version_comparison: Dict[str, Any]


class TripPlanInfo(BaseModel):
    """トリッププラン情報"""

    plan_id: str
    version: int
    pre_info_id: int
    created_at: datetime
    total_spots: int


class TripPlanResponse(BaseModel):
    """トリッププラン取得レスポンス"""

    plan_info: TripPlanInfo
    recommend_spots: RecommendSpots
    all_versions: List[int]
