from datetime import datetime
from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.ext.declarative import as_declarative, declared_attr


@as_declarative()
class Base:
    """
    Base class for all database models.
    Provides common fields and naming conventions.
    """

    id: int
    __name__: str

    # Auto-generate table names from class names
    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower()

    # Common fields for all models
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        comment="Timestamp when the record was created",
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment="Timestamp when the record was last updated",
    )
