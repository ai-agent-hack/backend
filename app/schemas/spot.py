from pydantic import BaseModel
from typing import List, Optional
from enum import Enum
from datetime import time


class TimeSlot(str, Enum):
    MORNING = "午前"
    AFTERNOON = "午後"
    NIGHT = "夜"


class DayOfWeek(str, Enum):
    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"
    HOLIDAY = "HOLIDAY"


class BusinessHours(BaseModel):
    """営業時間の詳細情報"""

    open_time: Optional[time] = None
    close_time: Optional[time] = None


class BusinessHoursPerDay(BaseModel):
    """曜日ごとの営業時間"""

    MONDAY: Optional[BusinessHours] = None
    TUESDAY: Optional[BusinessHours] = None
    WEDNESDAY: Optional[BusinessHours] = None
    THURSDAY: Optional[BusinessHours] = None
    FRIDAY: Optional[BusinessHours] = None
    SATURDAY: Optional[BusinessHours] = None
    SUNDAY: Optional[BusinessHours] = None
    HOLIDAY: Optional[BusinessHours] = None


class SpotDetail(BaseModel):
    """スポットの詳細情報"""

    name: str
    congestion: List[int]  # 0-23時の混雑度
    business_hours: BusinessHoursPerDay  # 曜日ごとの営業時間
    price: Optional[int] = None


class Spot(BaseModel):
    """個別のスポット情報"""

    spot_id: str
    longitude: float
    latitude: float
    recommendation_reason: str
    details: SpotDetail
    google_map_image_url: Optional[str] = None
    website_url: Optional[str] = None
    selected: bool = False
    similarity_score: Optional[float] = None


class TimeSlotSpots(BaseModel):
    """時間帯ごとのスポット情報"""

    time_slot: TimeSlot
    spots: List[Spot]


class RecommendSpots(BaseModel):
    """おすすめスポットの全体情報"""

    recommend_spot_id: str
    recommend_spots: List[TimeSlotSpots]


class ChatRole(str, Enum):
    """チャットのロール"""

    ASSISTANT = "assistant"
    USER = "user"


class ChatMessage(BaseModel):
    """チャットメッセージ"""

    role: ChatRole
    message: str


class RecommendSpotFromChatRequest(BaseModel):
    """スポット推薦の入力スキーマ"""

    chat: List[ChatMessage]
    recommend_spot: RecommendSpots


class RecommendSpotFromPreInfoRequest(BaseModel):
    """スポット推薦の入力スキーマ"""

    pre_info_id: str


class RefineTriPlanRequest(BaseModel):
    """トリッププラン精査の入力スキーマ"""

    chat_history: List[ChatMessage]
    recommend_spots: RecommendSpots
