from typing import Optional, List

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, FirebaseUserCreate
from app.repositories.user import UserRepository
from app.core.security import get_password_hash, verify_password
from app.core.firebase import FirebaseService
from app.core.exceptions import (
    UserAlreadyExistsError,
    UserNotFoundError,
    InvalidCredentialsError,
    ValidationError,
)


class UserService:
    """
    User service implementing business logic for user operations.
    Follows Single Responsibility Principle - handles only user business logic.
    """

    def __init__(
        self,
        user_repository: UserRepository,
        firebase_service: Optional[FirebaseService] = None,
    ):
        """
        Initialize user service with repository dependency.

        Args:
            user_repository: User repository for data access
            firebase_service: Firebase service for authentication
        """
        self.user_repository = user_repository
        self.firebase_service = firebase_service

    async def create_firebase_user(
        self, firebase_user_create: FirebaseUserCreate
    ) -> User:
        """
        Create a new user from Firebase authentication.

        Args:
            firebase_user_create: Firebase user creation data

        Returns:
            Created user instance

        Raises:
            ValidationError: If Firebase token is invalid
            UserAlreadyExistsError: If username already exists
        """
        if not self.firebase_service:
            raise ValidationError("Firebase service not initialized")

        # Verify Firebase token
        decoded_token = await self.firebase_service.verify_id_token(
            firebase_user_create.firebase_token
        )
        if not decoded_token:
            raise ValidationError("Invalid Firebase token")

        firebase_uid = decoded_token["uid"]
        email = decoded_token.get("email")

        if not email:
            raise ValidationError("Email not found in Firebase token")

        # Check if user already exists with this Firebase UID
        existing_user = self.user_repository.get_by_firebase_uid(firebase_uid)
        if existing_user:
            return existing_user  # Return existing user instead of error

        # Business logic: Check for duplicate username
        if self.user_repository.username_exists(firebase_user_create.username):
            raise UserAlreadyExistsError("username", firebase_user_create.username)

        # Create user with Firebase data
        return self.user_repository.create_firebase_user(
            firebase_uid=firebase_uid,
            email=email,
            username=firebase_user_create.username,
            full_name=firebase_user_create.full_name,
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

        # Hash the password before storing
        hashed_password = get_password_hash(user_create.password)

        return self.user_repository.create_user_with_hashed_password(
            user_create, hashed_password
        )

    def authenticate_user(self, username: str, password: str) -> User:
        """
        Authenticate user with username and password.

        Args:
            username: Username or email
            password: Plain text password

        Returns:
            Authenticated user instance

        Raises:
            InvalidCredentialsError: If authentication fails
        """
        # Try to find user by username first, then by email
        user = self.user_repository.get_active_user_by_username(username)
        if not user:
            user = self.user_repository.get_active_user_by_email(username)

        if not user:
            raise InvalidCredentialsError()

        # Skip password verification for Firebase users (no hashed_password)
        if user.hashed_password is None:
            raise InvalidCredentialsError()

        if not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError()

        return user

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

        # Hash password if being updated (only for non-Firebase users)
        if user_update.password and user.hashed_password is not None:
            # Create a copy of the update data
            update_data = user_update.dict(exclude_unset=True)
            update_data["hashed_password"] = get_password_hash(user_update.password)
            del update_data["password"]

            # Create new UserUpdate instance without password
            user_update = UserUpdate(**update_data)

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
            List of user instances
        """
        users = self.user_repository.get_multi(skip=skip, limit=limit)
        if active_only:
            users = [user for user in users if user.is_active]
        return users

    def count_users(self, active_only: bool = False) -> int:
        """
        Count total number of users.

        Args:
            active_only: Whether to count only active users

        Returns:
            Total number of users
        """
        # This is a simple implementation - in a real app, you'd want
        # to implement this in the repository for better performance
        users = self.get_users(skip=0, limit=10000, active_only=active_only)
        return len(users)
