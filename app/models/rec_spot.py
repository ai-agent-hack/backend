from sqlalchemy import (
    Integer,
    String,
    DateTime,
    Numeric,
    Index,
    Boolean,
    Text,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any

from app.models.base import Base


class SpotStatus(str, Enum):
    """Enum for spot status"""

    ADD = "ADD"  # 새로 추가된 스팟
    KEEP = "KEEP"  # 이전 버전에서 유지된 스팟
    DEL = "DEL"  # 삭제된 스팟 (히스토리 보관용)


class RecSpot(Base):
    """
    RecSpot model representing recommendation spot status for each plan version.
    Tracks which spots were added, kept, or deleted in each version.
    """

    __tablename__ = "rec_spot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plan_id: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    spot_id: Mapped[str] = mapped_column(String(100), nullable=False)  # Google Place ID
    rank: Mapped[int] = mapped_column(Integer, nullable=False)  # 추천 순위
    status: Mapped[str] = mapped_column(String(10), nullable=False)  # ADD/KEEP/DEL
    similarity_score: Mapped[Decimal] = mapped_column(
        Numeric(precision=5, scale=4), nullable=True
    )
    # New spot detail columns
    time_slot: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True
    )  # '오전', '오후', '저녁'
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 8), nullable=True)
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(11, 8), nullable=True)
    spot_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    spot_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )  # congestion, business_hours, etc.
    recommendation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    website_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    selected: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, default=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships는 복합키로 인해 복잡하므로 repository에서 처리
    # rec_plan = relationship("RecPlan", back_populates="rec_spots")

    # Database indexes for performance
    __table_args__ = (
        Index("idx_rec_spot_plan_version", "plan_id", "version"),
        Index("idx_rec_spot_status", "status"),
        Index("idx_rec_spot_rank", "plan_id", "version", "rank"),
        Index("idx_rec_spot_time_slot", "plan_id", "version", "time_slot"),
    )

    def __repr__(self) -> str:
        return f"<RecSpot(plan_id='{self.plan_id}', version={self.version}, spot_id='{self.spot_id}', status='{self.status}')>"

    @property
    def is_active(self) -> bool:
        """Check if this spot is active (not deleted)"""
        return self.status in [SpotStatus.ADD, SpotStatus.KEEP]

    @property
    def similarity_score_float(self) -> float:
        """Get similarity score as float"""
        if self.similarity_score is None:
            return 0.0
        return float(self.similarity_score)

    def get_status_display(self) -> str:
        """Get human-readable status"""
        status_display = {
            SpotStatus.ADD: "새로 추가",
            SpotStatus.KEEP: "유지",
            SpotStatus.DEL: "삭제됨",
        }
        return status_display.get(self.status, self.status)
