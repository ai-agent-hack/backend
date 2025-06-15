from pydantic import BaseModel, EmailStr, ConfigDict, field_validator
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    """Base user schema with common attributes."""

    email: EmailStr
    username: str
    full_name: Optional[str] = None
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

    password: str

    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if len(v) > 100:
            raise ValueError("Password must be less than 100 characters")
        return v


class UserUpdate(BaseModel):
    """Schema for user update requests."""

    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None

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

    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, v):
        """Validate password strength if provided."""
        if v is not None:
            if len(v) < 8:
                raise ValueError("Password must be at least 8 characters long")
            if len(v) > 100:
                raise ValueError("Password must be less than 100 characters")
        return v


class UserInDB(UserBase):
    """Schema for user data stored in database."""

    id: int
    hashed_password: str
    is_superuser: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class User(UserBase):
    """Schema for user responses (public data only)."""

    id: int
    is_superuser: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    """Schema for user login requests."""

    username: str  # Can be username or email
    password: str


class Token(BaseModel):
    """Schema for authentication token response."""

    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Schema for token payload data."""

    username: Optional[str] = None
