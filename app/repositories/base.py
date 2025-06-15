from typing import Generic, TypeVar, Type, Optional, List, Any, Dict
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.base import Base

# Type variables for generic repository
ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    Base repository class implementing common CRUD operations.
    Follows Repository pattern and Single Responsibility Principle.
    """

    def __init__(self, model: Type[ModelType], db: Session):
        """
        Initialize repository with model and database session.

        Args:
            model: SQLAlchemy model class
            db: Database session
        """
        self.model = model
        self.db = db

    def get(self, id: int) -> Optional[ModelType]:
        """
        Get a single record by ID.

        Args:
            id: Record ID

        Returns:
            Model instance or None if not found
        """
        return self.db.query(self.model).filter(self.model.id == id).first()

    def get_multi(
        self, skip: int = 0, limit: int = 100, filters: Optional[Dict[str, Any]] = None
    ) -> List[ModelType]:
        """
        Get multiple records with pagination and filtering.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Optional filters to apply

        Returns:
            List of model instances
        """
        query = self.db.query(self.model)

        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.filter(getattr(self.model, key) == value)

        return query.offset(skip).limit(limit).all()

    def create(self, obj_in: CreateSchemaType) -> ModelType:
        """
        Create a new record.

        Args:
            obj_in: Pydantic schema with data for creation

        Returns:
            Created model instance

        Raises:
            IntegrityError: If unique constraints are violated
        """
        obj_data = obj_in.dict()
        db_obj = self.model(**obj_data)

        self.db.add(db_obj)
        try:
            self.db.commit()
            self.db.refresh(db_obj)
            return db_obj
        except IntegrityError:
            self.db.rollback()
            raise

    def update(self, db_obj: ModelType, obj_in: UpdateSchemaType) -> ModelType:
        """
        Update an existing record.

        Args:
            db_obj: Existing model instance
            obj_in: Pydantic schema with update data

        Returns:
            Updated model instance
        """
        obj_data = obj_in.dict(exclude_unset=True)

        for field, value in obj_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        try:
            self.db.commit()
            self.db.refresh(db_obj)
            return db_obj
        except IntegrityError:
            self.db.rollback()
            raise

    def delete(self, id: int) -> Optional[ModelType]:
        """
        Delete a record by ID.

        Args:
            id: Record ID to delete

        Returns:
            Deleted model instance or None if not found
        """
        obj = self.get(id)
        if obj:
            self.db.delete(obj)
            self.db.commit()
        return obj

    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count records with optional filtering.

        Args:
            filters: Optional filters to apply

        Returns:
            Number of records matching criteria
        """
        query = self.db.query(self.model)

        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.filter(getattr(self.model, key) == value)

        return query.count()

    def exists(self, id: int) -> bool:
        """
        Check if a record exists by ID.

        Args:
            id: Record ID

        Returns:
            True if record exists, False otherwise
        """
        return self.db.query(self.model).filter(self.model.id == id).first() is not None
