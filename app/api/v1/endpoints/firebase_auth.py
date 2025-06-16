from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any

from app.schemas.user import User, FirebaseUserCreate, FirebaseAuth, Token
from app.services.user import UserService
from app.core.dependencies import get_user_service, get_current_user_firebase
from app.core.exceptions import UserAlreadyExistsError, ValidationError
from app.core.security import create_access_token
from app.core.config import settings
from datetime import timedelta

router = APIRouter()


@router.post("/signup", response_model=User, status_code=status.HTTP_201_CREATED)
async def firebase_signup(
    firebase_user_create: FirebaseUserCreate,
    user_service: UserService = Depends(get_user_service),
) -> Any:
    """
    Firebase 회원가입 엔드포인트.

    Firebase에서 이미 인증된 사용자를 우리 데이터베이스에 등록합니다.

    Args:
        firebase_user_create: Firebase 사용자 생성 데이터
        user_service: 사용자 서비스 의존성

    Returns:
        생성된 사용자 정보

    Raises:
        HTTPException: 토큰이 유효하지 않거나 사용자명이 이미 존재하는 경우
    """
    try:
        user = await user_service.create_firebase_user(firebase_user_create)
        return user
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except UserAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with {e.field} '{e.value}' already exists",
        )


@router.post("/login", response_model=Token)
async def firebase_login(
    firebase_auth: FirebaseAuth,
    user_service: UserService = Depends(get_user_service),
) -> Any:
    """
    Firebase 로그인 엔드포인트.

    Firebase 토큰을 검증하고 JWT 토큰을 반환합니다.

    Args:
        firebase_auth: Firebase 인증 데이터
        user_service: 사용자 서비스 의존성

    Returns:
        JWT 액세스 토큰

    Raises:
        HTTPException: 인증에 실패한 경우
    """
    try:
        user = await user_service.authenticate_firebase_user(
            firebase_auth.firebase_token
        )

        # JWT 토큰 생성
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            subject=user.username, expires_delta=access_token_expires
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
        }
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase authentication failed",
            headers={"WWW-Authenticate": "Firebase"},
        )


@router.get("/me", response_model=User)
async def get_current_user_info(
    current_user: User = Depends(get_current_user_firebase),
) -> Any:
    """
    Firebase 토큰으로 현재 사용자 정보를 가져옵니다.

    Args:
        current_user: 현재 사용자 (Firebase 토큰으로 인증됨)

    Returns:
        현재 사용자 정보
    """
    return current_user


@router.post("/verify", response_model=User)
async def verify_firebase_token(
    current_user: User = Depends(get_current_user_firebase),
) -> Any:
    """
    Firebase 토큰을 검증하고 사용자 정보를 반환합니다.

    Args:
        current_user: 현재 사용자 (Firebase 토큰으로 인증됨)

    Returns:
        사용자 정보
    """
    return current_user
