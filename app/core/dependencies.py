from fastapi import Depends, HTTPException, status, Header, Request
from sqlalchemy.orm import Session
from typing import Optional

from app.core.config import settings
from app.core.database import get_db
from app.core.firebase import get_firebase_service, FirebaseService
from app.repositories.user import UserRepository
from app.repositories.pre_info import PreInfoRepository
from app.repositories.rec_plan import RecPlanRepository
from app.repositories.rec_spot import RecSpotRepository
from app.services.user import UserService
from app.services.pre_info import PreInfoService
from app.services.recommendation_service import RecommendationService
from app.services.llm_service import LLMService
from app.services.rec_plan import RecPlanService
from app.services.rec_spot import RecSpotService
from app.services.trip_refine import TripRefineService
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


def get_rec_plan_repository(db: Session = Depends(get_db)) -> RecPlanRepository:
    """
    Dependency to get rec_plan repository instance.

    Args:
        db: Database session dependency

    Returns:
        RecPlanRepository instance
    """
    return RecPlanRepository(db)


def get_rec_spot_repository(db: Session = Depends(get_db)) -> RecSpotRepository:
    """
    Dependency to get rec_spot repository instance.

    Args:
        db: Database session dependency

    Returns:
        RecSpotRepository instance
    """
    return RecSpotRepository(db)


def get_rec_plan_service(
    rec_plan_repo: RecPlanRepository = Depends(get_rec_plan_repository),
    pre_info_repo: PreInfoRepository = Depends(get_pre_info_repository),
    rec_spot_repo: RecSpotRepository = Depends(get_rec_spot_repository),
) -> RecPlanService:
    """
    Dependency to get rec_plan service instance.

    Args:
        rec_plan_repo: RecPlan repository dependency
        pre_info_repo: PreInfo repository dependency
        rec_spot_repo: RecSpot repository dependency

    Returns:
        RecPlanService instance
    """
    return RecPlanService(rec_plan_repo, pre_info_repo, rec_spot_repo)


def get_rec_spot_service(
    rec_spot_repo: RecSpotRepository = Depends(get_rec_spot_repository),
) -> RecSpotService:
    """
    Dependency to get rec_spot service instance.

    Args:
        rec_spot_repo: RecSpot repository dependency

    Returns:
        RecSpotService instance
    """
    return RecSpotService(rec_spot_repo)


def get_trip_refine_service(
    rec_plan_service: RecPlanService = Depends(get_rec_plan_service),
    rec_spot_service: RecSpotService = Depends(get_rec_spot_service),
    recommendation_service: RecommendationService = Depends(get_recommendation_service),
    llm_service: LLMService = Depends(get_llm_service),
) -> TripRefineService:
    """
    Dependency to get trip refine service instance.

    Args:
        rec_plan_service: RecPlan service dependency
        rec_spot_service: RecSpot service dependency
        recommendation_service: Recommendation service dependency
        llm_service: LLM service dependency

    Returns:
        TripRefineService instance
    """
    return TripRefineService(
        rec_plan_service, rec_spot_service, recommendation_service, llm_service
    )


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
    セッションベースユーザー認証（Firebaseトークンなしでセッションのみで認証）

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
    柔軟な認証方式 - Firebaseトークンまたはセッション両方をサポート

    Args:
        request: FastAPI request object
        firebase_token: Optional Firebase token
        user_service: User service dependency

    Returns:
        Current authenticated user

    Raises:
        HTTPException: If both authentication methods fail
    """
    # 1. FirebaseトークンがあればFirebase認証を試行
    if firebase_token:
        try:
            user = await user_service.authenticate_firebase_user(firebase_token)
            if user.is_active:
                return user
        except Exception:
            pass

    # 2. セッション認証を試行
    user_id = request.session.get("user_id")
    if user_id:
        try:
            user = user_service.get_user_by_id(user_id)
            if user.is_active:
                return user
        except Exception:
            pass

    # 3. 両方とも失敗した場合はエラー
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Please provide Firebase token or valid session.",
    )


# Test用
async def get_current_user_test(
    user_service: UserService = Depends(get_user_service),
) -> User:
    """
    テスト用依存性 - ハードコーディングされたユーザーを返す（開発環境でのみ使用）
    """
    if settings.ENVIRONMENT != "development":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Test authentication only available in development",
        )

    # テスト用ハードコーディングされたユーザー（最初のユーザー）
    try:
        # 既存のユーザーを取得（user_service를 통해）
        users = user_service.get_users(skip=0, limit=1, active_only=True)
        if users:
            return users[0]

        # ユーザーが存在しない場合はテストユーザーを作成
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
