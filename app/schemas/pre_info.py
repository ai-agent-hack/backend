from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional


class PreInfoBase(BaseModel):
    """旅行事前情報の共通フィールド"""

    start_date: datetime = Field(..., description="旅行開始日")
    end_date: datetime = Field(..., description="旅行終了日")
    atmosphere: str = Field(..., description="旅行の雰囲気（自由記述）")
    budget: int = Field(..., ge=10000, description="予算（ウォン、最低10,000ウォン）")
    participants_count: int = Field(
        default=2, ge=1, le=20, description="旅行参加者数（1-20名）"
    )
    region: str = Field(..., description="旅行地域")


class PreInfoRequest(PreInfoBase):
    """旅行事前情報登録リクエスト"""

    model_config = ConfigDict(extra="ignore")

    departure_location: Optional[str] = Field(None, description="출발지 (무시됨)")


class PreInfoUpdate(BaseModel):
    """旅行事前情報修正リクエスト"""

    start_date: Optional[datetime] = Field(None, description="旅行開始日")
    end_date: Optional[datetime] = Field(None, description="旅行終了日")
    atmosphere: Optional[str] = Field(None, description="旅行の雰囲気")
    budget: Optional[int] = Field(
        None, ge=10000, description="予算（ウォン、最低10,000ウォン）"
    )
    participants_count: Optional[int] = Field(
        None, ge=1, le=20, description="旅行参加者数（1-20名）"
    )
    region: Optional[str] = Field(None, description="旅行地域")


class PreInfoResponse(PreInfoBase):
    """旅行事前情報レスポンス"""

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
