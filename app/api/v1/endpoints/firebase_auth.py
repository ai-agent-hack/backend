from fastapi import APIRouter, Depends, HTTPException, status, Request
from typing import Any

from app.schemas.user import (
    User,
    FirebaseUserCreate,
    FirebaseAuth,
    SessionLoginResponse,
    LogoutResponse,
)
from app.services.user import UserService
from app.core.dependencies import (
    get_user_service,
    get_current_user_firebase,
    get_current_user_session,
    get_current_user_flexible,
)
from app.core.exceptions import UserAlreadyExistsError, InvalidCredentialsError

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
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="無効なFirebaseトークンです"
        )
    except UserAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{e.field} '{e.value}' のユーザーが既に存在します",
        )


@router.post("/login", response_model=User)
async def firebase_login(
    current_user: User = Depends(get_current_user_firebase),
) -> Any:
    """
    Firebaseログインエンドポイント。

    Firebaseログイン後に受け取ったトークンでバックエンドユーザー情報を確認します。

    Args:
        current_user: Firebaseトークンで認証された現在のユーザー

    Returns:
        ユーザー情報と認証状態
    """
    return current_user


@router.post("/session-login", response_model=SessionLoginResponse)
async def firebase_session_login(
    request: Request,
    current_user: User = Depends(get_current_user_firebase),
) -> Any:
    """
    Firebaseセッションログインエンドポイント。

    Firebaseトークンで認証後、セッションを作成して以降のAPI呼び出し時にトークン不要にします。

    Args:
        request: FastAPI request object
        current_user: Firebaseトークンで認証された現在のユーザー

    Returns:
        ユーザー情報とセッション作成状態
    """
    # セッションにユーザーID保存
    request.session["user_id"] = current_user.id
    return SessionLoginResponse(
        message="セッションログインが完了しました", user=current_user, session_created=True
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(request: Request) -> Any:
    """
    ログアウトエンドポイント - セッション削除

    Returns:
        ログアウト完了メッセージ
    """
    request.session.clear()
    return LogoutResponse(message="ログアウトが完了しました")


@router.get("/me", response_model=User)
async def get_current_user_info(
    current_user: User = Depends(get_current_user_flexible),
) -> Any:
    """
    現在のユーザー情報を取得します。（Firebaseトークンまたはセッション認証）

    Args:
        current_user: 現在のユーザー（Firebaseトークンまたはセッションで認証済み）

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
