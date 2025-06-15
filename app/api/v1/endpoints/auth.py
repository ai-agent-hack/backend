from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.config import settings
from app.core.security import create_access_token
from app.schemas.token import Token
from app.schemas.user import UserLogin
from app.services.user import UserService
from app.core.dependencies import get_user_service
from app.core.exceptions import InvalidCredentialsError

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    user_service: UserService = Depends(get_user_service),
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.

    Args:
        form_data: OAuth2 password form data (username, password)
        user_service: User service dependency

    Returns:
        Access token and token type

    Raises:
        HTTPException: If authentication fails
    """
    try:
        user = user_service.authenticate_user(
            username=form_data.username, password=form_data.password
        )
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.username, expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.post("/login/json", response_model=Token)
async def login_json(
    user_login: UserLogin, user_service: UserService = Depends(get_user_service)
) -> Any:
    """
    JSON-based login endpoint as an alternative to OAuth2 form.

    Args:
        user_login: User login credentials
        user_service: User service dependency

    Returns:
        Access token and token type

    Raises:
        HTTPException: If authentication fails
    """
    try:
        user = user_service.authenticate_user(
            username=user_login.username, password=user_login.password
        )
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.username, expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }
