from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class PreInfoBase(BaseModel):
    """旅行事前情報の共通フィールド"""

    departure_location: str = Field(..., description="出発地")
    start_date: datetime = Field(..., description="旅行開始日")
    end_date: datetime = Field(..., description="旅行終了日")
    atmosphere: str = Field(..., description="旅行の雰囲気（自由記述）")
    budget: int = Field(..., ge=10000, description="予算（ウォン、最低10,000ウォン）")
    region: str = Field(..., description="旅行地域")


class PreInfoRequest(PreInfoBase):
    """旅行事前情報登録リクエスト"""

    pass


class PreInfoUpdate(BaseModel):
    """旅行事前情報修正リクエスト"""

    departure_location: Optional[str] = Field(None, description="出発地")
    start_date: Optional[datetime] = Field(None, description="旅行開始日")
    end_date: Optional[datetime] = Field(None, description="旅行終了日")
    atmosphere: Optional[str] = Field(None, description="旅行の雰囲気")
    budget: Optional[int] = Field(
        None, ge=10000, description="予算（ウォン、最低10,000ウォン）"
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
