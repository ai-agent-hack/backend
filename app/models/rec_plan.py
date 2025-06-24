from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from typing import List, Optional

from app.models.base import Base


class RecPlan(Base):
    """
    RecPlan model representing trip recommendation plan versions.
    Follows Single Responsibility Principle - only handles plan version management.
    """

    __tablename__ = "rec_plan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plan_id: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    pre_info_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pre_infos.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    pre_info = relationship("PreInfo", back_populates="rec_plans")
    # RecSpot relationship은 repository layer에서 처리 (복합키 관계로 인해 복잡함)

    # Database indexes for performance
    __table_args__ = (
        Index("idx_rec_plan_plan_id", "plan_id"),
        Index("idx_rec_plan_version", "plan_id", "version", unique=True),
    )

    def __repr__(self) -> str:
        return f"<RecPlan(plan_id='{self.plan_id}', version={self.version}, pre_info_id={self.pre_info_id})>"

    @property
    def is_latest_version(self) -> bool:
        """Check if this is the latest version for the plan_id"""
        # This would need a query to determine, implemented in service layer
        return True  # Placeholder

    def get_spot_count(self) -> int:
        """Get the number of spots in this plan version"""
        return len(self.rec_spots) if self.rec_spots else 0
