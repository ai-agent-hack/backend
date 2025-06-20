from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class PreInfoBase(BaseModel):
    """여행 사전정보 공통 필드"""

    departure_location: str = Field(..., description="출발지")
    start_date: datetime = Field(..., description="여행 시작일")
    end_date: datetime = Field(..., description="여행 종료일")
    atmosphere: str = Field(..., description="여행 분위기 (자유 기술)")
    budget: int = Field(..., ge=10000, description="예산 (원, 최소 10,000원)")
    region: str = Field(..., description="여행 지역")


class PreInfoRequest(PreInfoBase):
    """여행 사전정보 등록 요청"""

    pass


class PreInfoUpdate(BaseModel):
    """여행 사전정보 수정 요청"""

    departure_location: Optional[str] = Field(None, description="출발지")
    start_date: Optional[datetime] = Field(None, description="여행 시작일")
    end_date: Optional[datetime] = Field(None, description="여행 종료일")
    atmosphere: Optional[str] = Field(None, description="여행 분위기")
    budget: Optional[int] = Field(
        None, ge=10000, description="예산 (원, 최소 10,000원)"
    )
    region: Optional[str] = Field(None, description="여행 지역")


class PreInfoResponse(PreInfoBase):
    """여행 사전정보 응답"""

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
