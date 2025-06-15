from typing import Optional
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
    """
    User repository implementing user-specific database operations.
    Extends BaseRepository with user-specific queries.
    """

    def __init__(self, db: Session):
        """Initialize user repository with database session."""
        super().__init__(User, db)

    def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email address.

        Args:
            email: User's email address

        Returns:
            User instance or None if not found
        """
        return self.db.query(User).filter(User.email == email).first()

    def get_by_username(self, username: str) -> Optional[User]:
        """
        Get user by username.

        Args:
            username: User's username

        Returns:
            User instance or None if not found
        """
        return self.db.query(User).filter(User.username == username).first()

    def get_active_user_by_email(self, email: str) -> Optional[User]:
        """
        Get active user by email address.

        Args:
            email: User's email address

        Returns:
            Active user instance or None if not found or inactive
        """
        return (
            self.db.query(User)
            .filter(User.email == email, User.is_active == True)
            .first()
        )

    def get_active_user_by_username(self, username: str) -> Optional[User]:
        """
        Get active user by username.

        Args:
            username: User's username

        Returns:
            Active user instance or None if not found or inactive
        """
        return (
            self.db.query(User)
            .filter(User.username == username, User.is_active == True)
            .first()
        )

    def create_user_with_hashed_password(
        self, user_create: UserCreate, hashed_password: str
    ) -> User:
        """
        Create user with pre-hashed password.

        Args:
            user_create: User creation data
            hashed_password: Already hashed password

        Returns:
            Created user instance
        """
        user_data = user_create.dict()
        user_data["hashed_password"] = hashed_password
        # Remove plain password from data
        if "password" in user_data:
            del user_data["password"]

        db_obj = User(**user_data)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def email_exists(self, email: str) -> bool:
        """
        Check if email already exists in database.

        Args:
            email: Email address to check

        Returns:
            True if email exists, False otherwise
        """
        return self.db.query(User).filter(User.email == email).first() is not None

    def username_exists(self, username: str) -> bool:
        """
        Check if username already exists in database.

        Args:
            username: Username to check

        Returns:
            True if username exists, False otherwise
        """
        return self.db.query(User).filter(User.username == username).first() is not None

    def deactivate_user(self, user_id: int) -> Optional[User]:
        """
        Deactivate a user account.

        Args:
            user_id: User ID to deactivate

        Returns:
            Updated user instance or None if not found
        """
        user = self.get(user_id)
        if user:
            user.is_active = False
            self.db.commit()
            self.db.refresh(user)
        return user

    def activate_user(self, user_id: int) -> Optional[User]:
        """
        Activate a user account.

        Args:
            user_id: User ID to activate

        Returns:
            Updated user instance or None if not found
        """
        user = self.get(user_id)
        if user:
            user.is_active = True
            self.db.commit()
            self.db.refresh(user)
        return user
