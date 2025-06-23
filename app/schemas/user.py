from pydantic import BaseModel, EmailStr, ConfigDict, field_validator
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    """Base user schema with common attributes."""

    email: EmailStr
    username: str
    is_active: bool = True

    @field_validator("username")
    @classmethod
    def username_must_be_valid(cls, v):
        """Validate username format."""
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters long")
        if len(v) > 50:
            raise ValueError("Username must be less than 50 characters")
        if not v.replace("_", "").isalnum():
            raise ValueError(
                "Username can only contain letters, numbers, and underscores"
            )
        return v


class UserCreate(UserBase):
    """Schema for user creation requests."""

    firebase_uid: str


class FirebaseUserCreate(BaseModel):
    """Schema for Firebase user creation requests."""

    firebase_token: str
    username: str

    @field_validator("username")
    @classmethod
    def username_must_be_valid(cls, v):
        """Validate username format."""
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters long")
        if len(v) > 50:
            raise ValueError("Username must be less than 50 characters")
        if not v.replace("_", "").isalnum():
            raise ValueError(
                "Username can only contain letters, numbers, and underscores"
            )
        return v


class FirebaseAuth(BaseModel):
    """Schema for Firebase authentication requests."""

    firebase_token: str


class UserUpdate(BaseModel):
    """Schema for user update requests."""

    email: EmailStr | None = None
    username: str | None = None
    is_active: bool | None = None

    @field_validator("username")
    @classmethod
    def username_must_be_valid(cls, v):
        """Validate username format if provided."""
        if v is not None:
            if len(v) < 3:
                raise ValueError("Username must be at least 3 characters long")
            if len(v) > 50:
                raise ValueError("Username must be less than 50 characters")
            if not v.replace("_", "").isalnum():
                raise ValueError(
                    "Username can only contain letters, numbers, and underscores"
                )
        return v


class UserInDB(UserBase):
    """Schema for user data stored in database."""

    id: int
    firebase_uid: str
    is_superuser: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class User(UserBase):
    """Schema for user responses (public data only)."""

    id: int
    firebase_uid: str
    is_superuser: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SessionLoginResponse(BaseModel):
    """セッションログインレスポンススキーマ"""

    message: str
    user: User
    session_created: bool

    model_config = ConfigDict(from_attributes=True)


class LogoutResponse(BaseModel):
    """ログアウトレスポンススキーマ"""

    message: str
