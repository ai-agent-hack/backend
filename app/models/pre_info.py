from sqlalchemy import Column, Integer, String, DateTime, Text, Index, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from typing import Optional

from app.models.base import Base


class PreInfo(Base):
    """
    PreInfo model representing travel planning information.
    Follows Single Responsibility Principle - only handles pre-travel data structure.
    """

    __tablename__ = "pre_infos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    departure_location: Mapped[str] = mapped_column(String(200), nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atmosphere: Mapped[str] = mapped_column(Text, nullable=False)
    budget: Mapped[int] = mapped_column(Integer, nullable=False)
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationship with User
    # user = relationship("User", back_populates="pre_infos")

    # Database indexes for performance
    __table_args__ = (
        Index("idx_pre_info_user_id", "user_id"),
        Index("idx_pre_info_region", "region"),
        Index("idx_pre_info_dates", "start_date", "end_date"),
        Index("idx_pre_info_budget", "budget"),
    )

    def __repr__(self) -> str:
        return f"<PreInfo(id={self.id}, user_id={self.user_id}, region='{self.region}', departure='{self.departure_location}')>"
