from fastapi import Depends, HTTPException, status, Header, Request
from sqlalchemy.orm import Session
from typing import Optional

from app.core.config import settings
from app.core.database import get_db
from app.core.firebase import get_firebase_service, FirebaseService
from app.repositories.user import UserRepository
from app.repositories.pre_info import PreInfoRepository
from app.services.user import UserService
from app.services.pre_info import PreInfoService
from app.services.recommendation_service import RecommendationService
from app.services.llm_service import LLMService
from app.models.user import User
from app.core.exceptions import UserNotFoundError


def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    """
    Dependency to get user repository instance.

    Args:
        db: Database session dependency

    Returns:
        UserRepository instance
    """
    return UserRepository(db)


def get_pre_info_repository(db: Session = Depends(get_db)) -> PreInfoRepository:
    """
    Dependency to get pre_info repository instance.

    Args:
        db: Database session dependency

    Returns:
        PreInfoRepository instance
    """
    return PreInfoRepository(db)


def get_user_service(
    user_repository: UserRepository = Depends(get_user_repository),
    firebase_service: FirebaseService = Depends(get_firebase_service),
) -> UserService:
    """
    Dependency to get user service instance.

    Args:
        user_repository: User repository dependency
        firebase_service: Firebase service dependency

    Returns:
        UserService instance
    """
    return UserService(user_repository, firebase_service)


def get_pre_info_service(
    pre_info_repository: PreInfoRepository = Depends(get_pre_info_repository),
) -> PreInfoService:
    """
    Dependency to get pre_info service instance.

    Args:
        pre_info_repository: PreInfo repository dependency

    Returns:
        PreInfoService instance
    """
    return PreInfoService(pre_info_repository)


def get_llm_service() -> LLMService:
    """
    Dependency to get LLM service instance.

    Returns:
        LLMService instance
    """
    return LLMService()


def get_recommendation_service(
    llm_service: LLMService = Depends(get_llm_service),
) -> RecommendationService:
    """
    Dependency to get recommendation service instance.

    Args:
        llm_service: LLM service dependency

    Returns:
        RecommendationService instance
    """
    return RecommendationService()


async def get_current_user_firebase(
    firebase_token: Optional[str] = Header(None, alias="Firebase-Token"),
    user_service: UserService = Depends(get_user_service),
) -> User:
    """
    Dependency to get current authenticated user from Firebase token.

    Args:
        firebase_token: Firebase ID token from Firebase-Token header
        user_service: User service dependency

    Returns:
        Current authenticated user

    Raises:
        HTTPException: If token is invalid or user not found
    """
    if not firebase_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase token required",
            headers={"WWW-Authenticate": "Firebase"},
        )

    try:
        # Authenticate user with Firebase token
        user = await user_service.authenticate_firebase_user(firebase_token)
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
            )
        return user
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate Firebase credentials",
            headers={"WWW-Authenticate": "Firebase"},
        )


async def get_current_user_session(
    request: Request,
    user_service: UserService = Depends(get_user_service),
) -> User:
    """
    세션 기반 사용자 인증 (Firebase 토큰 없이 세션만으로 인증)

    Args:
        request: FastAPI request object with session
        user_service: User service dependency

    Returns:
        Current authenticated user from session

    Raises:
        HTTPException: If session is invalid or user not found
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session required. Please login first.",
        )

    try:
        user = user_service.get_user_by_id(user_id)
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
            )
        return user
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
        )


async def get_current_user_flexible(
    request: Request,
    firebase_token: Optional[str] = Header(None, alias="Firebase-Token"),
    user_service: UserService = Depends(get_user_service),
) -> User:
    """
    유연한 인증 방식 - Firebase 토큰 또는 세션 둘 다 지원

    Args:
        request: FastAPI request object
        firebase_token: Optional Firebase token
        user_service: User service dependency

    Returns:
        Current authenticated user

    Raises:
        HTTPException: If both authentication methods fail
    """
    # 1. Firebase 토큰이 있으면 Firebase 인증 시도
    if firebase_token:
        try:
            user = await user_service.authenticate_firebase_user(firebase_token)
            if user.is_active:
                return user
        except Exception:
            pass

    # 2. 세션 인증 시도
    user_id = request.session.get("user_id")
    if user_id:
        try:
            user = user_service.get_user_by_id(user_id)
            if user.is_active:
                return user
        except Exception:
            pass

    # 3. 둘 다 실패하면 에러
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Please provide Firebase token or valid session.",
    )


# Test用
async def get_current_user_test(
    user_service: UserService = Depends(get_user_service),
) -> User:
    """
    테스트용 의존성 - 하드코딩된 사용자 반환 (개발 환경에서만 사용)
    """
    if settings.ENVIRONMENT != "development":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Test authentication only available in development",
        )

    # 테스트용 하드코딩된 사용자 (첫 번째 사용자)
    try:
        # Firebase UID로 사용자 찾기 (테스트용)
        from app.repositories.user import UserRepository
        from app.core.database import get_db

        db = next(get_db())
        user_repo = UserRepository(db)

        # 첫 번째 active 사용자 반환
        users = user_repo.get_multi(skip=0, limit=1)
        if users:
            return users[0]

        # 사용자가 없으면 테스트 사용자 생성
        from app.schemas.user import UserCreate

        test_user = UserCreate(
            email="test@example.com",
            username="testuser",
            firebase_uid="test-firebase-uid",
        )
        return user_service.create_user(test_user)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get test user: {str(e)}",
        )
