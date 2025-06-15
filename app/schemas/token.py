from pydantic import BaseModel
from typing import Optional


class Token(BaseModel):
    """Schema for authentication token response."""

    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Schema for token payload data."""

    username: Optional[str] = None
    user_id: Optional[int] = None
