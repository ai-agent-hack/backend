from typing import Optional, List
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

    def get_by_firebase_uid(self, firebase_uid: str) -> Optional[User]:
        """
        Get user by Firebase UID.

        Args:
            firebase_uid: Firebase user UID

        Returns:
            User instance or None if not found
        """
        return self.db.query(User).filter(User.firebase_uid == firebase_uid).first()

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

    def get_active_user_by_firebase_uid(self, firebase_uid: str) -> Optional[User]:
        """
        Get active user by Firebase UID.

        Args:
            firebase_uid: Firebase user UID

        Returns:
            Active user instance or None if not found or inactive
        """
        return (
            self.db.query(User)
            .filter(User.firebase_uid == firebase_uid, User.is_active == True)
            .first()
        )

    def create_firebase_user(
        self, firebase_uid: str, email: str, username: str
    ) -> User:
        """
        Create user from Firebase authentication.

        Args:
            firebase_uid: Firebase user UID
            email: User's email address
            username: User's username

        Returns:
            Created user instance
        """
        db_obj = User(
            firebase_uid=firebase_uid, email=email, username=username, is_active=True
        )
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

    def firebase_uid_exists(self, firebase_uid: str) -> bool:
        """
        Check if Firebase UID already exists in database.

        Args:
            firebase_uid: Firebase UID to check

        Returns:
            True if Firebase UID exists, False otherwise
        """
        return (
            self.db.query(User).filter(User.firebase_uid == firebase_uid).first()
            is not None
        )

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

    def get_users(
        self, skip: int = 0, limit: int = 100, active_only: bool = False
    ) -> List[User]:
        """
        Get list of users with pagination.

        Args:
            skip: Number of users to skip
            limit: Maximum number of users to return
            active_only: Whether to return only active users

        Returns:
            List of users
        """
        query = self.db.query(User)
        if active_only:
            query = query.filter(User.is_active == True)
        return query.offset(skip).limit(limit).all()

    def count_users(self, active_only: bool = False) -> int:
        """
        Count total number of users.

        Args:
            active_only: Whether to count only active users

        Returns:
            Number of users
        """
        query = self.db.query(User)
        if active_only:
            query = query.filter(User.is_active == True)
        return query.count()
