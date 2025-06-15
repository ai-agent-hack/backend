from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status, Query

from app.schemas.user import User, UserCreate, UserUpdate
from app.services.user import UserService
from app.core.dependencies import (
    get_user_service,
    get_current_active_user,
    get_current_superuser,
)
from app.core.exceptions import (
    UserAlreadyExistsError,
    UserNotFoundError,
    ValidationError,
)

router = APIRouter()


@router.post("/", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate, user_service: UserService = Depends(get_user_service)
) -> Any:
    """
    Create new user.

    Args:
        user_in: User creation data
        user_service: User service dependency

    Returns:
        Created user data

    Raises:
        HTTPException: If user already exists or validation fails
    """
    try:
        user = user_service.create_user(user_in)
        return user
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )


@router.get("/me", response_model=User)
async def read_user_me(current_user: User = Depends(get_current_active_user)) -> Any:
    """
    Get current user profile.

    Args:
        current_user: Current authenticated user

    Returns:
        Current user data
    """
    return current_user


@router.put("/me", response_model=User)
async def update_user_me(
    user_in: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service),
) -> Any:
    """
    Update current user profile.

    Args:
        user_in: User update data
        current_user: Current authenticated user
        user_service: User service dependency

    Returns:
        Updated user data

    Raises:
        HTTPException: If validation fails or conflicts occur
    """
    try:
        user = user_service.update_user(current_user.id, user_in)
        return user
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )


@router.get("/{user_id}", response_model=User)
async def read_user_by_id(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service),
) -> Any:
    """
    Get user by ID. Users can only access their own profile unless they are superusers.

    Args:
        user_id: User ID to retrieve
        current_user: Current authenticated user
        user_service: User service dependency

    Returns:
        User data

    Raises:
        HTTPException: If user not found or insufficient permissions
    """
    # Users can only access their own profile unless they are superusers
    if user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    try:
        user = user_service.get_user_by_id(user_id)
        return user
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )


@router.put("/{user_id}", response_model=User)
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service),
) -> Any:
    """
    Update user by ID. Users can only update their own profile unless they are superusers.

    Args:
        user_id: User ID to update
        user_in: User update data
        current_user: Current authenticated user
        user_service: User service dependency

    Returns:
        Updated user data

    Raises:
        HTTPException: If user not found, insufficient permissions, or validation fails
    """
    # Users can only update their own profile unless they are superusers
    if user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    try:
        user = user_service.update_user(user_id, user_in)
        return user
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )


@router.get("/", response_model=List[User])
async def read_users(
    skip: int = Query(0, ge=0, description="Number of users to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of users to return"),
    active_only: bool = Query(False, description="Return only active users"),
    current_user: User = Depends(get_current_superuser),
    user_service: UserService = Depends(get_user_service),
) -> Any:
    """
    Retrieve users. Only accessible by superusers.

    Args:
        skip: Number of users to skip for pagination
        limit: Maximum number of users to return
        active_only: Whether to return only active users
        current_user: Current authenticated superuser
        user_service: User service dependency

    Returns:
        List of users
    """
    users = user_service.get_users(skip=skip, limit=limit, active_only=active_only)
    return users


@router.delete("/{user_id}", response_model=User)
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_superuser),
    user_service: UserService = Depends(get_user_service),
) -> Any:
    """
    Delete user by ID. Only accessible by superusers.

    Args:
        user_id: User ID to delete
        current_user: Current authenticated superuser
        user_service: User service dependency

    Returns:
        Deleted user data

    Raises:
        HTTPException: If user not found
    """
    try:
        user = user_service.delete_user(user_id)
        return user
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )


@router.post("/{user_id}/deactivate", response_model=User)
async def deactivate_user(
    user_id: int,
    current_user: User = Depends(get_current_superuser),
    user_service: UserService = Depends(get_user_service),
) -> Any:
    """
    Deactivate user by ID. Only accessible by superusers.

    Args:
        user_id: User ID to deactivate
        current_user: Current authenticated superuser
        user_service: User service dependency

    Returns:
        Deactivated user data

    Raises:
        HTTPException: If user not found
    """
    try:
        user = user_service.deactivate_user(user_id)
        return user
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )


@router.post("/{user_id}/activate", response_model=User)
async def activate_user(
    user_id: int,
    current_user: User = Depends(get_current_superuser),
    user_service: UserService = Depends(get_user_service),
) -> Any:
    """
    Activate user by ID. Only accessible by superusers.

    Args:
        user_id: User ID to activate
        current_user: Current authenticated superuser
        user_service: User service dependency

    Returns:
        Activated user data

    Raises:
        HTTPException: If user not found
    """
    try:
        user = user_service.activate_user(user_id)
        return user
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
