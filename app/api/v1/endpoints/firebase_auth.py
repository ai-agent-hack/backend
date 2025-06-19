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
    Firebaseユーザー登録エンドポイント。

    Firebaseで既に認証されたユーザーをデータベースに登録します。

    Args:
        firebase_user_create: Firebaseユーザー作成データ
        user_service: ユーザーサービス依存性

    Returns:
        作成されたユーザー情報

    Raises:
        HTTPException: トークンが無効またはユーザー名が既に存在する場合
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
    Firebaseログインエンドポイント。

    Firebaseトークンを検証してJWTトークンを返します。

    Args:
        firebase_auth: Firebase認証データ
        user_service: ユーザーサービス依存性

    Returns:
        JWTアクセストークン

    Raises:
        HTTPException: 認証に失敗した場合
    """
    try:
        user = await user_service.authenticate_firebase_user(
            firebase_auth.firebase_token
        )

        # JWT トークン生成
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
    Firebaseトークンで現在のユーザー情報を取得します。

    Args:
        current_user: 現在のユーザー（Firebaseトークンで認証済み）

    Returns:
        現在のユーザー情報
    """
    return current_user


@router.post("/verify", response_model=User)
async def verify_firebase_token(
    current_user: User = Depends(get_current_user_firebase),
) -> Any:
    """
    Firebaseトークンを検証してユーザー情報を返します。

    Args:
        current_user: 現在のユーザー（Firebaseトークンで認証済み）

    Returns:
        ユーザー情報
    """
    return current_user
