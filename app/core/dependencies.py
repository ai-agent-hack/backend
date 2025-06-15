from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_token
from app.repositories.user import UserRepository
from app.services.user import UserService
from app.models.user import User
from app.core.exceptions import UserNotFoundError

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    """
    Dependency to get user repository instance.

    Args:
        db: Database session dependency

    Returns:
        UserRepository instance
    """
    return UserRepository(db)


def get_user_service(
    user_repository: UserRepository = Depends(get_user_repository),
) -> UserService:
    """
    Dependency to get user service instance.

    Args:
        user_repository: User repository dependency

    Returns:
        UserService instance
    """
    return UserService(user_repository)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    user_service: UserService = Depends(get_user_service),
) -> User:
    """
    Dependency to get current authenticated user from JWT token.

    Args:
        token: JWT token from Authorization header
        user_service: User service dependency

    Returns:
        Current authenticated user

    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode JWT token
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    try:
        # Get user from database
        user = user_service.get_user_by_username(username)
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
            )
        return user
    except UserNotFoundError:
        raise credentials_exception


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency to get current active user.

    Args:
        current_user: Current user dependency

    Returns:
        Current active user

    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )
    return current_user


def get_current_superuser(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency to get current superuser.

    Args:
        current_user: Current user dependency

    Returns:
        Current superuser

    Raises:
        HTTPException: If user is not a superuser
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )
    return current_user


# Optional dependency that doesn't raise exception if no token provided
oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False
)


async def get_current_user_optional(
    token: str = Depends(oauth2_scheme_optional),
    user_service: UserService = Depends(get_user_service),
) -> User | None:
    """
    Optional dependency to get current user (doesn't raise exception if no token).

    Args:
        token: Optional JWT token
        user_service: User service dependency

    Returns:
        Current user if token is valid, None otherwise
    """
    if not token:
        return None

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        username: str = payload.get("sub")
        if username is None:
            return None

        user = user_service.get_user_by_username(username)
        return user if user.is_active else None
    except (JWTError, UserNotFoundError):
        return None
