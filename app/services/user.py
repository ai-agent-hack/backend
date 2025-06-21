from typing import List, Optional

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, FirebaseUserCreate
from app.repositories.user import UserRepository
from app.core.firebase import FirebaseService
from app.core.exceptions import (
    UserAlreadyExistsError,
    UserNotFoundError,
    InvalidCredentialsError,
)


class UserService:
    """
    User service for business logic operations.
    Follows Single Responsibility Principle - only handles user business operations.
    """

    def __init__(
        self,
        user_repository: UserRepository,
        firebase_service: Optional[FirebaseService] = None,
    ):
        self.user_repository = user_repository
        self.firebase_service = firebase_service

    async def create_firebase_user(
        self, firebase_user_create: FirebaseUserCreate
    ) -> User:
        """
        Create a Firebase user after verifying Firebase token.

        Args:
            firebase_user_create: Firebase user creation data with token

        Returns:
            Created user instance

        Raises:
            InvalidCredentialsError: If Firebase token is invalid
            UserAlreadyExistsError: If user already exists
        """
        if not self.firebase_service:
            raise InvalidCredentialsError()

        # Verify Firebase token first
        decoded_token = await self.firebase_service.verify_id_token(
            firebase_user_create.firebase_token
        )
        if not decoded_token:
            raise InvalidCredentialsError()

        firebase_uid = decoded_token["uid"]
        email = decoded_token.get("email")

        if not email:
            raise InvalidCredentialsError()

        # Check if user already exists
        existing_user = self.user_repository.get_by_firebase_uid(firebase_uid)
        if existing_user:
            raise UserAlreadyExistsError("firebase_uid", firebase_uid)

        if self.user_repository.email_exists(email):
            raise UserAlreadyExistsError("email", email)

        if self.user_repository.username_exists(firebase_user_create.username):
            raise UserAlreadyExistsError("username", firebase_user_create.username)

        # Create user with Firebase UID
        return self.user_repository.create_firebase_user(
            firebase_uid=firebase_uid,
            email=email,
            username=firebase_user_create.username,
        )

    async def authenticate_firebase_user(self, firebase_token: str) -> User:
        """
        Authenticate user with Firebase token.

        Args:
            firebase_token: Firebase ID token

        Returns:
            Authenticated user instance

        Raises:
            InvalidCredentialsError: If authentication fails
        """
        if not self.firebase_service:
            raise InvalidCredentialsError()

        # Verify Firebase token
        decoded_token = await self.firebase_service.verify_id_token(firebase_token)
        if not decoded_token:
            raise InvalidCredentialsError()

        firebase_uid = decoded_token["uid"]
        user = self.user_repository.get_active_user_by_firebase_uid(firebase_uid)

        if not user:
            raise InvalidCredentialsError()

        return user

    def create_user(self, user_create: UserCreate) -> User:
        """
        Create a new user with business logic validation.

        Args:
            user_create: User creation data

        Returns:
            Created user instance

        Raises:
            UserAlreadyExistsError: If email or username already exists
        """
        # Business logic: Check for duplicate email
        if self.user_repository.email_exists(user_create.email):
            raise UserAlreadyExistsError("email", user_create.email)

        # Business logic: Check for duplicate username
        if self.user_repository.username_exists(user_create.username):
            raise UserAlreadyExistsError("username", user_create.username)

        # Create Firebase user (no password needed)
        return self.user_repository.create_firebase_user(
            firebase_uid=user_create.firebase_uid,
            email=user_create.email,
            username=user_create.username,
        )

    def get_user_by_id(self, user_id: int) -> User:
        """
        Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User instance

        Raises:
            UserNotFoundError: If user not found
        """
        user = self.user_repository.get(user_id)
        if not user:
            raise UserNotFoundError(user_id=user_id)
        return user

    def get_user_by_firebase_uid(self, firebase_uid: str) -> User:
        """
        Get user by Firebase UID.

        Args:
            firebase_uid: Firebase UID

        Returns:
            User instance

        Raises:
            UserNotFoundError: If user not found
        """
        user = self.user_repository.get_by_firebase_uid(firebase_uid)
        if not user:
            raise UserNotFoundError(firebase_uid=firebase_uid)
        return user

    def get_user_by_username(self, username: str) -> User:
        """
        Get user by username.

        Args:
            username: Username

        Returns:
            User instance

        Raises:
            UserNotFoundError: If user not found
        """
        user = self.user_repository.get_by_username(username)
        if not user:
            raise UserNotFoundError(username=username)
        return user

    def get_user_by_email(self, email: str) -> User:
        """
        Get user by email.

        Args:
            email: User email

        Returns:
            User instance

        Raises:
            UserNotFoundError: If user not found
        """
        user = self.user_repository.get_by_email(email)
        if not user:
            raise UserNotFoundError(email=email)
        return user

    def update_user(self, user_id: int, user_update: UserUpdate) -> User:
        """
        Update user information with business logic validation.

        Args:
            user_id: User ID to update
            user_update: Update data

        Returns:
            Updated user instance

        Raises:
            UserNotFoundError: If user not found
            UserAlreadyExistsError: If email or username conflicts
        """
        user = self.user_repository.get(user_id)
        if not user:
            raise UserNotFoundError(user_id=user_id)

        # Business logic: Check for email conflicts
        if user_update.email and user_update.email != user.email:
            if self.user_repository.email_exists(user_update.email):
                raise UserAlreadyExistsError("email", user_update.email)

        # Business logic: Check for username conflicts
        if user_update.username and user_update.username != user.username:
            if self.user_repository.username_exists(user_update.username):
                raise UserAlreadyExistsError("username", user_update.username)

        return self.user_repository.update(user, user_update)

    def deactivate_user(self, user_id: int) -> User:
        """
        Deactivate a user account.

        Args:
            user_id: User ID to deactivate

        Returns:
            Deactivated user instance

        Raises:
            UserNotFoundError: If user not found
        """
        user = self.user_repository.deactivate_user(user_id)
        if not user:
            raise UserNotFoundError(user_id=user_id)
        return user

    def activate_user(self, user_id: int) -> User:
        """
        Activate a user account.

        Args:
            user_id: User ID to activate

        Returns:
            Activated user instance

        Raises:
            UserNotFoundError: If user not found
        """
        user = self.user_repository.activate_user(user_id)
        if not user:
            raise UserNotFoundError(user_id=user_id)
        return user

    def delete_user(self, user_id: int) -> User:
        """
        Delete a user account (soft delete by deactivation).

        Args:
            user_id: User ID to delete

        Returns:
            Deleted user instance

        Raises:
            UserNotFoundError: If user not found
        """
        return self.deactivate_user(user_id)

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
        return self.user_repository.get_users(skip, limit, active_only)

    def count_users(self, active_only: bool = False) -> int:
        """
        Count total number of users.

        Args:
            active_only: Whether to count only active users

        Returns:
            Number of users
        """
        return self.user_repository.count_users(active_only)
