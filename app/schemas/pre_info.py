from pydantic import BaseModel
from datetime import datetime

class PreInfoRequest(BaseModel):
    """旅行計画の事前情報"""
    departure_location: str  # 出発地
    start_date: datetime    # 旅行開始日
    end_date: datetime      # 旅行終了日
    atmosphere: str         # 旅行の雰囲気（自由記述）
    budget: int            # 予算
    region: str            # 地域

class PreInfoResponse(BaseModel):
    pre_info_id: str